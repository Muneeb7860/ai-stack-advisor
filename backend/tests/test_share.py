"""Integration tests for the share-links milestone. Requires a live Postgres reachable at
DATABASE_URL (docker compose up -d db, or a local Postgres — see README "Running tests").

These hit a real database rather than mocking the ORM — for a scaffold this thin, a mock
would just be re-asserting the mock's own behavior. Keep it this way until the schema/logic
is complex enough that integration tests become slow, not before.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def analysis_payload():
    return {
        "requirement_text": "Test fintech app, SOC2 compliant, small team.",
        "signals": {"finance": True, "compliance": True, "smallTeam": True},
        "recommendations": {"cloud": {"v": "AWS", "conf": "high"}},
    }


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_analysis_has_no_share_slug_yet(analysis_payload):
    resp = client.post("/api/analyses", json=analysis_payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["share_slug"] is None
    assert body["requirement_text"] == analysis_payload["requirement_text"]


def test_share_then_fetch_round_trip(analysis_payload):
    created = client.post("/api/analyses", json=analysis_payload).json()
    share = client.post(f"/api/analyses/{created['id']}/share")
    assert share.status_code == 200
    slug = share.json()["share_slug"]

    fetched = client.get(f"/api/analyses/shared/{slug}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]
    assert fetched.json()["share_slug"] == slug


def test_sharing_is_idempotent_same_slug_twice(analysis_payload):
    """Calling /share twice on the same analysis should return the SAME slug, not mint a
    second one — the ERD/schema only supports one live slug per analysis (unique column)."""
    created = client.post("/api/analyses", json=analysis_payload).json()
    first = client.post(f"/api/analyses/{created['id']}/share").json()
    second = client.post(f"/api/analyses/{created['id']}/share").json()
    assert first["share_slug"] == second["share_slug"]


def test_unknown_slug_is_404():
    resp = client.get("/api/analyses/shared/this-slug-does-not-exist")
    assert resp.status_code == 404


def test_unknown_analysis_id_is_404_on_share():
    resp = client.post("/api/analyses/00000000-0000-0000-0000-000000000000/share")
    assert resp.status_code == 404


def test_mcp_server_still_raises_on_import():
    """The only remaining stub (v2 milestone 4) — app/mcp/server.py raises NotImplementedError
    at import time, deliberately (see its module docstring). This is the tripwire for it: if
    someone accidentally makes the module importable without actually building it, this test
    fails loudly instead of the stub silently looking done. Both /api/refine and /api/ask are
    now real — see tests/test_refine.py and tests/test_ask.py."""
    with pytest.raises(NotImplementedError):
        import app.mcp.server  # noqa: F401
