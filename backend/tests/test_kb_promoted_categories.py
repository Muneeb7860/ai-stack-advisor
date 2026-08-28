"""
Regression tests for the six categories promoted from docs/use-case-knowledge-base's
target-design domains (12, 13, 15, 16, 17, 18) into real pickX()/pick_x() functions.

One test per guard condition actually exercised, not just "does it not crash" — same
discipline as the frontend-expansion-pass regressions in test_rule_engine.py. Doc 14 has no
corresponding category and no test here; see the comment above pickAuditLogging() in
index.html for why.

These tests only exercise the Python engine (rule_engine.recommend_stack). Cross-engine
agreement is test_engine_differential.py's job, not this file's.
"""
from app.rule_engine import recommend_stack


def _rec(text):
    return recommend_stack(text)["recommendations"]


# ---------------------------------------------------------------------- audit_logging (doc 15)

def test_audit_logging_says_application_logs_suffice_for_a_minimal_project():
    v = _rec("A personal learning project — a to-do app for myself.")["audit_logging"]["v"]
    assert "no dedicated audit pipeline" in v.lower()


def test_audit_logging_requires_a_separate_immutable_pipeline_for_compliance():
    v = _rec("A HIPAA-compliant patient records system for a hospital network.")["audit_logging"]["v"]
    assert "immutable" in v.lower() and "audit pipeline" in v.lower()


# ------------------------------------------------------------------ privileged_access (doc 18)

def test_privileged_access_needs_no_process_for_a_solo_minimal_project():
    v = _rec("A solo learning project, just me building a hobby app.")["privileged_access"]["v"]
    assert "no formal privileged-access process" in v.lower()


def test_privileged_access_uses_bastion_and_jit_for_on_prem():
    v = _rec("We run our own servers in-house and cannot move to cloud.")["privileged_access"]["v"]
    assert "bastion" in v.lower()


def test_privileged_access_requires_jit_elevation_for_regulated_enterprise():
    v = _rec("A large enterprise fintech platform handling real transactions, SOC2 required.")["privileged_access"]["v"]
    assert "just-in-time" in v.lower() or "pim" in v.lower()


def test_privileged_access_does_not_duplicate_iam_vendor_pick():
    """pick_privileged_access reasons about HOW a human gets admin; pick_iam picks a vendor.
    The two must stay distinct picks, not the same string under two keys."""
    recs = _rec("Enterprise fintech platform, SOC2, 50 engineers.")
    assert recs["iam"]["v"] != recs["privileged_access"]["v"]


# ------------------------------------------------------------------- testing_strategy (doc 16)

def test_testing_strategy_skips_the_pyramid_extras_for_a_minimal_project():
    v = _rec("A college capstone project, just a class assignment.")["testing_strategy"]["v"]
    assert "skip the rest" in v.lower()


def test_testing_strategy_locked_down_compliance_only_case_has_no_dangling_plus():
    """Regression lock for the bug the JS<->Python differential harness caught: a
    compliance-only, non-highScale requirement used to produce a `v` with a dangling '+ '
    (JS) or an unjustified 'high' confidence with no visible reason (Python), because the
    data-strategy note was gated on `len(notes) > 1` instead of on whether it specifically
    fired. Locked down here as its own case so it cannot regress silently."""
    rec = _rec("Internal knowledge assistant with RAG over Confluence, enterprise, SOC2, "
                "6 engineers, 4 month timeline.")["testing_strategy"]
    assert rec["v"].strip()
    assert not rec["v"].rstrip().endswith("+")
    assert "masked/synthetic test-data strategy" in rec["v"]
    # highScale did not fire in this requirement, so the load/soak fragment must not appear.
    assert "load/soak" not in rec["v"]


def test_testing_strategy_adds_load_soak_note_for_high_scale():
    v = _rec("High traffic e-commerce platform expecting millions of users during a sales event, "
              "5 engineers, no compliance requirement.")["testing_strategy"]["v"]
    assert "load/soak testing" in v


