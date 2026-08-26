"""
Contract tests for stackKbData schema, technology catalog integrity, and zero-drift signal keywords.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"

requires_node = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="Node.js binary not found on PATH; skipping JS runtime tests",
)

REQUIRED_TECH_FIELDS = [
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


def _extract_kb_data() -> dict:
    assert INDEX_HTML.exists(), f"index.html not found at {INDEX_HTML}"
    content = INDEX_HTML.read_text(encoding="utf-8")
    m = re.search(r'<script type="application/json" id="stackKbData">\s*([\s\S]*?)\s*</script>', content)
    assert m, "Knowledge-base block <script type=\"application/json\" id=\"stackKbData\"> not found in index.html"
    return json.loads(m.group(1))


def test_kb_json_is_valid_and_has_required_sections():
    kb = _extract_kb_data()
    assert "meta" in kb
    assert "technologies" in kb
    assert isinstance(kb["technologies"], list)
    assert len(kb["technologies"]) >= 216


def test_every_technology_conforms_to_schema():
    kb = _extract_kb_data()
    techs = kb["technologies"]
    seen_ids = set()

    for tech in techs:
        tech_id = tech.get("id")
        assert tech_id, "Technology entry missing id"
        assert tech_id not in seen_ids, f"Duplicate technology ID found: {tech_id}"
        seen_ids.add(tech_id)

        # Check required fields
        for field in REQUIRED_TECH_FIELDS:
            assert field in tech, f"Tech '{tech_id}' is missing required field: '{field}'"

        # Check types
        assert isinstance(tech["name"], str) and tech["name"].strip()
        assert isinstance(tech["category"], str) and tech["category"].strip()
        assert tech["domain"] in VALID_DOMAINS, f"Tech '{tech_id}' has invalid domain: '{tech.get('domain')}'"
        assert isinstance(tech["best_when"], list) and len(tech["best_when"]) > 0
        assert isinstance(tech["avoid_when"], list) and len(tech["avoid_when"]) > 0
        assert isinstance(tech["alternatives"], list)
        assert isinstance(tech["signal_keywords"], list), f"Tech '{tech_id}' signal_keywords must be a list of strings"
        assert isinstance(tech["innovation_token_cost"], (int, float))

        # Check maturity structure
        maturity = tech.get("maturity")
        assert isinstance(maturity, dict), f"Tech '{tech_id}' maturity must be an object"
        assert maturity.get("ring") in VALID_RINGS, f"Tech '{tech_id}' invalid maturity ring: {maturity.get('ring')}"


def test_alternatives_integrity():
    kb = _extract_kb_data()
    tech_ids = {t["id"] for t in kb["technologies"]}
    backlog_ids = set(kb.get("meta", {}).get("expansion_backlog", {}).get("ids", []))

    for tech in kb["technologies"]:
        for alt_id in tech.get("alternatives", []):
            assert alt_id in tech_ids or alt_id in backlog_ids, (
                f"Tech '{tech['id']}' references alternative '{alt_id}' which does not exist in "
                f"technologies and is not tracked in meta.expansion_backlog.ids"
            )


def test_key_observability_and_quality_technologies_exist():
    kb = _extract_kb_data()
    tech_ids = {t["id"] for t in kb["technologies"]}
    critical_tools = [
        "dynatrace",
        "datadog",
        "splunk",
        "newrelic",
        "elasticsearch",
        "grafana",
        "sonarqube",
        "jprofiler",
        "visualvm",
    ]
    for tool in critical_tools:
        assert tool in tech_ids, f"Critical technology '{tool}' is missing from stackKbData.technologies"


@requires_node
def test_runtime_detect_signals_matches_signal_keywords():
    source = INDEX_HTML.read_text(encoding="utf-8")
    parts = source.split("<script>")
    script = parts[2].split("</script>")[0]
    
    node_harness = f"""
    const dummyEl = {{ style: {{}}, classList: {{ add: () => {{}}, remove: () => {{}}, toggle: () => {{}} }}, addEventListener: () => {{}}, setAttribute: () => {{}}, getAttribute: () => null }};
    global.window = {{ location: {{ search: "" }}, addEventListener: () => {{}} }};
    global.document = {{ documentElement: dummyEl, querySelectorAll: () => [], getElementById: () => dummyEl, addEventListener: () => {{}} }};
    global.navigator = {{ clipboard: {{}} }};
    global.fetch = () => Promise.resolve({{ ok: false }});

    {script}

    const testPhrases = [
      {{ text: "We need Dynatrace for APM and SonarQube for static analysis.", checks: ["dynatraceMentioned", "sonarqubeMentioned"] }},
      {{ text: "Using Grafana dashboards with Prometheus metrics and JProfiler.", checks: ["prometheusMentioned", "grafanaMentioned", "jprofilerMentioned"] }},
      {{ text: "VisualVM and Splunk for error diagnostics.", checks: ["visualvmMentioned", "splunkMentioned"] }}
    ];

    const results = testPhrases.map(p => {{
      const sigs = detectSignals(p.text);
      return {{
        text: p.text,
        matches: p.checks.every(k => sigs[k] === true),
        sigs: p.checks.map(k => [k, sigs[k]])
      }};
    }});

    console.log(JSON.stringify(results));
    """
    proc = subprocess.run(["node", "-e", node_harness], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, f"Node execution failed:\n{proc.stderr}"
    results = json.loads(proc.stdout)
    for r in results:
        assert r["matches"] is True, f"Signal detection failed on: {r['text']}, detail: {r['sigs']}"


@requires_node
def test_runtime_custom_kb_overlay():
    source = INDEX_HTML.read_text(encoding="utf-8")
    parts = source.split("<script>")
    script = parts[2].split("</script>")[0]
    
    node_harness = f"""
    const store = {{}};
    global.localStorage = {{
      getItem: (k) => store[k] || null,
      setItem: (k, v) => {{ store[k] = String(v); }},
      removeItem: (k) => {{ delete store[k]; }}
    }};
    const dummyEl = {{ style: {{}}, classList: {{ add: () => {{}}, remove: () => {{}}, toggle: () => {{}} }}, addEventListener: () => {{}}, setAttribute: () => {{}}, getAttribute: () => null }};
    global.window = {{ location: {{ search: "" }}, addEventListener: () => {{}} }};
    global.document = {{
      documentElement: dummyEl,
      querySelectorAll: () => [],
      getElementById: (id) => {{
        if (id === 'stackKbData') {{
          return {{ textContent: JSON.stringify({{ meta: {{}}, technologies: [{{ id: 'seed-tech', name: 'Seed Tech', signal_keywords: ['seed'] }}] }}) }};
        }}
        return dummyEl;
      }},
      addEventListener: () => {{}}
    }};
    global.navigator = {{ clipboard: {{}} }};
    global.fetch = () => Promise.resolve({{ ok: false }});

    {script}

    // 1. Initial KB data has only seed
    let kb = getKbData();
    const initialCount = kb.technologies.length;

    // 2. Save a custom tech
    saveCustomKbTech({{
      id: 'custom-corp-sso',
      name: 'Custom Corp SSO',
      domain: 'identity',
      category: 'identity-gateway',
      license: 'Proprietary',
      signal_keywords: ['corp-sso']
    }});

    // 3. Merged KB data contains the custom tech
    kb = getKbData();
    const hasCustom = kb.technologies.some(t => t.id === 'custom-corp-sso');

    console.log(JSON.stringify({{
      initialCount,
      mergedCount: kb.technologies.length,
      hasCustom
    }}));
    """
    proc = subprocess.run(["node", "-e", node_harness], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, f"Node execution failed:\n{proc.stderr}"
    res = json.loads(proc.stdout)
    assert res["initialCount"] == 1
    assert res["mergedCount"] == 2
    assert res["hasCustom"] is True


def test_python_detect_signals_matches_new_keywords():
    from app.rule_engine import detect_signals
    
    sigs1 = detect_signals("We need Dynatrace for APM and SonarQube for static analysis.")
    assert sigs1["dynatraceMentioned"] is True
    assert sigs1["sonarqubeMentioned"] is True
    
    sigs2 = detect_signals("Using Grafana dashboards with Prometheus metrics and JProfiler.")
    assert sigs2["prometheusMentioned"] is True
    assert sigs2["grafanaMentioned"] is True
    assert sigs2["jprofilerMentioned"] is True

    sigs3 = detect_signals("VisualVM and Splunk for error diagnostics.")
    assert sigs3["visualvmMentioned"] is True
    assert sigs3["splunkMentioned"] is True

