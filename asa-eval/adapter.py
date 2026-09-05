"""THE ONLY FILE YOU NEED TO EDIT TO WIRE THE HARNESS TO YOUR ADVISOR.

Implement `advise()`. Everything else in this package treats the advisor as a
black box, so this survives the backend being rewritten.

Three reference implementations are below:

  * MockAdapter  -- deliberately mediocre, used to smoke-test the harness itself
  * HttpAdapter  -- POSTs the case to a REST endpoint
  * ImportAdapter-- calls your Python advisor directly

Select one with ASA_ADAPTER=mock|http|import (default: mock).
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Protocol

from evalkit.schema import AdvisorOutput, BindingConstraint, CaseInput, Card, Confidence, ScopeVerdict


class Adapter(Protocol):
    def advise(self, case_input: CaseInput) -> AdvisorOutput: ...


# --------------------------------------------------------------------------
# Normalisation helpers -- shared by every adapter
# --------------------------------------------------------------------------

def _conf(value: str | None) -> Confidence:
    v = (value or "medium").strip().lower()
    return {"high": Confidence.HIGH, "medium": Confidence.MEDIUM,
            "low": Confidence.LOW}.get(v, Confidence.MEDIUM)


def _enum(cls, value):
    if value is None:
        return None
    try:
        return cls(str(value).strip().lower())
    except ValueError:
        return None


def parse_advisor_json(payload: dict) -> AdvisorOutput:
    """Map your advisor's JSON onto AdvisorOutput.

    Adjust the key names here if your backend uses different ones. This is the
    single place where the advisor's wire format is known.
    """
    cards = []
    for c in payload.get("cards", []):
        ruled = c.get("ruled_out", [])
        if isinstance(ruled, dict):
            ruled = [f"{k}: {v}" for k, v in ruled.items()]
        cards.append(Card(
            domain=str(c.get("domain", "")).strip().lower(),
            recommendation=str(c.get("recommendation", "")).strip().lower(),
            confidence=_conf(c.get("confidence")),
            reasoning=c.get("reasoning", "") or "",
            preconditions=list(c.get("preconditions", []) or []),
            ruled_out=[str(r) for r in (ruled or [])],
            risks=list(c.get("risks", []) or []),
        ))
    return AdvisorOutput(
        cards=cards,
        binding_constraint=_enum(BindingConstraint, payload.get("binding_constraint")),
        scope_verdict=_enum(ScopeVerdict, payload.get("scope_verdict")),
        constraint_rationale=payload.get("constraint_rationale", "") or "",
        narrative=payload.get("narrative", "") or "",
        raw=payload,
    )


# --------------------------------------------------------------------------
# Adapters
# --------------------------------------------------------------------------

class HttpAdapter:
    """POST {mode, text, answers} -> advisor JSON. Set ASA_ADVISOR_URL."""

    def __init__(self, url: str | None = None, timeout: int = 120):
        self.url = url or os.environ.get("ASA_ADVISOR_URL", "http://localhost:8000/advise")
        self.timeout = timeout

    def advise(self, case_input: CaseInput) -> AdvisorOutput:
        body = json.dumps({
            "mode": case_input.mode,
            "text": case_input.text,
            "answers": case_input.answers,
        }).encode()
        req = urllib.request.Request(
            self.url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return parse_advisor_json(json.loads(resp.read()))


class ImportAdapter:
    """Call the advisor in-process. Set ASA_ADVISOR_IMPORT=pkg.module:callable.

    The callable receives (mode, text, answers) and returns a dict shaped like
    parse_advisor_json expects.
    """

    def __init__(self, target: str | None = None):
        target = target or os.environ.get("ASA_ADVISOR_IMPORT", "")
        if ":" not in target:
            raise ValueError("ASA_ADVISOR_IMPORT must look like 'pkg.module:callable'")
        mod_name, fn_name = target.split(":", 1)
        import importlib
        self.fn = getattr(importlib.import_module(mod_name), fn_name)

    def advise(self, case_input: CaseInput) -> AdvisorOutput:
        payload = self.fn(case_input.mode, case_input.text, case_input.answers)
        return parse_advisor_json(payload)


class MockAdapter:
    """A deliberately mediocre advisor, for testing the harness.

    It behaves the way an unimproved recommender does: always answers with a
    stack, never states a binding constraint, never rules anything out, and is
    confident regardless. Its scores are the floor you are improving from.
    """

    def advise(self, case_input: CaseInput) -> AdvisorOutput:
        text = (case_input.text or " ".join(case_input.answers.values())).lower()
        picks = {
            "backend": "java/spring boot",
            "database": "postgresql",
            "cloud": "aws",
            "llm_strategy": "hosted frontier model via api",
        }
        if "analytic" in text or "warehouse" in text:
            picks["database"] = "snowflake"
        if "on-prem" in text or "air-gap" in text or "sovereign" in text:
            picks["cloud"] = "aws"  # deliberately wrong: ignores the constraint
        cards = [
            Card(domain=d, recommendation=r, confidence=Confidence.HIGH,
                 reasoning=f"{r} is a mature, widely adopted choice for {d}.")
            for d, r in picks.items()
        ]
        return AdvisorOutput(cards=cards, narrative="Recommended stack below.", raw={})


def get_adapter(name: str | None = None) -> Adapter:
    name = (name or os.environ.get("ASA_ADAPTER", "mock")).lower()
    if name == "http":
        return HttpAdapter()
    if name == "import":
        return ImportAdapter()
    if name == "mock":
        return MockAdapter()
    raise ValueError(f"unknown adapter: {name}")
