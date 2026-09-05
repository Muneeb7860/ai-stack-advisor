"""Deterministic scoring rules.

These are the cheap, reproducible checks. They catch regressions without a model
in the loop, and they run in milliseconds so you can put them in CI.

Weights are deliberate. Recommending something disqualified (R4) and missing a
hard precondition (R3) matter more than picking the second-best database (R5),
because those are the failures that waste an architect's month rather than an
afternoon.
"""

from __future__ import annotations

import re

from evalkit.schema import (CONFIDENCE_WEIGHT, AdvisorOutput, Confidence, EvalCase,
                            RuleResult)

# Weight per rule. Tune these; they encode what you think "wrong" costs.
WEIGHTS = {
    "R1_binding_constraint": 3.0,
    "R2_scope_verdict": 2.0,
    "R3_required_flags": 4.0,
    "R4_no_forbidden": 5.0,
    "R5_domain_acceptable": 3.0,
    "R6_domain_preferred": 1.0,
    "R7_wellformed": 1.0,
    "R8_ruled_out_present": 1.5,
}


def _mentions(haystack: str, needle: str) -> bool:
    """Flag matching: underscored keys are matched as loose word sequences.

    'dlt_registration' matches 'DLT registration', 'DLT-registration', 'registered on DLT'
    is NOT matched -- order matters. Keep flags short and canonical.
    """
    words = [re.escape(w) for w in needle.lower().replace("-", "_").split("_") if w]
    if not words:
        return False
    pattern = r"[\s\-_/]*".join(words)
    return re.search(pattern, haystack) is not None


def score_rules(case: EvalCase, out: AdvisorOutput) -> list[RuleResult]:
    g = case.golden
    text = out.all_text()
    results: list[RuleResult] = []

    # R1 -- did it identify what actually gates the project?
    got = out.binding_constraint
    results.append(RuleResult(
        "R1_binding_constraint",
        passed=got is not None and got == g.binding_constraint,
        weight=WEIGHTS["R1_binding_constraint"],
        detail=f"expected {g.binding_constraint.value}, got {got.value if got else 'None (not emitted)'}",
    ))

    # R2 -- did it know how much of the problem it can actually address?
    gotv = out.scope_verdict
    results.append(RuleResult(
        "R2_scope_verdict",
        passed=gotv is not None and gotv == g.scope_verdict,
        weight=WEIGHTS["R2_scope_verdict"],
        detail=f"expected {g.scope_verdict.value}, got {gotv.value if gotv else 'None (not emitted)'}",
    ))

    # R3 -- recall on things that must be surfaced (preconditions, blockers).
    if g.required_flags:
        missing = [f for f in g.required_flags if not _mentions(text, f)]
        results.append(RuleResult(
            "R3_required_flags",
            passed=not missing,
            weight=WEIGHTS["R3_required_flags"],
            detail=("all present" if not missing else f"missing: {', '.join(missing)}"),
        ))

    # R4 -- precision. Any forbidden recommendation is a hard defect.
    # Matched against the recommendation fields ONLY, never the full text: an
    # advisor that correctly names a bad option in `ruled_out` must not be
    # punished for mentioning it.
    if g.forbidden:
        recs = " | ".join(c.recommendation for c in out.cards)
        hits = [f for f in g.forbidden if _mentions(recs, f)]
        results.append(RuleResult(
            "R4_no_forbidden",
            passed=not hits,
            weight=WEIGHTS["R4_no_forbidden"],
            detail=("clean" if not hits else f"recommended/mentioned forbidden: {', '.join(hits)}"),
        ))

    # R5/R6 -- per-domain choice quality.
    if g.domains:
        by_domain = {c.domain: c for c in out.cards}
        bad, absent, preferred_hits, preferred_total = [], [], 0, 0
        for dom, exp in g.domains.items():
            card = by_domain.get(dom)
            if card is None:
                absent.append(dom)
                continue
            rec = card.recommendation
            if any(_mentions(rec, u) for u in exp.unacceptable):
                bad.append(f"{dom}={rec} (unacceptable)")
            elif exp.acceptable and not any(_mentions(rec, a) for a in exp.acceptable):
                bad.append(f"{dom}={rec} (not in acceptable set)")
            if exp.preferred:
                preferred_total += 1
                if _mentions(rec, exp.preferred):
                    preferred_hits += 1
        problems = bad + [f"{d}=<no card>" for d in absent]
        results.append(RuleResult(
            "R5_domain_acceptable",
            passed=not problems,
            weight=WEIGHTS["R5_domain_acceptable"],
            detail=("all domains acceptable" if not problems else "; ".join(problems)),
        ))
        if preferred_total:
            results.append(RuleResult(
                "R6_domain_preferred",
                passed=preferred_hits == preferred_total,
                weight=WEIGHTS["R6_domain_preferred"],
                detail=f"{preferred_hits}/{preferred_total} matched preferred",
            ))

    # R7 -- structural sanity. An advisor that returns nothing scores nothing.
    wellformed = bool(out.cards) and all(c.domain and c.recommendation for c in out.cards)
    results.append(RuleResult(
        "R7_wellformed", passed=wellformed, weight=WEIGHTS["R7_wellformed"],
        detail="ok" if wellformed else "empty or malformed cards",
    ))

    # R8 -- did it show its work by naming rejected alternatives?
    if g.should_rule_out:
        ruled_text = " ".join(r.lower() for c in out.cards for r in c.ruled_out)
        found = [a for a in g.should_rule_out if _mentions(ruled_text, a)]
        results.append(RuleResult(
            "R8_ruled_out_present",
            passed=len(found) == len(g.should_rule_out),
            weight=WEIGHTS["R8_ruled_out_present"],
            detail=f"named {len(found)}/{len(g.should_rule_out)} expected rejections",
        ))

    return results


def calibration_penalty(rules: list[RuleResult], out: AdvisorOutput) -> float:
    """Penalise confident wrongness.

    The product ships a confidence badge. If that badge is decorative -- High on
    answers that are wrong -- it is worse than no badge, because it transfers
    unearned trust. This metric makes that visible as a number.

    Penalty is proportional to how much of the rule score was missed, scaled by
    how loudly the advisor asserted itself. A Low-confidence miss costs little;
    a High-confidence miss costs the most.
    """
    total = sum(r.weight for r in rules)
    if not total or not out.cards:
        return 0.0
    miss_fraction = 1.0 - (sum(r.earned for r in rules) / total)
    avg_conf = sum(CONFIDENCE_WEIGHT[c.confidence] for c in out.cards) / len(out.cards)
    # Cap at 0.25 so calibration shapes the ranking without swamping correctness.
    return round(min(0.25, miss_fraction * avg_conf * 0.35), 4)


def confidence_calibration_report(rows: list[tuple[Confidence, bool]]) -> dict:
    """Aggregate view: for each confidence level, what fraction was actually right.

    A well-calibrated advisor shows high accuracy at High and lower at Low. A
    flat line means the badge carries no information.
    """
    out = {}
    for level in Confidence:
        subset = [ok for conf, ok in rows if conf is level]
        out[level.value] = {
            "n": len(subset),
            "accuracy": round(sum(subset) / len(subset), 3) if subset else None,
        }
    return out
