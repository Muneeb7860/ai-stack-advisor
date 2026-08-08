"""Integration tests for POST /api/ask (v2 milestone 3). Requires a live Postgres reachable
at DATABASE_URL, same as test_share.py / test_refine.py.

The Anthropic call is monkeypatched via app.routers.ask._run_ask — these tests exercise this
endpoint's own logic (analysis scoping, conversation history assembly/persistence, error
handling), not Anthropic's API or network reliability. No real API key is used or needed.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import ask as ask_module

client = TestClient(app)


@pytest.fixture
def mock_ask(monkeypatch):
    """Replaces the real Anthropic call with a canned answer and records what it was called
    with (system prompt + full message history), so tests can assert on both behavior and
    exactly what context was sent to the model."""
    calls = []

    def _fake_run_ask(api_key, system_prompt, history):
        calls.append({"api_key": api_key, "system_prompt": system_prompt, "history": history})
        return f"Canned answer #{len(calls)}"

    monkeypatch.setattr(ask_module, "_run_ask", _fake_run_ask)
    return calls


@pytest.fixture
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


def test_ask_404s_on_unknown_analysis_id(mock_ask):
    resp = client.post(
        "/api/ask",
        json={
            "analysis_id": str(uuid.uuid4()),
            "question": "Why Postgres over Mongo here?",
            "anthropic_api_key": "sk-ant-fake-key-not-real",
        },
    )
    assert resp.status_code == 404


def test_ask_grounds_the_system_prompt_in_the_analysis(mock_ask, existing_analysis):
    resp = client.post(
        "/api/ask",
        json={
            "analysis_id": existing_analysis["id"],
            "question": "Why Postgres over Mongo here?",
            "anthropic_api_key": "sk-ant-fake-key-not-real",
        },
    )
    assert resp.status_code == 200
    call = mock_ask[0]
    assert existing_analysis["requirement_text"] in call["system_prompt"]
    assert "PostgreSQL" in call["system_prompt"]
    assert call["history"] == [{"role": "user", "content": "Why Postgres over Mongo here?"}]


def test_ask_persists_question_and_answer(mock_ask, existing_analysis):
    resp = client.post(
        "/api/ask",
        json={
            "analysis_id": existing_analysis["id"],
            "question": "Why Postgres over Mongo here?",
            "anthropic_api_key": "sk-ant-fake-key-not-real",
        },
    )
    body = resp.json()
    assert body["answer"] == "Canned answer #1"
    assert len(body["conversation"]) == 2
    assert body["conversation"][0]["role"] == "user"
    assert body["conversation"][0]["content"] == "Why Postgres over Mongo here?"
    assert body["conversation"][1]["role"] == "assistant"
    assert body["conversation"][1]["content"] == "Canned answer #1"


def test_ask_replays_conversation_history_on_second_turn(mock_ask, existing_analysis):
    client.post(
        "/api/ask",
        json={
            "analysis_id": existing_analysis["id"],
            "question": "Why Postgres over Mongo here?",
            "anthropic_api_key": "sk-ant-fake-key-not-real",
        },
    )
    resp = client.post(
        "/api/ask",
        json={
            "analysis_id": existing_analysis["id"],
            "question": "What if I only ever store JSON blobs?",
            "anthropic_api_key": "sk-ant-fake-key-not-real",
        },
    )
    assert resp.status_code == 200
    second_call_history = mock_ask[1]["history"]
    assert second_call_history == [
        {"role": "user", "content": "Why Postgres over Mongo here?"},
        {"role": "assistant", "content": "Canned answer #1"},
        {"role": "user", "content": "What if I only ever store JSON blobs?"},
    ]
    # Full history returned to the client too, not just the latest turn.
    assert len(resp.json()["conversation"]) == 4


def test_ask_scoped_to_one_analysis_does_not_leak_across_analyses(mock_ask, existing_analysis):
    """DDD 4.3 structural invariant: a second, unrelated Analysis must never see the first
    Analysis's conversation history."""
    other_analysis = client.post(
        "/api/analyses",
        json={
            "requirement_text": "Unrelated healthcare chatbot.",
            "signals": {},
            "recommendations": {"database": {"v": "PostgreSQL", "conf": "high"}},
        },
    ).json()

    client.post(
        "/api/ask",
        json={
            "analysis_id": existing_analysis["id"],
            "question": "Why Postgres over Mongo here?",
            "anthropic_api_key": "sk-ant-fake-key-not-real",
        },
    )
    resp = client.post(
        "/api/ask",
        json={
            "analysis_id": other_analysis["id"],
            "question": "Is this HIPAA compliant?",
            "anthropic_api_key": "sk-ant-fake-key-not-real",
        },
    )
    assert resp.status_code == 200
    # Second call's history must start fresh — no bleed-over from the other analysis.
    assert mock_ask[1]["history"] == [{"role": "user", "content": "Is this HIPAA compliant?"}]
    assert len(resp.json()["conversation"]) == 2


