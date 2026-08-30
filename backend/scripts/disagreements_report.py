"""Aggregate "disagreements" report — the read-only local report scoped in
docs/aggregate-disagreements-dashboard-spec.md (Option 1: no new network endpoint, no auth
surface, no admin page — this script IS the dashboard for now).

BRD Section 7 defines "disagreement rate" as a success metric, and until this script existed
the only documented way to look at it was "query the disagreements table manually"
(docs/gtm-beta-outreach-plan.md, Weeks 4-6). This makes that query reusable and correct instead
of ad hoc and re-derived by hand each time.

Deliberately excluded (see the spec's "Explicitly not in v1" section — don't add these here
without updating the spec first): no segment breakdown (no segment field exists anywhere in the
data model today), no charts/HTML, no auth, no scheduled run, no write path of any kind.

Usage (from backend/):
    python -m scripts.disagreements_report
    python -m scripts.disagreements_report --since 2026-08-01
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models
from app.db import SessionLocal

TOP_ALTERNATIVES_PER_CATEGORY = 3


def build_report(db: Session, since: datetime | None = None) -> dict:
    """Pure query/aggregation logic, factored out of main() so it's testable without shelling
    out to the script. Never writes to the database.
    """
    disagreement_query = db.query(models.Disagreement)
    if since is not None:
        disagreement_query = disagreement_query.filter(models.Disagreement.created_at >= since)
    disagreements = disagreement_query.all()

    total_analyses = db.query(models.Analysis).count()
    distinct_analysis_ids = {d.analysis_id for d in disagreements}

    category_counts: dict[str, int] = defaultdict(int)
    alternative_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    reasons_by_category: dict[str, list[dict]] = defaultdict(list)

    for d in disagreements:
        category_counts[d.category] += 1
        alternative_counts[d.category][d.proposed_alternative] += 1
        reasons_by_category[d.category].append(
            {
                "reason": d.reason,
                "current_pick": d.current_pick,
                "proposed_alternative": d.proposed_alternative,
                "created_at": d.created_at,
            }
        )

    by_category = [
        {"category": category, "count": count}
        for category, count in sorted(category_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    top_alternatives_by_category = {
        category: [
            {"alternative": alt, "count": count}
            for alt, count in sorted(alts.items(), key=lambda kv: (-kv[1], kv[0]))[
                :TOP_ALTERNATIVES_PER_CATEGORY
            ]
        ]
        for category, alts in alternative_counts.items()
    }

    for category, entries in reasons_by_category.items():
        entries.sort(key=lambda e: e["created_at"], reverse=True)

    return {
        "total_disagreements": len(disagreements),
        "distinct_analyses_with_disagreement": len(distinct_analysis_ids),
        "total_analyses": total_analyses,
        "disagreement_rate": (
            len(distinct_analysis_ids) / total_analyses if total_analyses > 0 else None
        ),
        "by_category": by_category,
        "top_alternatives_by_category": top_alternatives_by_category,
        "reasons_by_category": dict(reasons_by_category),
    }


def format_report(report: dict) -> str:
    """Turns build_report()'s structured data into plain stdout text. No HTML, no charts —
    per the spec, this is a report you read, not a page you browse.
    """
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("DISAGREEMENTS REPORT")
    lines.append("=" * 60)

    rate = report["disagreement_rate"]
    rate_str = f"{rate:.1%}" if rate is not None else "n/a (no analyses recorded)"
    lines.append(f"Total disagreements:                 {report['total_disagreements']}")
    lines.append(
        f"Analyses with >=1 disagreement:       "
        f"{report['distinct_analyses_with_disagreement']} / {report['total_analyses']}"
    )
    lines.append(f"Disagreement rate:                    {rate_str}")
    lines.append("")

    lines.append("-" * 60)
    lines.append("BY CATEGORY")
    lines.append("-" * 60)
    if not report["by_category"]:
        lines.append("(none)")
    for row in report["by_category"]:
        lines.append(f"  {row['category']:<28} {row['count']}")
    lines.append("")

    lines.append("-" * 60)
    lines.append("TOP PROPOSED ALTERNATIVES BY CATEGORY")
    lines.append("-" * 60)
    if not report["top_alternatives_by_category"]:
        lines.append("(none)")
    for category, alts in report["top_alternatives_by_category"].items():
        lines.append(f"  {category}:")
        for alt in alts:
            lines.append(f"    - {alt['alternative']} ({alt['count']})")
    lines.append("")

    lines.append("-" * 60)
    lines.append("REASONS (most recent first, grouped by category)")
    lines.append("-" * 60)
    if not report["reasons_by_category"]:
        lines.append("(none)")
    for category, entries in report["reasons_by_category"].items():
        lines.append(f"  {category}:")
        for entry in entries:
            lines.append(
                f"    [{entry['created_at']}] {entry['current_pick']} -> "
                f"{entry['proposed_alternative']}"
            )
            lines.append(f"      \"{entry['reason']}\"")
    lines.append("=" * 60)

    return "\n".join(lines)


def _parse_since(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since",
        type=_parse_since,
        default=None,
        help="Only include disagreements created on/after this ISO date (e.g. 2026-08-01). "
        "Defaults to all-time.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = build_report(db, since=args.since)
    finally:
        db.close()

    print(format_report(report))


if __name__ == "__main__":
    main()
