"""Regression suite for app/rule_engine.py — the Python port of index.html's rule engine
(see docs/adr/0001-mcp-rule-engine-port.md for the port decision and its verification).

These assertions are a durable subset of the 13-scenario, zero-diff verification done before
app/mcp/server.py was written to depend on this module (that full verification used a
temporary Node.js harness that wasn't committed — see the ADR). This file exists so a future
change to rule_engine.py that reintroduces one of validation-report.md's already-fixed bugs
fails a real test, not just a one-time manual check that's now history.

No live Postgres needed — this module is pure functions, no DB/network access.
"""
from app.rule_engine import detect_signals, recommend_stack, strip_negations


def test_strip_negations_removes_short_negated_clauses():
    assert "compliance" not in strip_negations("don't have compliance requirements yet")


def test_negation_bug_regression_mvp_example():
    """validation-report.md bug #1: 'don't have compliance requirements yet' was matching the
    compliance signal via plain substring search, incorrectly triggering local/self-hosted
    LLM infra and compliance-driven guardrails for a startup that explicitly opted out."""
    text = (
        "Early-stage startup, 3 engineers, building an MVP web app for scheduling and CRM "
        "with an AI email drafting assistant. Budget conscious, need to launch fast, don't "
        "have compliance requirements yet, want serverless and low ops overhead."
    )
    result = recommend_stack(text)
    assert result["signals"]["compliance"] is False
    assert result["signals"]["startupMvp"] is True
    # Fixed behavior: cloud API hosting, not local/self-hosted (which the bug used to force).
    assert result["recommendations"]["hosting_location"]["rec"] == "Cloud API (hosted, pay-per-token)"


def test_onprem_bug_regression_air_gapped():
    """validation-report.md bug #2: an explicit air-gapped/no-public-cloud requirement had no
    signal at all and fell through to a generic enterprise default — recommending Azure and a
    string of other public-cloud services that directly contradict the stated constraint."""
    text = (
        "Government defense contractor building an internal tool. Air-gapped environment, "
        "cannot use any public cloud. Must run entirely on bare metal deployment inside our "
        "own data center. Team of 20 engineers."
    )
    result = recommend_stack(text)
    assert result["signals"]["onPrem"] is True
    rec = result["recommendations"]
    # No public cloud anywhere in the output — this was the actual bug (Azure leaking through).
    assert "Azure" not in rec["cloud"]["v"]
    assert "AWS" not in rec["cloud"]["v"]
    assert "Google Cloud" not in rec["cloud"]["v"]
    assert rec["cloud"]["conf"] == "high"
    assert "on-prem" in rec["gateway"]["v"].lower()
    assert "self-managed" in rec["compute"]["v"].lower()
    assert "self-hosted" in rec["observability"]["v"].lower()


def test_onprem_soft_signal_is_not_triggered_by_hybrid_cloud_mentions():
    """detectSignals()'s softOnPrem logic: "on-prem" alone shouldn't trigger the override if
    the text also explicitly describes a hybrid setup that includes cloud — only unambiguous
    air-gapped/no-cloud phrasing should always win regardless of nearby wording."""
    text = "We run a hybrid on-prem and cloud system, using AWS for some workloads."
    result = recommend_stack(text)
    assert result["signals"]["onPrem"] is False


def test_warehouse_bug_regression_pure_etl_workload():
    """validation-report.md bug #3: a pure batch-ETL/analytics workload with no transactional/
    chat/RAG signal was getting recommended MongoDB and Cassandra instead of a warehouse."""
    text = (
        "We run nightly ETL batch jobs pulling from multiple sources into a data lake, then "
        "run big data analytics and BI dashboard reporting on top. No transactional app, no "
        "chatbot, no document search."
    )
    result = recommend_stack(text)
    db = result["recommendations"]["database"]
    assert "warehouse" in db["v"].lower() or "bigquery" in db["v"].lower() or "snowflake" in db["v"].lower() or "redshift" in db["v"].lower()


def test_small_team_high_scale_conflict_resolves_to_middle_path():
    """validation-report.md's tightened conflict handling: startupMvp/smallTeam alone used to
    force pure serverless even with highScale/enterprise/realtime also present. Now resolves
    to a stated middle ground (serverless containers), and the Compute Model card must not
    contradict the Kubernetes-vs-Serverless trade-off card for the same signals."""
    text = "4-person ops team building a real-time, high-scale enterprise fraud detection system. Move fast, budget conscious."
    result = recommend_stack(text)
    rec = result["recommendations"]
    assert "Serverless containers" in rec["compute"]["v"]
    k8s_tradeoff = next(t for t in rec["tradeoffs"] if t["d"] == "Kubernetes vs. Serverless")
    assert "Serverless containers" in k8s_tradeoff["rec"]


def test_small_team_regex_fallback_four_person_team():
    """validation-report.md: small-team detection was too narrow (only literal '3 engineers'
    style phrases); '4-person ops team' needed a regex fallback for 'N-person'/'team of N'."""
    text = "We are a 4-person ops team building an internal scheduling tool."
    result = recommend_stack(text)
    assert result["signals"]["smallTeam"] is True


def test_architecture_style_prioritizes_team_size_over_compliance():
    """validation-report.md: enterprise/largeTeam used to be checked before startupMvp/
    smallTeam, so a 3-person team with a compliance requirement got 'microservices' — team
    size must take priority for monolith-vs-microservices specifically (Conway's law)."""
    text = "3 engineers, fintech startup, SOC2 compliance required, move fast."
    result = recommend_stack(text)
    assert "monolith" in result["recommendations"]["architecture"]["v"].lower()


def test_structured_rag_routes_to_sql_not_vector_store():
    # Needs ragNeed=True (via "document search") with structured=True, unstructured=False —
    # NOT a negated "no document search" (that hits pick_rag's "RAG likely not required"
    # branch first, before the structured/SQL check ever runs).
    text = "We have a document search feature over our relational SQL database of orders and transactions."
    result = recommend_stack(text)
    assert result["recommendations"]["rag"]["name"].startswith("Structured/SQL")
    assert result["recommendations"]["vector_db_placement"]["needed"] is False


def test_empty_requirement_text_raises():
    import pytest

    with pytest.raises(ValueError):
        recommend_stack("")
    with pytest.raises(ValueError):
        recommend_stack("   ")


def test_recommend_stack_returns_all_expected_categories():
    result = recommend_stack("A generic web app for a small team.")
    expected_categories = {
        "cloud", "gateway", "iam", "languages", "architecture", "compute", "messaging",
        "mesh", "cache", "database", "containers", "observability", "frontend", "cicd", "dns",
        "docs", "llm", "mcp_servers", "rag", "guardrails", "cost_optimization", "concurrency",
        "governance", "tradeoffs", "model_orchestration", "hosting_location", "vram_tier",
        "interface_topology", "mcp_vs_api", "guardrail_pipeline", "vector_db_placement",
    }
    assert set(result["recommendations"].keys()) == expected_categories


def test_detect_signals_returns_camelcase_keys_matching_index_html():
    """Deliberate naming choice (see rule_engine.py's module docstring): signal dict keys stay
    camelCase, matching index.html exactly, so this stays a diffable port rather than
    introducing a translation layer that could hide a transcription error."""
    signals = detect_signals("fintech startup")
    assert "onPrem" in signals
    assert "startupMvp" in signals
    assert "on_prem" not in signals