def test_testing_strategy_composes_both_notes_when_both_signals_fire():
    v = _rec("High traffic fintech trading platform, PCI compliance, millions of users during "
              "peak load.")["testing_strategy"]["v"]
    assert "load/soak testing" in v
    assert "masked/synthetic test-data strategy" in v


# ------------------------------------------------------------------- network_boundary (doc 13)

def test_network_boundary_not_applicable_for_on_prem():
    v = _rec("We run our own servers in-house and cannot move to cloud.")["network_boundary"]["v"]
    assert v.lower().startswith("not applicable")


def test_network_boundary_not_needed_for_a_minimal_project():
    v = _rec("A personal side project, just for learning, no compliance requirement.")["network_boundary"]["v"]
    assert "no private-endpoint architecture needed" in v.lower()


def test_network_boundary_requires_private_endpoints_for_healthcare():
    v = _rec("A HIPAA-compliant clinical data platform for a hospital.")["network_boundary"]["v"]
    assert "private endpoint" in v.lower()


# --------------------------------------------------------------- multi_cloud_bridging (doc 17)

def test_multi_cloud_bridging_not_applicable_for_a_single_cloud_shop():
    v = _rec("AWS shop building an e-commerce recommendation engine.")["multi_cloud_bridging"]["v"]
    assert v.lower().startswith("not applicable")


def test_multi_cloud_bridging_signal_requires_two_distinct_vendors_not_one_mentioned_twice():
    """multiCloudMentioned counts distinct vendor GROUPS, not raw keyword hits — 'AWS and AWS
    Lambda' must not count as two providers."""
    signals = recommend_stack("AWS and AWS Lambda shop, building a backend.")["signals"]
    assert signals.get("multiCloudMentioned") is not True


def test_multi_cloud_bridging_fires_for_two_distinct_providers():
    signals = recommend_stack("GCP compute plane and Azure data plane, PCI compliance, "
                               "high traffic.")["signals"]
    assert signals.get("multiCloudMentioned") is True
    v = _rec("GCP compute plane and Azure data plane, PCI compliance, high traffic.")["multi_cloud_bridging"]["v"]
    assert not v.lower().startswith("not applicable")
    assert "constraint" in v.lower()


def test_multi_cloud_bridging_not_applicable_when_on_prem_even_with_two_vendors_named():
    """The onPrem override takes priority — an air-gapped requirement that happens to mention
    two cloud vendor names (e.g. ruling both out) is not a multi-cloud bridging design."""
    v = _rec("We run our own servers in-house and cannot move to cloud, though we evaluated "
              "AWS and Azure before deciding against it.")["multi_cloud_bridging"]["v"]
    assert v.lower().startswith("not applicable")


# ------------------------------------------------------------------- security_gates (doc 12)

def test_security_gates_are_minimal_for_a_learning_project():
    v = _rec("A personal hobby project, just for learning.")["security_gates"]["v"]
    assert "secrets scanning" in v.lower()
    assert "full gate set" not in v.lower()


def test_security_gates_are_full_set_for_regulated_enterprise():
    v = _rec("A large enterprise fintech platform, PCI compliance, SOC2 required.")["security_gates"]["v"]
    assert "full gate set" in v.lower()


# ------------------------------------------------------------- STACK_CARD_CATEGORY reachability

def test_hybrid_connectivity_and_new_categories_are_reachable_from_refine():
    """Regression lock for the pre-existing gap found while wiring these categories: a card
    missing from STACK_CARD_CATEGORY in index.html renders its refine button but can never
    show a real suggestion (applyRefinementToCard's `category && p.category...` guard always
    short-circuits). This test only asserts the Python side computes a `v`/`why`/`conf` for
    every promoted category — the STACK_CARD_CATEGORY mapping itself lives in index.html and
    is JS-only, so it cannot be asserted from the Python test suite directly."""
    recs = _rec("A generic web app for a small team.")
    for key in ("audit_logging", "privileged_access", "testing_strategy", "network_boundary",
                "multi_cloud_bridging", "security_gates"):
        assert recs[key].get("v"), f"{key} produced no pick"
        assert recs[key].get("why"), f"{key} produced no rationale"
        assert recs[key].get("conf") in ("high", "medium", "low"), f"{key} has no confidence"
