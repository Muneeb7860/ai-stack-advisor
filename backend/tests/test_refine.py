"""Integration tests for POST /api/refine (v2 milestone 2). Requires a live Postgres reachable
at DATABASE_URL, same as test_share.py.

The Anthropic call itself is monkeypatched via app.routers.refine._run_refinement — these
tests exercise this endpoint's own logic (analysis creation/reuse, persistence, response
shape, error handling), not Anthropic's API or network reliability. No real API key is used
or needed to run this file.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import refine as refine_module

client = TestClient(app)

FAKE_REFINEMENT_RESULT = {
    "adjusted_picks": [
        {
            "category": "database",
            "pick": "PostgreSQL only",
            "reason": "Requirement text mentions only transactional order data.",
        }
    ],
    "rationale": "Mongo wasn't justified given the requirement only describes transactional data.",
    "open_questions": ["Do you expect any unstructured data alongside orders?"],
}


@pytest.fixture
def mock_anthropic(monkeypatch):
    """Replaces the real Anthropic call with a canned result and records what it was called
    with, so tests can assert on both behavior and the exact inputs sent to the model."""
    calls = []

    def _fake_run_refinement(api_key, requirement_text, recommendations):
        calls.append(
            {"api_key": api_key, "requirement_text": requirement_text, "recommendations": recommendations}
        )
        return FAKE_REFINEMENT_RESULT

    monkeypatch.setattr(refine_module, "_run_refinement", _fake_run_refinement)
    return calls


@pytest.fixture
def refine_payload():
    return {
        "requirement_text": "Fintech app storing order totals and payment records.",
        "recommendations": {"database": {"v": "PostgreSQL · MongoDB", "conf": "medium"}},
        "anthropic_api_key": "sk-ant-fake-key-not-real",
    }


def test_refine_without_analysis_id_creates_a_new_analysis(mock_anthropic, refine_payload):
    resp = client.post("/api/refine", json=refine_payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["analysis_id"]
    assert body["original_recommendations"] == refine_payload["recommendations"]
    # response adds changed_from_tier1 (always True here — schemas.AdjustedPick's default,
    # since adjusted_picks by construction only ever lists categories that changed).
    assert len(body["adjusted_picks"]) == len(FAKE_REFINEMENT_RESULT["adjusted_picks"])
    for actual, expected in zip(body["adjusted_picks"], FAKE_REFINEMENT_RESULT["adjusted_picks"]):
        assert actual["category"] == expected["category"]
        assert actual["pick"] == expected["pick"]
        assert actual["reason"] == expected["reason"]
        assert actual["changed_from_tier1"] is True
    assert body["rationale"] == FAKE_REFINEMENT_RESULT["rationale"]
    assert body["open_questions"] == FAKE_REFINEMENT_RESULT["open_questions"]
    assert body["llm_model_used"] == refine_module.MODEL

    # The Analysis really was persisted, not just echoed back.
    fetched = client.post(f"/api/analyses/{body['analysis_id']}/share")
    assert fetched.status_code == 200


def test_refine_passes_the_right_inputs_to_the_model(mock_anthropic, refine_payload):
    client.post("/api/refine", json=refine_payload)
    assert len(mock_anthropic) == 1
    call = mock_anthropic[0]
    assert call["api_key"] == refine_payload["anthropic_api_key"]
    assert call["requirement_text"] == refine_payload["requirement_text"]
    assert call["recommendations"] == refine_payload["recommendations"]


def test_refine_never_returns_the_api_key(mock_anthropic, refine_payload):
    resp = client.post("/api/refine", json=refine_payload)
    assert refine_payload["anthropic_api_key"] not in resp.text


def test_refine_with_existing_analysis_id_reuses_it(mock_anthropic, refine_payload):
    created = client.post(
        "/api/analyses",
        json={
            "requirement_text": refine_payload["requirement_text"],
            "signals": {"finance": True},
            "recommendations": refine_payload["recommendations"],
        },
    ).json()

    resp = client.post(
        "/api/refine", json={**refine_payload, "analysis_id": created["id"]}
    )
    assert resp.status_code == 200
    assert resp.json()["analysis_id"] == created["id"]


def test_refine_404s_on_unknown_analysis_id(mock_anthropic, refine_payload):
    resp = client.post(
        "/api/refine",
        json={**refine_payload, "analysis_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


def test_refine_persists_an_append_only_refinement_result(mock_anthropic, refine_payload):
    """Calling /api/refine twice on the same analysis must produce TWO RefinementResult rows,
    never an update of the first — DDD 4.2's append-only invariant, load-bearing for the
    'disagreement rate' success metric (BRD Section 7)."""
    created_id = client.post("/api/refine", json=refine_payload).json()["analysis_id"]
    client.post("/api/refine", json={**refine_payload, "analysis_id": created_id})

    from app.db import SessionLocal
    from app import models

    db = SessionLocal()
    try:
        rows = db.query(models.RefinementResult).filter_by(analysis_id=created_id).all()
        assert len(rows) == 2
    finally:
        db.close()


def test_refine_rejects_overlong_requirement_text(mock_anthropic, refine_payload):
    resp = client.post(
        "/api/refine", json={**refine_payload, "requirement_text": "x" * 10_001}
    )
    assert resp.status_code == 422


def test_refine_surfaces_anthropic_api_errors_as_502(monkeypatch, refine_payload):
    from fastapi import HTTPException

    def _raise(*args, **kwargs):
        raise HTTPException(status_code=502, detail="Anthropic API error: simulated failure")

    monkeypatch.setattr(refine_module, "_run_refinement", _raise)
    resp = client.post("/api/refine", json=refine_payload)
    assert resp.status_code == 502


def test_build_grounding_context_returns_citable_content_for_covered_domain():
    """RAG grounding (KICKOFF_BRIEF.md decision #6) — a requirement squarely in one of the 11
    knowledge-base domains should produce non-empty, citable grounding context. Uses eval case
    1's exact query (docs/use-case-knowledge-base/eval_cases.json) — a verified direct hit in
    tests/test_retrieval_eval.py — rather than a hand-written query that might land near the
    threshold boundary for reasons unrelated to what this test is actually checking."""
    grounding = refine_module._build_grounding_context(
        "We're building a Figma-like design tool where multiple people edit the same canvas at once."
    )
    assert grounding != ""
    assert "01-realtime-collaborative-editing.md" in grounding
    # Never a Signals/triggers chunk — see app/retrieval.py's module docstring.
    from app.retrieval import ROUTING_HEADER_PATTERN

    citation_lines = [line for line in grounding.splitlines() if line.startswith("[")]
    assert citation_lines, "expected at least one bracketed citation line"
    for line in citation_lines:
        assert not ROUTING_HEADER_PATTERN.search(line)


def test_build_grounding_context_empty_for_zero_overlap_query():
    """Best-effort, not a hard gate (module docstring) — GROUNDING_SCORE_THRESHOLD is
    deliberately low (0.03, see refine.py's constant comment for the full empirical
    reasoning), so this only filters TRUE zero-lexical-overlap queries, not merely
    off-topic-but-still-technical-sounding ones (those can legitimately score 0.03-0.14 and
    are an accepted, disclosed trade-off — not something this test asserts against)."""
    grounding = refine_module._build_grounding_context("Tell me a joke about cats.")
    assert grounding == ""


def test_refine_still_works_when_grounding_is_empty(mock_anthropic, refine_payload):
    """Grounding must never gate the core refine flow — confirm refine still succeeds end to
    end for a requirement with no knowledge-base match at all."""
    resp = client.post(
        "/api/refine",
        json={**refine_payload, "requirement_text": "Configure DNS for our custom domain."},
    )
    assert resp.status_code == 200
