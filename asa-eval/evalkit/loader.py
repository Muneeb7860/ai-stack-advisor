"""Load and validate YAML case files."""

from __future__ import annotations

from pathlib import Path

import yaml

from evalkit.schema import (BindingConstraint, CaseInput, DomainExpectation, EvalCase,
                            Golden, GoldenStatus, ScopeVerdict)


def load_case(path: Path) -> EvalCase:
    data = yaml.safe_load(path.read_text())
    g = data["golden"]
    domains = {
        name: DomainExpectation(
            acceptable=spec.get("acceptable", []) or [],
            preferred=spec.get("preferred"),
            unacceptable=spec.get("unacceptable", []) or [],
            required_because=spec.get("required_because"),
        )
        for name, spec in (g.get("domains") or {}).items()
    }
    golden = Golden(
        status=GoldenStatus(g["status"]),
        binding_constraint=BindingConstraint(g["binding_constraint"]),
        scope_verdict=ScopeVerdict(g["scope_verdict"]),
        required_flags=g.get("required_flags", []) or [],
        forbidden=g.get("forbidden", []) or [],
        domains=domains,
        reasoning_rubric=g.get("reasoning_rubric", "") or "",
        should_rule_out=g.get("should_rule_out", []) or [],
        reviewer=g.get("reviewer"),
        reviewed_at=g.get("reviewed_at"),
        notes=g.get("notes"),
    )
    i = data["input"]
    return EvalCase(
        id=data["id"], title=data["title"], tags=data.get("tags", []) or [],
        input=CaseInput(mode=i["mode"], text=i.get("text"), answers=i.get("answers", {}) or {}),
        golden=golden,
    )


def load_cases(directory: str | Path = "cases", tag: str | None = None,
               include_draft: bool = True) -> list[EvalCase]:
    cases = [load_case(p) for p in sorted(Path(directory).glob("*.yaml"))]
    if tag:
        cases = [c for c in cases if tag in c.tags]
    if not include_draft:
        cases = [c for c in cases if c.counts_toward_score]
    return cases
