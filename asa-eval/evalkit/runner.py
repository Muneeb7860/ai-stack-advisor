"""Run the eval set against an advisor and write a report.

    python -m evalkit.runner --adapter mock
    python -m evalkit.runner --adapter http --judge anthropic --tag cpaas
    python -m evalkit.runner --adapter http --baseline runs/2026-09-05-a.json

The last form is the one that matters day to day: it tells you which cases got
worse since the last run. A KB edit that raises the mean while silently breaking
three cases is a regression, and the mean alone will not show you that.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapter import get_adapter  # noqa: E402
from evalkit.judge import judge as run_judge  # noqa: E402
from evalkit.loader import load_cases  # noqa: E402
from evalkit.report import write_reports  # noqa: E402
from evalkit.rules import calibration_penalty, score_rules  # noqa: E402
from evalkit.schema import CaseResult  # noqa: E402


def run(adapter_name: str, cases_dir: str, tag: str | None, judge_backend: str,
        rule_weight: float) -> dict:
    adapter = get_adapter(adapter_name)
    cases = load_cases(cases_dir, tag=tag)
    results: list[CaseResult] = []
    calibration_rows = []

    for case in cases:
        try:
            out = adapter.advise(case.input)
        except Exception as exc:  # noqa: BLE001 -- an advisor crash is a result
            results.append(CaseResult(case_id=case.id, counted=case.counts_toward_score,
                                      error=f"{type(exc).__name__}: {exc}"))
            continue

        rules = score_rules(case, out)
        res = CaseResult(
            case_id=case.id,
            counted=case.counts_toward_score,
            rules=rules,
            judge=run_judge(case, out, judge_backend),
            calibration_penalty=calibration_penalty(rules, out),
        )
        results.append(res)
        passed = res.rule_score >= 0.8
        for card in out.cards:
            calibration_rows.append((card.confidence, passed))

    counted = [r for r in results if r.counted and not r.error]
    draft = [r for r in results if not r.counted and not r.error]

    from evalkit.rules import confidence_calibration_report
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "adapter": adapter_name,
        "judge": judge_backend,
        "rule_weight": rule_weight,
        "n_cases": len(results),
        "n_scored": len(counted),
        "n_draft_excluded": len(draft),
        "n_errors": sum(1 for r in results if r.error),
        "mean_composite": round(statistics.fmean(
            [r.composite(rule_weight) for r in counted]), 4) if counted else None,
        "mean_rule_score": round(statistics.fmean(
            [r.rule_score for r in counted]), 4) if counted else None,
        "mean_judge_score": round(statistics.fmean(
            [r.judge_score for r in counted]), 4) if counted and counted[0].judge else None,
        "calibration": confidence_calibration_report(calibration_rows),
        # Draft scores are computed and shown but excluded from the headline,
        # so you can watch them without letting unreviewed answers move the metric.
        "draft_mean_composite": round(statistics.fmean(
            [r.composite(rule_weight) for r in draft]), 4) if draft else None,
    }
    return {"summary": summary,
            "cases": [dataclasses.asdict(r) | {"composite": round(r.composite(rule_weight), 4),
                                               "rule_score": round(r.rule_score, 4),
                                               "judge_score": round(r.judge_score, 4)}
                      for r in results]}


def compare(current: dict, baseline_path: str) -> list[dict]:
    base = json.loads(Path(baseline_path).read_text())
    base_by_id = {c["case_id"]: c for c in base["cases"]}
    deltas = []
    for c in current["cases"]:
        prev = base_by_id.get(c["case_id"])
        if not prev:
            continue
        delta = round(c["composite"] - prev["composite"], 4)
        if abs(delta) >= 0.01:
            deltas.append({"case_id": c["case_id"], "before": prev["composite"],
                           "after": c["composite"], "delta": delta})
    return sorted(deltas, key=lambda d: d["delta"])


def main() -> int:
    ap = argparse.ArgumentParser(description="AI Stack Advisor eval harness")
    ap.add_argument("--adapter", default="mock", help="mock | http | import")
    ap.add_argument("--cases", default="cases")
    ap.add_argument("--tag", default=None, help="only run cases with this tag")
    ap.add_argument("--judge", default="none", help="none | anthropic | ollama")
    ap.add_argument("--rule-weight", type=float, default=0.7)
    ap.add_argument("--out", default=None, help="path for the JSON run record")
    ap.add_argument("--baseline", default=None, help="prior run JSON to diff against")
    ap.add_argument("--fail-under", type=float, default=None,
                    help="exit non-zero if mean composite falls below this (for CI)")
    ap.add_argument("--fail-on-regression", action="store_true",
                    help="exit non-zero if any case dropped vs --baseline")
    args = ap.parse_args()

    report = run(args.adapter, args.cases, args.tag, args.judge, args.rule_weight)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = Path(args.out or f"runs/{stamp}-{args.adapter}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    regressions = []
    if args.baseline:
        regressions = compare(report, args.baseline)
        report["regressions"] = regressions

    out_path.write_text(json.dumps(report, indent=2))
    write_reports(report, out_path.with_suffix(".md"), args.cases)

    s = report["summary"]
    print(f"scored {s['n_scored']} cases "
          f"({s['n_draft_excluded']} draft excluded, {s['n_errors']} errors)")
    print(f"mean composite: {s['mean_composite']}   rules: {s['mean_rule_score']}"
          + (f"   judge: {s['mean_judge_score']}" if s['mean_judge_score'] is not None else ""))
    print(f"report: {out_path.with_suffix('.md')}")
    if regressions:
        worse = [r for r in regressions if r["delta"] < 0]
        print(f"regressions: {len(worse)} case(s) got worse")
        for r in worse[:10]:
            print(f"  {r['case_id']}: {r['before']} -> {r['after']} ({r['delta']:+})")

    if args.fail_under is not None and (s["mean_composite"] or 0) < args.fail_under:
        return 1
    if args.fail_on_regression and any(r["delta"] < 0 for r in regressions):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
