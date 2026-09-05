"""Constraint classifier — the stage that runs before domain cards.

Drop this into the advisor pipeline ahead of retrieval and card generation:

    from classifier.classifier import classify, apply_to_cards

    verdict = classify(prd_text)
    cards   = generate_cards(prd_text)          # your existing pipeline
    cards   = apply_to_cards(verdict, cards)    # downgrades confidence, adds context
    return {**verdict.to_payload(), "cards": cards}

Deliberately has no dependency on the rest of the advisor. It reads the request and
nothing else -- no retrieval, no KB. It is answering a question about the shape of
the problem, not about technology, and giving it the KB would only tempt it to
reach for a stack.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

VALID_CONSTRAINTS = {"technology", "regulatory", "commercial",
                     "organizational", "data", "product"}
VALID_VERDICTS = {"full", "partial", "wrong_question"}

_SPEC = Path(__file__).with_name("PROMPT.md")


@dataclass
class ConstraintVerdict:
    binding_constraint: str
    scope_verdict: str
    confidence: str = "medium"
    secondary_constraints: list[str] = field(default_factory=list)
    rationale: str = ""
    cannot_determine: list[str] = field(default_factory=list)
    unblocking_questions: list[str] = field(default_factory=list)

    def to_payload(self) -> dict:
        return {
            "binding_constraint": self.binding_constraint,
            "secondary_constraints": self.secondary_constraints,
            "scope_verdict": self.scope_verdict,
            "constraint_confidence": self.confidence,
            "constraint_rationale": self.rationale,
            "cannot_determine": self.cannot_determine,
            "unblocking_questions": self.unblocking_questions,
        }


def _build_prompt(request: str) -> str:
    spec = _SPEC.read_text()
    # Everything from the "## Prompt" heading down is the instruction block; the
    # taxonomy and rules above it are prepended as context.
    body, _, prompt_block = spec.partition("## Prompt")
    instruction = prompt_block.replace(">", "").strip()
    return (f"{body}\n\n---\n\n{instruction}".replace("{request}", request))


def _call_anthropic(prompt: str) -> str:
    key = os.environ["ANTHROPIC_API_KEY"]
    model = os.environ.get("ASA_CLASSIFIER_MODEL", "claude-sonnet-4-5")
    body = json.dumps({"model": model, "max_tokens": 1200,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())["content"][0]["text"]


def _call_ollama(prompt: str) -> str:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    model = os.environ.get("ASA_CLASSIFIER_MODEL", "qwen2.5:14b-instruct")
    body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(f"{host}/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read())["response"]


def classify(request: str, backend: str | None = None) -> ConstraintVerdict:
    backend = (backend or os.environ.get("ASA_CLASSIFIER", "anthropic")).lower()
    raw = _call_anthropic(_build_prompt(request)) if backend == "anthropic" \
        else _call_ollama(_build_prompt(request))
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        raise ValueError(f"classifier returned no JSON: {raw[:200]}")
    data = json.loads(match.group(0))

    constraint = str(data.get("binding_constraint", "")).strip().lower()
    verdict = str(data.get("scope_verdict", "")).strip().lower()
    if constraint not in VALID_CONSTRAINTS:
        raise ValueError(f"invalid binding_constraint: {constraint!r}")
    if verdict not in VALID_VERDICTS:
        raise ValueError(f"invalid scope_verdict: {verdict!r}")

    return ConstraintVerdict(
        binding_constraint=constraint,
        scope_verdict=verdict,
        confidence=str(data.get("confidence", "medium")).strip().lower(),
        secondary_constraints=[str(s).lower() for s in data.get("secondary_constraints", [])
                               if str(s).lower() in VALID_CONSTRAINTS],
        rationale=str(data.get("rationale", "")),
        cannot_determine=[str(x) for x in data.get("cannot_determine", [])],
        unblocking_questions=[str(x) for x in data.get("unblocking_questions", [])],
    )


def apply_to_cards(verdict: ConstraintVerdict, cards: list[dict]) -> list[dict]:
    """Let the verdict shape the cards instead of sitting beside them.

    This is the part that changes behaviour rather than just adding a field. On a
    `wrong_question`, every card is capped at low confidence and labelled, because
    a high-confidence database recommendation on a problem gated by a carrier
    contract is precisely the failure this stage exists to stop.
    """
    order = {"low": 0, "medium": 1, "high": 2}
    cap = {"full": "high", "partial": "medium", "wrong_question": "low"}[verdict.scope_verdict]
    out = []
    for card in cards:
        c = dict(card)
        current = str(c.get("confidence", "medium")).lower()
        if order.get(current, 1) > order[cap]:
            c["confidence"] = cap
            c.setdefault("risks", []).append(
                f"Confidence capped: the binding constraint here is {verdict.binding_constraint}, "
                f"which this recommendation does not address."
            )
        if verdict.scope_verdict == "wrong_question":
            c["impact"] = "low"
        out.append(c)
    return out


if __name__ == "__main__":
    import sys
    text = sys.stdin.read() if not sys.stdin.isatty() else " ".join(sys.argv[1:])
    print(json.dumps(classify(text).to_payload(), indent=2))
