"""Render a run into a readable markdown report."""

from __future__ import annotations

from pathlib import Path

from evalkit.loader import load_cases


def write_reports(report: dict, md_path: Path, cases_dir: str) -> None:
    s = report["summary"]
    titles = {c.id: c.title for c in load_cases(cases_dir)}
    status = {c.id: c.golden.status.value for c in load_cases(cases_dir)}

    lines = [
        "# AI Stack Advisor — eval run",
        "",
        f"**Generated:** {s['generated_at']} · **Adapter:** `{s['adapter']}` · "
        f"**Judge:** `{s['judge']}`",
        "",
        "## Headline",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Mean composite (reviewed cases only) | **{s['mean_composite']}** |",
        f"| Mean rule score | {s['mean_rule_score']} |",
        f"| Mean judge score | {s['mean_judge_score'] if s['mean_judge_score'] is not None else '—'} |",
        f"| Cases scored | {s['n_scored']} |",
        f"| Draft cases excluded | {s['n_draft_excluded']} |",
        f"| Advisor errors | {s['n_errors']} |",
        f"| Draft-only mean (not counted) | {s['draft_mean_composite'] if s['draft_mean_composite'] is not None else '—'} |",
        "",
    ]

    cal = s.get("calibration") or {}
    if any(v.get("n") for v in cal.values()):
        lines += [
            "## Confidence calibration",
            "",
            "A useful confidence badge shows high accuracy at High and lower at Low. "
            "A flat row means the badge carries no information.",
            "",
            "| Stated confidence | Cards | Accuracy |",
            "|---|---|---|",
        ]
        for level in ("high", "medium", "low"):
            row = cal.get(level, {})
            acc = row.get("accuracy")
            lines.append(f"| {level} | {row.get('n', 0)} | {acc if acc is not None else '—'} |")
        lines.append("")

    if report.get("regressions"):
        worse = [r for r in report["regressions"] if r["delta"] < 0]
        better = [r for r in report["regressions"] if r["delta"] > 0]
        lines += ["## Change vs baseline", ""]
        if worse:
            lines += ["**Regressions**", "", "| Case | Before | After | Δ |", "|---|---|---|---|"]
            lines += [f"| `{r['case_id']}` | {r['before']} | {r['after']} | {r['delta']:+} |"
                      for r in worse]
            lines.append("")
        if better:
            lines += ["**Improvements**", "", "| Case | Before | After | Δ |", "|---|---|---|---|"]
            lines += [f"| `{r['case_id']}` | {r['before']} | {r['after']} | {r['delta']:+} |"
                      for r in better]
            lines.append("")

    lines += ["## Per-case", ""]
    ordered = sorted(report["cases"], key=lambda c: c["composite"])
    for c in ordered:
        cid = c["case_id"]
        badge = "" if status.get(cid) == "REVIEWED" else " _(DRAFT — not scored)_"
        lines.append(f"### `{cid}` — {titles.get(cid, '')}{badge}")
        lines.append("")
        if c.get("error"):
            lines += [f"**ADVISOR ERROR:** {c['error']}", ""]
            continue
        lines.append(f"composite **{c['composite']}** · rules {c['rule_score']} · "
                     f"judge {c['judge_score']} · calibration penalty −{c['calibration_penalty']}")
        lines += ["", "| Rule | Result | Detail |", "|---|---|---|"]
        for r in c["rules"]:
            mark = "pass" if r["passed"] else "**FAIL**"
            lines.append(f"| {r['name']} | {mark} | {r['detail']} |")
        if c["judge"]:
            lines += ["", "| Judge dimension | Score | Note |", "|---|---|---|"]
            for j in c["judge"]:
                lines.append(f"| {j['dimension']} | {j['score']}/5 | {j['justification']} |")
        lines.append("")

    md_path.write_text("\n".join(lines))
