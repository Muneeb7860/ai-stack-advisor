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

from tests.ollama_gate import requires_ollama

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

    def _fake_run_refinement(api_key, requirement_text, recommendations, signals=None):
        calls.append(
            {
                "api_key": api_key,
                "requirement_text": requirement_text,
                "recommendations": recommendations,
                "signals": signals,
            }
        )
        return FAKE_REFINEMENT_RESULT, {"input_tokens": 512, "output_tokens": 128}

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
    # Real usage numbers flow through to the response (see mock_anthropic's fake tuple return).
    assert body["usage"] == {"input_tokens": 512, "output_tokens": 128}

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


# ------------------------------------------------------- category enum / server-side filtering
# refine_module.VALID_CATEGORIES mirrors index.html's STACK_CARD_CATEGORY values exactly — a
# category outside that closed set can never be matched back to a card by
# applyRefinementToCard()'s frontend matching, so it must not reach the response as if it were a
# normal, applicable pick. See VALID_CATEGORIES' own comment in routers/refine.py for the full
# reasoning (this closes Step 4 of the RAG-derivation-engine plan: the six categories promoted
# in the prior KB-promotion pass are only genuinely reachable from /api/refine if a bogus
# category can't silently swallow a real one, or itself go unnoticed).

def test_valid_categories_include_all_six_promoted_kb_categories():
    """Regression lock: the six categories promoted from docs/use-case-knowledge-base (12, 13,
    15, 16, 17, 18) must be in the enum, or the model is structurally unable to ever adjust
    them even though the categories themselves exist and render."""
    for cat in ("auditlogging", "privilegedaccess", "testingstrategy", "networkboundary",
                "multicloudbridging", "securitygates"):
        assert cat in refine_module.VALID_CATEGORIES


def test_refine_drops_a_pick_with_an_unrecognized_category(monkeypatch, refine_payload):
    """A category the model invents (or gets wrong, e.g. the JSON key 'gw' instead of the
    canonical 'gateway') must not reach the response as if it were an applicable pick — it
    would silently never match any card, indistinguishable from the rule engine simply being
    right about that category."""
    bogus_result = {
        "adjusted_picks": [
            {"category": "gw", "pick": "Kong", "reason": "Requirement names Kong explicitly."},
            {"category": "database", "pick": "PostgreSQL only", "reason": "Only transactional data mentioned."},
        ],
        "rationale": "Two changes proposed.",
        "open_questions": [],
    }

    def _fake_run_refinement(api_key, requirement_text, recommendations, signals=None):
        return bogus_result, {"input_tokens": 10, "output_tokens": 10}

    monkeypatch.setattr(refine_module, "_run_refinement", _fake_run_refinement)
    resp = client.post("/api/refine", json=refine_payload)
    assert resp.status_code == 200
    body = resp.json()
    # Only the valid-category pick survives into adjusted_picks.
    assert len(body["adjusted_picks"]) == 1
    assert body["adjusted_picks"][0]["category"] == "database"
    # The dropped pick isn't silently lost — it's surfaced as an open question instead.
    assert any("gw" in q for q in body["open_questions"])


def test_refine_accepts_a_promoted_kb_category(monkeypatch, refine_payload):
    """The positive case: a pick using one of the six newly-promoted categories' canonical
    value passes straight through, unfiltered."""
    result = {
        "adjusted_picks": [
            {
                "category": "auditlogging",
                "pick": "Application logs only — no dedicated audit pipeline needed",
                "reason": "Requirement text describes a personal learning project with no compliance obligation.",
            }
        ],
        "rationale": "Compliance signal was a false positive.",
        "open_questions": [],
    }

    def _fake_run_refinement(api_key, requirement_text, recommendations, signals=None):
        return result, {"input_tokens": 10, "output_tokens": 10}

    monkeypatch.setattr(refine_module, "_run_refinement", _fake_run_refinement)
    resp = client.post("/api/refine", json=refine_payload)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["adjusted_picks"]) == 1
    assert body["adjusted_picks"][0]["category"] == "auditlogging"
    assert body["open_questions"] == []


def test_filter_to_valid_categories_is_a_noop_when_everything_is_valid():
    result = {
        "adjusted_picks": [{"category": "cloud", "pick": "AWS", "reason": "x"}],
        "rationale": "r",
        "open_questions": ["q"],
    }
    filtered = refine_module._filter_to_valid_categories(result)
    assert filtered == result


def test_refinement_tool_schema_enumerates_valid_categories():
    """The tool schema itself must expose VALID_CATEGORIES as an enum — this is the actual
    'wiring' Step 4 closes: before this, category was an unconstrained string with no enum at
    all, for every category, not just the six newly-promoted ones."""
    category_schema = refine_module.REFINEMENT_TOOL["input_schema"]["properties"]["adjusted_picks"]["items"]["properties"]["category"]
    assert category_schema["enum"] == refine_module.VALID_CATEGORIES


# ------------------------------------------------------------ scale-aware retrieval wiring
# Step 2 of the RAG-derivation-engine plan (see app/retrieval.py's build_scale_aware_query()).

