"""Unit tests for build_scale_aware_query() — Step 2 of the RAG-derivation-engine plan (see
app/retrieval.py's own comment above that function for the full rationale).

Deliberately NOT gated behind @requires_ollama, unlike test_retrieval_eval.py: this function is
pure string logic over a signals dict, with no embedding model, no Chroma, no network call
involved — same "needs to run everywhere" reasoning as test_kb_corpus.py's own docstring.
"""
from app.retrieval import build_scale_aware_query


def test_returns_text_unchanged_when_signals_is_none():
    assert build_scale_aware_query("What audit logging do I need?", None) == "What audit logging do I need?"


def test_returns_text_unchanged_when_signals_is_empty():
    """The real, expected case for a refinement created without a prior /api/analyses call —
    see refine.py's docstring on analysis_id being optional. Must degrade silently, not raise."""
    assert build_scale_aware_query("What audit logging do I need?", {}) == "What audit logging do I need?"


def test_returns_text_unchanged_when_no_relevant_flag_is_true():
    """Signals dict is real and non-empty, but none of the flags this function cares about are
    set — e.g. a chatbot/ecommerce-flavored requirement with no scale signal at all."""
    signals = {"chatbot": True, "ecommerce": True, "minimalProject": False, "enterprise": False}
    assert build_scale_aware_query("text", signals) == "text"


def test_appends_minimal_project_descriptor():
    query = build_scale_aware_query("What audit logging do I need?", {"minimalProject": True})
    assert query.startswith("What audit logging do I need?")
    assert "minimal" in query.lower() or "learning" in query.lower()
    assert query != "What audit logging do I need?"


def test_appends_compliance_descriptor_for_any_of_compliance_finance_healthcare():
    for flag in ("compliance", "finance", "healthcare"):
        query = build_scale_aware_query("text", {flag: True})
        assert "regulated" in query.lower() or "compliance" in query.lower()


def test_appends_enterprise_descriptor():
    query = build_scale_aware_query("text", {"enterprise": True})
    assert "enterprise" in query.lower()


def test_appends_high_scale_descriptor():
    query = build_scale_aware_query("text", {"highScale": True})
    assert "high-scale" in query.lower() or "high-traffic" in query.lower()


def test_appends_on_prem_descriptor():
    query = build_scale_aware_query("text", {"onPrem": True})
    assert "on-premises" in query.lower() or "air-gapped" in query.lower()


def test_composes_multiple_descriptors_additively():
    """minimalProject, compliance, enterprise, highScale, onPrem are not mutually exclusive —
    a requirement can genuinely be minimal AND on-prem (e.g. a self-hosted student project), or
    enterprise AND highScale AND compliance all at once. Every flag that's true must contribute
    its own fragment, not just the first one checked."""
    query = build_scale_aware_query("text", {"enterprise": True, "compliance": True, "highScale": True})
    lowered = query.lower()
    assert "enterprise" in lowered
    assert "regulated" in lowered or "compliance" in lowered
    assert "high-scale" in lowered or "high-traffic" in lowered


def test_minimal_project_and_on_prem_compose_together():
    """The one true floor (minimalProject) can still legitimately combine with onPrem — e.g. a
    self-hosted college project — mirroring the same additive-not-exclusive guard pattern used
    throughout rule_engine.py's pickX() functions."""
    query = build_scale_aware_query("text", {"minimalProject": True, "onPrem": True})
    lowered = query.lower()
    assert "minimal" in lowered or "learning" in lowered
    assert "on-premises" in lowered or "air-gapped" in lowered


def test_never_raises_on_unexpected_signal_shapes():
    """Defensive: this function must never be the thing that turns a best-effort grounding
    feature into a 500 for /api/refine or /api/ask."""
    build_scale_aware_query("text", {"minimalProject": "yes"})  # truthy non-bool, still works
    build_scale_aware_query("", {"enterprise": True})  # empty base text
    build_scale_aware_query("text", {"unrelatedKey": True})  # no known flags at all
