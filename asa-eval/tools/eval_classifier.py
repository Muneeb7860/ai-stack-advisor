"""Score the constraint classifier alone, without running the whole advisor.

This is the fast loop for iterating on classifier/PROMPT.md. It touches no
retrieval and generates no cards, so a prompt change can be measured in under a
minute instead of a full advisor run.

    python tools/eval_classifier.py --backend anthropic
    python tools/eval_classifier.py --backend ollama --cases cases

Reports a confusion matrix over the six constraints plus scope-verdict accuracy.
Watch the wrong_question row: an advisor that never returns it has not learned to
say no, which is the capability this stage exists to add.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classifier.classifier import VALID_CONSTRAINTS, classify  # noqa: E402
from evalkit.loader import load_cases  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="anthropic")
    ap.add_argument("--cases", default="cases")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cases = load_cases(args.cases)
    confusion: dict[str, Counter] = defaultdict(Counter)
    verdict_hits = 0
    rows = []

    for case in cases:
        request = case.input.text or json.dumps(case.input.answers)
        expected_c = case.golden.binding_constraint.value
        expected_v = case.golden.scope_verdict.value
        try:
            v = classify(request, backend=args.backend)
            got_c, got_v = v.binding_constraint, v.scope_verdict
            rationale = v.rationale
        except Exception as exc:  # noqa: BLE001
            got_c, got_v, rationale = "ERROR", "ERROR", f"{type(exc).__name__}: {exc}"
        confusion[expected_c][got_c] += 1
        verdict_hits += int(got_v == expected_v)
        rows.append({"case": case.id, "expected_constraint": expected_c,
                     "got_constraint": got_c, "expected_verdict": expected_v,
                     "got_verdict": got_v, "rationale": rationale})
        mark = "ok " if got_c == expected_c else "MISS"
        print(f"{mark} {case.id:32s} {expected_c:15s} -> {got_c:15s} | "
              f"{expected_v:14s} -> {got_v}")

    total = len(cases)
    c_hits = sum(confusion[k][k] for k in confusion)
    print(f"\nconstraint accuracy: {c_hits}/{total} = {c_hits / total:.2%}")
    print(f"verdict accuracy:    {verdict_hits}/{total} = {verdict_hits / total:.2%}")

    labels = sorted(VALID_CONSTRAINTS)
    print("\nconfusion (rows = expected, cols = predicted)")
    print(" " * 16 + "".join(f"{l[:6]:>8s}" for l in labels))
    for exp in labels:
        if not confusion.get(exp):
            continue
        print(f"{exp:16s}" + "".join(f"{confusion[exp][got]:>8d}" for got in labels))

    if args.out:
        Path(args.out).write_text(json.dumps(
            {"constraint_accuracy": c_hits / total,
             "verdict_accuracy": verdict_hits / total, "rows": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