def test_refine_passes_the_analysis_signals_to_the_model(mock_anthropic, refine_payload):
    """An existing Analysis's real signals (created via POST /api/analyses, same as the
    frontend's actual flow — see index.html's ensureAnalysisId()) must reach _run_refinement,
    which is what threads them into the retrieval query (see _build_grounding_context)."""
    created = client.post(
        "/api/analyses",
        json={
            "requirement_text": refine_payload["requirement_text"],
            "signals": {"finance": True, "compliance": True},
            "recommendations": refine_payload["recommendations"],
        },
    ).json()
    client.post("/api/refine", json={**refine_payload, "analysis_id": created["id"]})
    assert mock_anthropic[0]["signals"] == {"finance": True, "compliance": True}


def test_refine_passes_empty_signals_for_a_freshly_created_analysis(mock_anthropic, refine_payload):
    """The documented gap (this module's own docstring): a refine call with no analysis_id
    creates a new Analysis with signals={} — that {} must reach _run_refinement too (as a real
    empty dict, not silently omitted), so grounding degrades exactly the way
    build_scale_aware_query() is designed to degrade, not by luck."""
    client.post("/api/refine", json=refine_payload)
    assert mock_anthropic[0]["signals"] == {}


def test_build_grounding_context_folds_signals_into_the_retrieval_query(monkeypatch):
    """Unit-level check of refine.py's own _build_grounding_context, mirroring ask.py's
    equivalent test — monkeypatches retrieve() directly so this runs everywhere, no
    @requires_ollama needed."""
    captured = {}

    def _fake_retrieve(query, top_k=5):
        captured["query"] = query
        return []

    monkeypatch.setattr(refine_module, "retrieve", _fake_retrieve)
    refine_module._build_grounding_context("What audit logging do I need?", {"enterprise": True})
    assert "enterprise" in captured["query"].lower()
    assert captured["query"].startswith("What audit logging do I need?")


def test_refine_surfaces_anthropic_api_errors_as_502(monkeypatch, refine_payload):
    from fastapi import HTTPException

    def _raise(*args, **kwargs):
        raise HTTPException(status_code=502, detail="Anthropic API error: simulated failure")

    monkeypatch.setattr(refine_module, "_run_refinement", _raise)
    resp = client.post("/api/refine", json=refine_payload)
    assert resp.status_code == 502


@requires_ollama
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
    """Best-effort, not a hard gate (module docstring) — GROUNDING_SCORE_THRESHOLD is tuned to
    the embedding score scale (0.55, see refine.py's constant comment for the full empirical
    reasoning post-migration to ChromaDB/embeddings), so this only filters TRUE
    zero-relevance queries, not merely off-topic-but-still-technical-sounding ones (those can
    legitimately score close to the threshold and are an accepted, disclosed trade-off — not
    something this test asserts against)."""
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


# --- Local-model (Ollama) fallback provider routing --- see app/llm_providers.py for the real
# structured-output reliability numbers this feature is based on; these tests cover this
# endpoint's own routing/opt-in-gating logic, not Ollama itself (monkeypatched, same spirit as
# mock_anthropic above — no real local model call needed to run this file).

def test_refine_rejects_ollama_provider_when_not_enabled(refine_payload):
    """Both sides must opt in (LLM_PROVIDER=ollama on the deployment AND provider='ollama' on
    the request) — see routers/refine.py. Default test settings have LLM_PROVIDER=anthropic,
    so a caller asking for the local path gets a clear 400, never a silent reroute to Claude
    nor an attempt to actually reach Ollama."""
    resp = client.post(
        "/api/refine",
        json={**refine_payload, "provider": "ollama", "anthropic_api_key": None},
    )
    assert resp.status_code == 400
    assert "not enabled" in resp.json()["detail"]


def test_refine_ollama_provider_works_when_enabled(monkeypatch, refine_payload):
    """With the deployment opted in (LLM_PROVIDER=ollama) and the caller opting in per-request,
    /api/refine routes to the local path, omits requiring an anthropic_api_key, and labels the
    response provider='ollama'."""
    from app.config import settings

    monkeypatch.setattr(settings, "llm_provider", "ollama")
    calls = []

    def _fake_run_ollama_refinement(base_url, model, system_prompt, tool, requirement_text, recommendations, grounding):
        calls.append({"requirement_text": requirement_text, "recommendations": recommendations})
        return FAKE_REFINEMENT_RESULT, {"input_tokens": 10, "output_tokens": 5}

    monkeypatch.setattr(refine_module, "run_ollama_refinement", _fake_run_ollama_refinement)

    resp = client.post(
        "/api/refine",
        json={
            "requirement_text": refine_payload["requirement_text"],
            "recommendations": refine_payload["recommendations"],
            "provider": "ollama",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "ollama"
    assert len(calls) == 1


def test_refine_request_requires_api_key_for_anthropic_provider(refine_payload):
    """anthropic_api_key is optional at the schema level (to allow the ollama path), but still
    required when provider is (implicitly or explicitly) 'anthropic' — enforced by
    schemas.RefineRequest's model_validator, not left to fail deeper in the call stack."""
    resp = client.post(
        "/api/refine",
        json={**refine_payload, "anthropic_api_key": None},
    )
    assert resp.status_code == 422
