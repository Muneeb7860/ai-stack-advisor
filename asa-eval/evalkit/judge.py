"""LLM judge for the qualities rules cannot see.

Scope discipline matters here. The judge does NOT decide whether the answer is
correct -- the rules already did that against a human-reviewed golden. The judge
only rates the *quality of the reasoning* on four dimensions, which is where
silent degradation shows up first and where string matching is useless.

Two backends: Anthropic API, or a local Ollama model (matching the advisor's own
local-inference setup). Ollama keeps the harness runnable with no API spend, at
the cost of a noisier judge -- fine for CI trend lines, less good for absolute
scores. Judge scores are reported separately from rule scores for exactly this
reason: never let a drifting judge silently move your headline number.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request

from evalkit.schema import AdvisorOutput, EvalCase, JudgeResult

DIMENSIONS = {
    "grounding": "Is each recommendation justified by something in the request, rather than generic praise for a popular technology?",
    "tradeoffs": "Does it name real trade-offs and the cost of being wrong, rather than only upside?",
    "alternatives": "Does it show what it considered and rejected, with reasons?",
    "honesty": "Does it admit what it cannot determine, flag preconditions it cannot verify, and avoid overstating certainty?",
}

PROMPT = """You are grading an architecture advisor's output. You are NOT deciding \
whether its recommendations are correct -- that has already been scored separately \
against a reviewed reference answer. Grade ONLY the quality of its reasoning.

## The request given to the advisor
{request}

## What a good answer should explain (rubric from the reference answer)
{rubric}

## The advisor's output
{output}

## Your task
Score each dimension from 1 to 5.
1 = absent. 2 = gestured at. 3 = present but shallow. 4 = solid. 5 = would survive \
review by a senior architect.

Be strict. Generic statements that would apply to any project score 2 or below. \
Confident prose with no supporting specifics is not evidence of good reasoning.

Dimensions:
{dimensions}

Return ONLY a JSON object, no prose:
{{"grounding": {{"score": int, "justification": str}}, ...}}
"""


def _render(case: EvalCase, out: AdvisorOutput) -> str:
    req = case.input.text or json.dumps(case.input.answers, indent=2)
    body = []
    if out.binding_constraint:
        body.append(f"Binding constraint: {out.binding_constraint.value}")
    if out.scope_verdict:
        body.append(f"Scope verdict: {out.scope_verdict.value}")
    if out.constraint_rationale:
        body.append(f"Rationale: {out.constraint_rationale}")
    if out.narrative:
        body.append(out.narrative)
    for c in out.cards:
        body.append(
            f"\n[{c.domain}] -> {c.recommendation} (confidence: {c.confidence.value})"
            f"\n  reasoning: {c.reasoning}"
            f"\n  preconditions: {'; '.join(c.preconditions) or 'none stated'}"
            f"\n  ruled out: {'; '.join(c.ruled_out) or 'none stated'}"
            f"\n  risks: {'; '.join(c.risks) or 'none stated'}"
        )
    dims = "\n".join(f"- {k}: {v}" for k, v in DIMENSIONS.items())
    return PROMPT.format(request=req, rubric=case.golden.reasoning_rubric or "(none supplied)",
                         output="\n".join(body) or "(empty)", dimensions=dims)


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError(f"judge returned no JSON: {text[:200]}")
    return json.loads(match.group(0))


def _call_anthropic(prompt: str) -> str:
    key = os.environ["ANTHROPIC_API_KEY"]
    model = os.environ.get("ASA_JUDGE_MODEL", "claude-sonnet-4-5")
    body = json.dumps({
        "model": model, "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body,
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read())["content"][0]["text"]


def _call_ollama(prompt: str) -> str:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    model = os.environ.get("ASA_JUDGE_MODEL", "qwen2.5:14b-instruct")
    body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(f"{host}/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read())["response"]


def judge(case: EvalCase, out: AdvisorOutput,
          backend: str | None = None) -> list[JudgeResult]:
    backend = (backend or os.environ.get("ASA_JUDGE", "none")).lower()
    if backend == "none":
        return []
    prompt = _render(case, out)
    raw = _call_anthropic(prompt) if backend == "anthropic" else _call_ollama(prompt)
    parsed = _extract_json(raw)
    results = []
    for dim in DIMENSIONS:
        entry = parsed.get(dim) or {}
        score = int(entry.get("score", 1))
        results.append(JudgeResult(
            dimension=dim,
            score=max(1, min(5, score)),
            justification=str(entry.get("justification", ""))[:400],
        ))
    return results
