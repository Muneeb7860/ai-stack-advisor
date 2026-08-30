"""Integration tests for POST /api/analyses/{analysis_id}/disagreements — the "Challenge This
Pick" widget's backend half (docs/challenge-this-pick-spec.md).

Despite test_ask.py's own module docstring claiming "requires a live Postgres," these tests
(like every other router test in this suite) actually run against tests/conftest.py's
zero-dependency in-memory SQLite override — no docker-compose, no DATABASE_URL needed. No LLM
call exists in this router at all, so unlike test_ask.py/test_refine.py there's no monkeypatch
fixture here — this is plain CRUD.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def existing_analysis():
    created = client.post(
        "/api/analyses",
        json={
            "requirement_text": "Fintech app storing order totals and payment records.",
            "signals": {"finance": True},
            "recommendations": {"database": {"v": "PostgreSQL · MongoDB", "conf": "medium"}},
        },
    )
    return created.json()


def test_create_disagreement_201s_with_the_full_shape():
    analysis = existing_analysis()
    resp = client.post(
        f"/api/analyses/{analysis['id']}/disagreements",
        json={
            "category": "cache",
            "current_pick": "Redis",
            "proposed_alternative": "Redis Streams (self-hosted, no separate service)",
            "reason": "For 20k/sec real-time websocket fan-out, a dedicated pub/sub tier is overkill for our scale.",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["analysis_id"] == analysis["id"]
    assert body["category"] == "cache"
    assert body["current_pick"] == "Redis"
    assert body["proposed_alternative"] == "Redis Streams (self-hosted, no separate service)"
    assert "id" in body and "created_at" in body


def test_create_disagreement_404s_on_unknown_analysis_id():
    resp = client.post(
        "/api/analyses/00000000-0000-0000-0000-000000000000/disagreements",
        json={
            "category": "cloud",
            "current_pick": "AWS",
            "proposed_alternative": "GCP",
            "reason": "Team already runs everything else on GCP.",
        },
    )
    assert resp.status_code == 404


def test_a_second_disagreement_does_not_overwrite_the_first():
    """Append-only, matching RefinementResult's own invariant (models.py) — a disagreement is
    a fact about a moment, not something later edits should be able to erase."""
    analysis = existing_analysis()
    first = client.post(
        f"/api/analyses/{analysis['id']}/disagreements",
        json={
            "category": "cache",
            "current_pick": "Redis",
            "proposed_alternative": "Memcached",
            "reason": "Simpler ops, we don't need Redis's data structures.",
        },
    )
    second = client.post(
        f"/api/analyses/{analysis['id']}/disagreements",
        json={
            "category": "database",
            "current_pick": "PostgreSQL",
            "proposed_alternative": "MySQL",
            "reason": "Existing team expertise is entirely MySQL.",
        },
    )
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


def test_missing_required_field_is_a_422_not_a_500():
    analysis = existing_analysis()
    resp = client.post(
        f"/api/analyses/{analysis['id']}/disagreements",
        json={
            "category": "cache",
            "current_pick": "Redis",
            # proposed_alternative missing
            "reason": "No reason given for the missing field on purpose.",
        },
    )
    assert resp.status_code == 422
