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
    """Category set as of the frontend expansion pass (see docs/adr/0001, Addendum 2) —
    vram_tier was replaced by compute_tier, and cost_estimate/runtime plus 12 vendor-comparison
    keys were added; hybrid_connectivity and integration_guidance were added when the JS<->Python
    parity gap they'd been sitting in was closed (see tests/test_engine_parity.py). Six more
    categories (audit_logging, privileged_access, testing_strategy, network_boundary,
    multi_cloud_bridging, security_gates) were added when docs 12/13/15/16/17/18 in
    docs/use-case-knowledge-base were promoted from target-design to implemented. gitops and
    gitops_vendor were added for the new GitOps CD (ArgoCD/Flux) category — gitops is the plain
    key used by STACK_CARD_CATEGORY/refine (no separate "base" pick exists for this category,
    unlike cicd/compute), and gitops_vendor is the *_vendor-convention alias used by the
    alt-toggle/suppress machinery; both hold the same object. agent_framework_vendor was added
    for the new Agent Framework (LangGraph/Pydantic AI/FastMCP) category — a bespoke, non-"stack"
    section like vector_db_vendor (has its own altToggle but no STACK_CARD_CATEGORY entry, since
    it doesn't render as a refine/ask/challenge-enabled stack card), so it needs no plain-key
    alias the way gitops does. inference_serving_vendor (vLLM/SGLang) was added the same
    bespoke-section way, gated on self-hosting actually being at production scale rather than
    just present at all (a genuinely different tier from pick_runtime's Ollama recommendation).
    If this test needs updating again, cross-check against the actual index.html analyze()
    assembly, not against what an MCP client currently expects.

    Note this list is hand-maintained, so it only catches a key added on the PYTHON side — it is
    not a substitute for test_engine_parity.py, which is what catches a category that landed in
    index.html and never got ported here."""
    result = recommend_stack("A generic web app for a small team.")
    expected_categories = {
        "cloud", "gateway", "iam", "languages", "architecture", "compute", "messaging",
        "mesh", "cache", "database", "containers", "observability", "frontend", "cicd", "dns",
        "docs", "hybrid_connectivity", "llm", "mcp_servers", "rag", "guardrails",
        "integration_guidance", "cost_optimization", "cost_estimate",
        "concurrency", "governance", "tradeoffs", "model_orchestration", "hosting_location",
        "compute_tier", "runtime", "interface_topology", "mcp_vs_api", "guardrail_pipeline",
        "vector_db_placement", "cloud_vendor", "compute_platform_vendor", "orchestrator_vendor",
        "gateway_vendor", "database_vendor", "messaging_vendor", "llm_provider_vendor",
        "vector_db_vendor", "guardrails_vendor", "cicd_vendor", "observability_vendor",
        "frontend_vendor", "audit_logging", "privileged_access", "testing_strategy",
        "network_boundary", "multi_cloud_bridging", "security_gates", "gitops", "gitops_vendor",
        "agent_framework_vendor", "inference_serving_vendor",
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


# ---------- Frontend expansion pass regressions (docs/adr/0001, Addendum 2) ----------
# One test per new dimension actually exercised in the 41-scenario verification, not just
# "does it not crash" — same discipline as the bugs above.


def test_live_multiplayer_routes_to_redis_not_kafka_or_postgres():
    """A live-quiz-app-shaped bug the expansion pass's own real-world testing caught: this used
    to recommend Postgres + Kafka for what's actually a Redis-sorted-set + Pub/Sub problem.
    The messaging pick's rationale text explicitly says "not Kafka" as part of explaining the
    fix, so assert the actual recommended broker (Redis Pub/Sub) rather than absence of the
    word "Kafka" anywhere in the string."""
    text = "Building a live quiz app with leaderboards, multiplayer game rooms, real-time scoring for up to 500 concurrent players."
    result = recommend_stack(text)
    rec = result["recommendations"]
    assert "Redis" in rec["database"]["v"]
    assert rec["messaging"]["v"].startswith("Redis Pub/Sub")


def test_collaborative_editing_routes_to_crdt_not_kafka():
    """Deliberately avoids the word "multiplayer" in the input — pick_messaging() checks
    liveMultiplayer before collabEditing (matching index.html's branch order exactly, verified
    in the 41-scenario diff), so text triggering both signals would hit the multiplayer branch
    first. This text is pure collaborative-editing phrasing to isolate the CRDT branch."""
    text = "Google-Docs-like collaborative editing tool with real-time cursors and a shared whiteboard for co-editing a document."
    result = recommend_stack(text)
    msg = result["recommendations"]["messaging"]["v"]
    assert msg.startswith("CRDT sync relay")


def test_video_conferencing_gets_sfu_tradeoff_card():
    text = "Video conferencing app supporting group calls with screen sharing, up to 20 participants per call, WebRTC based."
    result = recommend_stack(text)
    media_card = next((t for t in result["recommendations"]["tradeoffs"] if "Media server topology" in t["d"]), None)
    assert media_card is not None
    assert "SFU" in media_card["rec"]


def test_telehealth_phrasing_triggers_video_conferencing_signal():
    """Stress-test gap the expansion pass found and fixed: 'telehealth'/'video consultations'
    wasn't triggering the video-conferencing reasoning even though it's the same underlying need."""
    signals = detect_signals("Telehealth platform for video consultations between doctors and patients, HIPAA compliant.")
    assert signals["videoConferencing"] is True


def test_fleet_route_optimization_phrasing_triggers_geospatial_signal():
    """The other stress-test gap: 'route optimization'/'fleet management' wasn't triggering
    the geospatial reasoning."""
    signals = detect_signals("Fleet management app with live driver location tracking, route optimization, nearby drivers search, GPS based.")
    assert signals["geospatial"] is True
    assert "PostGIS" in recommend_stack("Fleet management app with live driver location tracking, route optimization, GPS based.")["recommendations"]["database"]["why"]


def test_social_feed_fanout_routes_to_wide_column_store():
    text = "Social media app with a news feed / timeline that fans out posts to millions of followers, high scale."
    result = recommend_stack(text)
    db = result["recommendations"]["database"]["v"]
    assert "Cassandra" in db or "DynamoDB" in db


def test_fixed_scope_government_contract_recommends_waterfall():
    """Delivery-methodology dimension: scope certainty/contract type is the driver, not team
    size — a fixed-price government RFP should recommend Waterfall regardless of team size."""
    text = "Government contract with fixed-price fixed-scope delivery, RFP-based statement of work, gated delivery required."
    result = recommend_stack(text)
    waterfall_card = next(t for t in result["recommendations"]["tradeoffs"] if "Waterfall vs. Agile" in t["d"])
    assert "Waterfall" in waterfall_card["rec"]


def test_small_team_alone_does_not_force_waterfall():
    """The corrected framing this dimension shipped with: small team is an argument FOR Agile,
    not for Waterfall — team size alone must not trigger the fixed-scope branch."""
    text = "3-person startup team building an MVP, move fast."
    result = recommend_stack(text)
    waterfall_card = next(t for t in result["recommendations"]["tradeoffs"] if "Waterfall vs. Agile" in t["d"])
    assert waterfall_card["rec"] == "Agile"


def test_cost_estimate_present_and_scales_with_signals():
    """pickCostEstimate() is new — deliberately a range, not a point estimate (see
    KICKOFF_BRIEF.md's known-traps note). Confirm both scale tiers actually differ."""
    startup = recommend_stack("Early-stage startup building a simple chatbot assistant, budget conscious, small team.")
    enterprise = recommend_stack("Enterprise chatbot with agentic workflows, high traffic, millions of users, need cost estimate for LLM API spend.")
    startup_est = startup["recommendations"]["cost_estimate"]
    enterprise_est = enterprise["recommendations"]["cost_estimate"]
    assert startup_est["scale"] == "low"
    assert enterprise_est["scale"] == "high"
    assert startup_est["llmBand"] is not None
    assert enterprise_est["llmBand"] is not None
    assert startup_est["llmBand"]["label"] != enterprise_est["llmBand"]["label"]
    # Range, not a point estimate — every band label should contain a dash.
    assert "–" in startup_est["computeBand"]["label"] or startup_est["computeBand"]["label"].startswith("$0")


def test_cost_estimate_llm_band_is_zero_for_local_hosting():
    """The audit-fixed bug this field's own comment warns about: a broad /hybrid/i regex would
    have incorrectly zeroed out LLM cost for the real-scale 'Hybrid: cloud API as the
    default...' branch, whose rec does NOT start with 'Local'. Confirm the fix holds: only
    hosting recs starting with 'Local' zero out the LLM band."""
    onprem = recommend_stack("Air-gapped government system, cannot use any public cloud, needs a chatbot assistant.")
    assert onprem["recommendations"]["cost_estimate"]["llmBand"]["label"] == "$0 direct API spend"


def test_compute_tier_replaces_vram_tier():
    """pickVRAMTier() was replaced entirely by pickComputeTier() (5-tier continuum) — confirm
    the new category exists and the old one is genuinely gone, not just renamed in name only."""
    result = recommend_stack("Mobile app running on-device inference, iPad and iPhone deployment target, tablet support.")
    assert result["recommendations"]["compute_tier"]["tier"] == "Mobile / Tablet"
    assert "vram_tier" not in result["recommendations"]


def test_vendor_comparison_layer_present_with_primary_id():
    """The new Group 1-4 vendor-alternatives layer — spot-check one category end to end rather
    than every one, since the 41-scenario diff harness already covers correctness exhaustively;
    this just confirms the shape is wired into recommend_stack()'s actual output."""
    result = recommend_stack("AWS shop, fintech startup, small team.")
    cloud_vendor = result["recommendations"]["cloud_vendor"]
    assert cloud_vendor["primaryId"] == "aws"
