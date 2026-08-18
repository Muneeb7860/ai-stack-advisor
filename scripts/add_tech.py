#!/usr/bin/env python3
"""
Maintainer Authoring & Validation Tool for ai-stack-advisor's Knowledge Base.

Usage:
  # Validate the current KB in index.html:
  python3 scripts/add_tech.py --validate

  # Add a technology from a JSON file:
  python3 scripts/add_tech.py --file my_tech.json

  # Interactive prompt to add a technology:
  python3 scripts/add_tech.py --interactive
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

INDEX_HTML_PATH = Path(__file__).resolve().parents[1] / "index.html"

REQUIRED_FIELDS = [
    "id",
    "name",
    "category",
    "domain",
    "maturity",
    "license",
    "best_when",
    "avoid_when",
    "alternatives",
    "innovation_token_cost",
    "signal_keywords",
]

VALID_DOMAINS = [
    "frontend",
    "backend",
    "database",
    "cloud",
    "cicd",
    "identity",
    "integration",
    "observability",
    "mobile",
    "architecture",
    "ai",
    "quality",
    "llm-strategy",
    "llm-tier",
]

VALID_RINGS = ["adopt", "trial", "assess", "hold", "adopt-with-prerequisites"]
VALID_HIRING_POOLS = ["very-high", "high", "medium", "low", "niche"]


def read_kb(html_path: Path = INDEX_HTML_PATH) -> Tuple[dict, Tuple[int, int], str]:
    if not html_path.exists():
        raise FileNotFoundError(f"index.html not found at {html_path}")
    content = html_path.read_text(encoding="utf-8")
    m = re.search(r'(<script type="application/json" id="stackKbData">\s*)([\s\S]*?)(\s*</script>)', content)
    if not m:
        raise ValueError("Could not find <script type=\"application/json\" id=\"stackKbData\"> in index.html")
    kb_data = json.loads(m.group(2))
    span = (m.start(2), m.end(2))
    return kb_data, span, content


def write_kb(kb_data: dict, html_path: Path = INDEX_HTML_PATH):
    _, span, content = read_kb(html_path)
    formatted_json = json.dumps(kb_data, indent=2, ensure_ascii=False)
    new_content = content[:span[0]] + formatted_json + content[span[1]:]
    html_path.write_text(new_content, encoding="utf-8")


def validate_tech_entry(tech: Dict[str, Any], existing_ids: set) -> List[str]:
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in tech:
            errors.append(f"Missing required field: '{field}'")

    tech_id = tech.get("id", "")
    if not tech_id or not isinstance(tech_id, str):
        errors.append("Field 'id' must be a non-empty string.")
    elif tech_id in existing_ids:
        errors.append(f"Technology with ID '{tech_id}' already exists in catalog.")

    if not isinstance(tech.get("name"), str) or not tech.get("name", "").strip():
        errors.append("Field 'name' must be a non-empty string.")

    domain = tech.get("domain")
    if domain not in VALID_DOMAINS:
        errors.append(f"Invalid domain '{domain}'. Must be one of {VALID_DOMAINS}.")

    maturity = tech.get("maturity")
    if not isinstance(maturity, dict) or maturity.get("ring") not in VALID_RINGS:
        errors.append(f"Field 'maturity' must be an object with 'ring' in {VALID_RINGS}.")

    if not isinstance(tech.get("best_when"), list) or len(tech.get("best_when", [])) == 0:
        errors.append("Field 'best_when' must be a non-empty list of strings.")

    if not isinstance(tech.get("avoid_when"), list) or len(tech.get("avoid_when", [])) == 0:
        errors.append("Field 'avoid_when' must be a non-empty list of strings.")

    if not isinstance(tech.get("alternatives"), list):
        errors.append("Field 'alternatives' must be a list of strings.")

    if not isinstance(tech.get("signal_keywords"), list) or len(tech.get("signal_keywords", [])) == 0:
        errors.append("Field 'signal_keywords' must be a non-empty list of strings (for keyword trigger matching).")

    if not isinstance(tech.get("innovation_token_cost"), (int, float)):
        errors.append("Field 'innovation_token_cost' must be a number (0, 1, or 2).")

    return errors


def validate_full_kb(html_path: Path = INDEX_HTML_PATH) -> bool:
    kb_data, _, _ = read_kb(html_path)
    technologies = kb_data.get("technologies", [])
    print(f"🔍 Validating {len(technologies)} technologies in {html_path.name}...")

    seen_ids = set()
    total_errors = 0

    for i, tech in enumerate(technologies):
        tid = tech.get("id", f"entry_{i}")
        # Validate without treating tid itself as duplicate against empty set
        temp_ids = set(seen_ids)
        errors = validate_tech_entry(tech, temp_ids)
        seen_ids.add(tid)
        if errors:
            print(f"❌ Errors in '{tid}':")
            for err in errors:
                print(f"   - {err}")
            total_errors += len(errors)

    if total_errors == 0:
        print(f"✅ All {len(technologies)} technologies passed validation!")
        return True
    else:
        print(f"❌ Validation failed with {total_errors} errors.")
        return False


def add_technology(tech_data: Dict[str, Any], html_path: Path = INDEX_HTML_PATH) -> bool:
    kb_data, _, _ = read_kb(html_path)
    existing_ids = {t["id"] for t in kb_data.get("technologies", [])}
    
    errors = validate_tech_entry(tech_data, existing_ids)
    if errors:
        print(f"❌ Cannot add technology '{tech_data.get('id')}':")
        for err in errors:
            print(f"   - {err}")
        return False

    kb_data.setdefault("technologies", []).append(tech_data)
    write_kb(kb_data, html_path)
    print(f"✅ Successfully added '{tech_data['name']}' ({tech_data['id']}) to {html_path.name}!")
    return True


def interactive_add():
    print("✨ Interactive Technology Authoring ✨\n")
    tech_id = input("ID (kebab-case, e.g. 'dynatrace'): ").strip()
    name = input("Display Name (e.g. 'Dynatrace'): ").strip()
    category = input("Category (e.g. 'observability-apm'): ").strip()
    print(f"Valid domains: {', '.join(VALID_DOMAINS)}")
    domain = input("Domain: ").strip()
    ring = input("Maturity Ring (adopt/trial/assess/hold) [default: adopt]: ").strip() or "adopt"
    source_id = input("Maturity Source ID [default: twr34]: ").strip() or "twr34"
    hiring_pool = input("Hiring Pool (very-high/high/medium/low/niche) [default: medium]: ").strip() or "medium"
    license_type = input("License (e.g. 'Proprietary SaaS', 'Apache-2.0', 'MIT'): ").strip() or "Proprietary SaaS"
    
    best_when_raw = input("Best When (comma-separated): ").strip()
    best_when = [b.strip() for b in best_when_raw.split(",") if b.strip()]

    avoid_when_raw = input("Avoid When (comma-separated): ").strip()
    avoid_when = [a.strip() for a in avoid_when_raw.split(",") if a.strip()]

    alts_raw = input("Alternatives (comma-separated IDs): ").strip()
    alternatives = [a.strip() for a in alts_raw.split(",") if a.strip()]

    keywords_raw = input("Signal Keywords (comma-separated match words, e.g. 'dynatrace, dynatrace apm'): ").strip()
    signal_keywords = [k.strip().lower() for k in keywords_raw.split(",") if k.strip()]

    token_cost = int(input("Innovation Token Cost (0, 1, 2) [default: 0]: ").strip() or "0")

    entry = {
        "id": tech_id,
        "name": name,
        "category": category,
        "domain": domain,
        "surfaces": ["backend", "ops"],
        "maturity": {
            "ring": ring,
            "source_id": source_id,
        },
        "hiring_pool": hiring_pool,
        "hiring_source_id": "so2025",
        "license": license_type,
        "hosting": ["saas", "cloud"],
        "exit_cost": "medium",
        "tco_shape": "vendor-heavy",
        "best_when": best_when or ["enterprise monitoring standard"],
        "avoid_when": avoid_when or ["tight budget early stage startup"],
        "alternatives": alternatives,
        "innovation_token_cost": token_cost,
        "signal_keywords": signal_keywords or [tech_id],
    }

    add_technology(entry)


def main():
    parser = argparse.ArgumentParser(description="Author and validate technologies in stackKbData.")
    parser.add_argument("--validate", action="store_true", help="Validate all technologies in index.html.")
    parser.add_argument("--file", type=str, help="Path to a JSON file containing a technology entry to add.")
    parser.add_argument("--interactive", action="store_true", help="Run interactive CLI authoring wizard.")

    args = parser.parse_args()

    if args.validate:
        success = validate_full_kb()
        sys.exit(0 if success else 1)
    elif args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ File not found: {file_path}")
            sys.exit(1)
        tech_data = json.loads(file_path.read_text(encoding="utf-8"))
        success = add_technology(tech_data)
        sys.exit(0 if success else 1)
    elif args.interactive:
        interactive_add()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
