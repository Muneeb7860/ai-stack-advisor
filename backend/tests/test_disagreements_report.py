"""Unit tests for scripts/disagreements_report.py — the read-only aggregate report scoped in
docs/aggregate-disagreements-dashboard-spec.md (Option 1: no network endpoint, no auth surface).

Uses the same in-memory SQLite fixture every other test file in this suite relies on
(tests/conftest.py's autouse setup_test_db) — no Postgres needed. Seeds rows directly via
app.db.SessionLocal (already rebound to the test engine by conftest) rather than going through
any HTTP endpoint, since build_report() takes a plain SQLAlchemy Session and this script has no
endpoint of its own to test through.
"""
from datetime import datetime, timedelta, timezone

from app import models
from app.db import SessionLocal
from scripts.disagreements_report import build_report, format_report


def make_analysis(db, requirement_text="Some requirement"):
    analysis = models.Analysis(
        requirement_text=requirement_text,
        signals={},
        recommendations={},
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


def make_disagreement(db, analysis, category, current_pick, proposed_alternative, reason, created_at):
    row = models.Disagreement(
        analysis_id=analysis.id,
        category=category,
        current_pick=current_pick,
        proposed_alternative=proposed_alternative,
        reason=reason,
        created_at=created_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_empty_db_returns_zero_counts_and_none_rate():
    db = SessionLocal()
    try:
        report = build_report(db)
    finally:
        db.close()

    assert report["total_disagreements"] == 0
    assert report["distinct_analyses_with_disagreement"] == 0
    assert report["total_analyses"] == 0
    assert report["disagreement_rate"] is None
    assert report["by_category"] == []
    assert report["top_alternatives_by_category"] == {}
    assert report["reasons_by_category"] == {}


def test_disagreement_rate_counts_distinct_analyses_not_raw_rows():
    """Two disagreements on the SAME analysis must count as 1 analysis-with-disagreement, not 2
    — the rate is "% of sessions where a user disagreed," not "disagreements per analysis."
    """
    db = SessionLocal()
    try:
        a1 = make_analysis(db)
        a2 = make_analysis(db)
        make_analysis(db)  # a3 — no disagreement at all
        now = datetime.now(timezone.utc)
        make_disagreement(db, a1, "cache", "Redis", "Memcached", "simpler ops", now)
        make_disagreement(db, a1, "database", "PostgreSQL", "MySQL", "team expertise", now)
        make_disagreement(db, a2, "cloud", "AWS", "GCP", "existing infra", now)

        report = build_report(db)
    finally:
        db.close()

    assert report["total_disagreements"] == 3
    assert report["distinct_analyses_with_disagreement"] == 2
    assert report["total_analyses"] == 3
    assert report["disagreement_rate"] == 2 / 3


def test_by_category_sorted_by_count_descending_then_alphabetically():
    db = SessionLocal()
    try:
        a = make_analysis(db)
        now = datetime.now(timezone.utc)
        # "database" gets 2, "cache" gets 2 (tie -> alphabetical), "cloud" gets 1
        make_disagreement(db, a, "database", "PostgreSQL", "MySQL", "r1", now)
        make_disagreement(db, a, "database", "PostgreSQL", "MongoDB", "r2", now)
        make_disagreement(db, a, "cache", "Redis", "Memcached", "r3", now)
        make_disagreement(db, a, "cache", "Redis", "Valkey", "r4", now)
        make_disagreement(db, a, "cloud", "AWS", "GCP", "r5", now)

        report = build_report(db)
    finally:
        db.close()

    assert report["by_category"] == [
        {"category": "cache", "count": 2},
        {"category": "database", "count": 2},
        {"category": "cloud", "count": 1},
    ]


def test_top_alternatives_capped_at_three_and_sorted_by_count():
    db = SessionLocal()
    try:
        a = make_analysis(db)
        now = datetime.now(timezone.utc)
        # "MySQL" x3, "MongoDB" x2, "SQLite" x1, "CockroachDB" x1 -> top 3 only
        for alt, times in [("MySQL", 3), ("MongoDB", 2), ("SQLite", 1), ("CockroachDB", 1)]:
            for _ in range(times):
                make_disagreement(db, a, "database", "PostgreSQL", alt, "reason", now)

        report = build_report(db)
    finally:
        db.close()

    top = report["top_alternatives_by_category"]["database"]
    assert len(top) == 3
    assert top[0] == {"alternative": "MySQL", "count": 3}
    assert top[1] == {"alternative": "MongoDB", "count": 2}
    # third slot is a count-1 tie broken alphabetically: "CockroachDB" < "SQLite"
    assert top[2] == {"alternative": "CockroachDB", "count": 1}


def test_reasons_sorted_most_recent_first_within_category():
    db = SessionLocal()
    try:
        a = make_analysis(db)
        base = datetime.now(timezone.utc)
        make_disagreement(db, a, "cache", "Redis", "Memcached", "oldest", base - timedelta(days=2))
        make_disagreement(db, a, "cache", "Redis", "Valkey", "newest", base)
        make_disagreement(db, a, "cache", "Redis", "KeyDB", "middle", base - timedelta(days=1))

        report = build_report(db)
    finally:
        db.close()

    reasons = [entry["reason"] for entry in report["reasons_by_category"]["cache"]]
    assert reasons == ["newest", "middle", "oldest"]


def test_since_filter_excludes_older_rows():
    db = SessionLocal()
    try:
        a = make_analysis(db)
        cutoff = datetime(2026, 8, 1, tzinfo=timezone.utc)
        make_disagreement(db, a, "cache", "Redis", "Memcached", "before cutoff", cutoff - timedelta(days=5))
        make_disagreement(db, a, "cache", "Redis", "Valkey", "after cutoff", cutoff + timedelta(days=5))

        report = build_report(db, since=cutoff)
    finally:
        db.close()

    assert report["total_disagreements"] == 1
    assert report["reasons_by_category"]["cache"][0]["reason"] == "after cutoff"


def test_since_filter_does_not_affect_total_analyses_denominator():
    """total_analyses is the whole-product denominator for the rate — it must not shrink just
    because a --since window was applied to the disagreements themselves."""
    db = SessionLocal()
    try:
        make_analysis(db)
        a2 = make_analysis(db)
        cutoff = datetime(2026, 8, 1, tzinfo=timezone.utc)
        make_disagreement(db, a2, "cache", "Redis", "Valkey", "recent", cutoff + timedelta(days=1))

        report = build_report(db, since=cutoff)
    finally:
        db.close()

    assert report["total_analyses"] == 2


def test_format_report_renders_empty_report_without_crashing():
    db = SessionLocal()
    try:
        report = build_report(db)
    finally:
        db.close()
    text = format_report(report)
    assert "DISAGREEMENTS REPORT" in text
    assert "n/a (no analyses recorded)" in text


def test_format_report_includes_category_counts_and_reason_text():
    db = SessionLocal()
    try:
        a = make_analysis(db)
        make_disagreement(
            db, a, "cache", "Redis", "Memcached", "simpler ops for our scale", datetime.now(timezone.utc)
        )
        report = build_report(db)
    finally:
        db.close()

    text = format_report(report)
    assert "cache" in text
    assert "Memcached" in text
    assert "simpler ops for our scale" in text