def test_ask_never_returns_the_api_key(mock_ask, existing_analysis):
    resp = client.post(
        "/api/ask",
        json={
            "analysis_id": existing_analysis["id"],
            "question": "Why Postgres over Mongo here?",
            "anthropic_api_key": "sk-ant-fake-key-not-real",
        },
    )
    assert "sk-ant-fake-key-not-real" not in resp.text


def test_ask_rejects_overlong_question(mock_ask, existing_analysis):
    resp = client.post(
        "/api/ask",
        json={
            "analysis_id": existing_analysis["id"],
            "question": "x" * 4_001,
            "anthropic_api_key": "sk-ant-fake-key-not-real",
        },
    )
    assert resp.status_code == 422


def test_ask_surfaces_anthropic_api_errors_as_502(monkeypatch, existing_analysis):
    from fastapi import HTTPException

    def _raise(*args, **kwargs):
        raise HTTPException(status_code=502, detail="Anthropic API error: simulated failure")

    monkeypatch.setattr(ask_module, "_run_ask", _raise)
    resp = client.post(
        "/api/ask",
        json={
            "analysis_id": existing_analysis["id"],
            "question": "Why Postgres over Mongo here?",
            "anthropic_api_key": "sk-ant-fake-key-not-real",
        },
    )
    assert resp.status_code == 502


def test_ask_persists_nothing_when_model_call_fails(monkeypatch, existing_analysis):
    """No orphaned question-with-no-answer row — see module docstring."""
    from fastapi import HTTPException

    def _raise(*args, **kwargs):
        raise HTTPException(status_code=502, detail="simulated failure")

    monkeypatch.setattr(ask_module, "_run_ask", _raise)
    client.post(
        "/api/ask",
        json={
            "analysis_id": existing_analysis["id"],
            "question": "Why Postgres over Mongo here?",
            "anthropic_api_key": "sk-ant-fake-key-not-real",
        },
    )

    from app.db import SessionLocal
    from app import models

    db = SessionLocal()
    try:
        rows = db.query(models.ConversationMessage).filter_by(
            analysis_id=existing_analysis["id"]
        ).all()
        assert len(rows) == 0
    finally:
        db.close()


def test_build_grounding_context_uses_question_as_query():
    """/api/ask grounds on the follow-up QUESTION, not the original requirement text (module
    docstring: anti-pattern sections are written to directly answer 'is X okay?' phrasing)."""
    grounding = ask_module._build_grounding_context(
        "Is it okay to just use Postgres LIKE queries for our search feature?"
    )
    assert grounding != ""
    assert "08-search-and-recommendation-engine.md" in grounding
    assert "anti-pattern" in grounding.lower()


def test_build_grounding_context_empty_for_zero_overlap_question():
    """GROUNDING_SCORE_THRESHOLD is deliberately low (see refine.py's constant comment) —
    filters true zero-overlap queries only, not merely off-topic-sounding ones."""
    grounding = ask_module._build_grounding_context("Tell me a joke about cats.")
    assert grounding == ""


def test_ask_still_works_when_grounding_is_empty(mock_ask, existing_analysis):
    """Grounding must never gate the core ask flow."""
    resp = client.post(
        "/api/ask",
        json={
            "analysis_id": existing_analysis["id"],
            "question": "What's the best way to configure DNS for our custom domain?",
            "anthropic_api_key": "sk-ant-fake-key-not-real",
        },
    )
    assert resp.status_code == 200
