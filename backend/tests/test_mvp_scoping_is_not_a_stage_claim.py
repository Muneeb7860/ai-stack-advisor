"""Asking whether a feature is in MVP scope is not declaring the project an MVP.

Found by running a real OTP-verification design document through the engine. That document
describes an enterprise verification platform at 300M checks/day and says "enterprise" four times.
It also contains exactly one occurrence of "mvp" — a row in its own decisions table:

    | 6 | Is `cancel` in MVP scope? | Product | §10 |

That one scoping question set startupMvp, which then out-voted the four genuine enterprise
mentions in pick_iam and produced "OneLogin — or cloud-native (AWS Cognito / Firebase Auth)": a
small-team identity vendor, for a platform serving ~3,472 checks per second.

Same shape as _TIMELINE_DISQUALIFIERS, where "retain audit logs for 12 months" was being read as a
ship date: a token only means what it looks like when the surrounding words agree.

The rule is deliberately conservative. It withdraws the stage claim only when EVERY occurrence of
"mvp" is a scoping phrase. A document that says "MVP is send-code and check-code over SMS" AND asks
"is cancel in MVP scope?" is still making a genuine stage claim, and eval case r01 depends on that.
"""
import pytest

from app.rule_engine import detect_signals, pick_iam

DECISION_ROW = "| 6 | Is `cancel` in MVP scope? | Product | §10 |"


# --------------------------------------------------------------- scoping a decision is not a stage

@pytest.mark.parametrize("text", [
    DECISION_ROW,
    "Is rate limiting in MVP scope?",
    "Cancel is out of MVP scope for now.",
    "We will decide what falls within the MVP scope next week.",
])
def test_scoping_phrasing_does_not_claim_the_project_is_an_mvp(text):
    assert detect_signals(text)["startupMvp"] is False, text


# ------------------------------------------------------------------ genuine stage claims survive

@pytest.mark.parametrize("text", [
    "MVP is send-code and check-code over SMS, with a REST API and a dashboard.",
    "We are shipping an MVP in eight weeks.",
    "For the MVP we will only support SMS.",
    "We are a bootstrapped startup with a small team.",
    "Early-stage product, need to move fast.",
])
def test_a_real_stage_claim_still_fires(text):
    assert detect_signals(text)["startupMvp"] is True, text


def test_a_scoping_row_does_not_cancel_a_real_claim_in_the_same_document():
    """The rule counts occurrences rather than matching the first one. A document doing both is
    making the claim — this is the case eval r01 (India OTP) depends on."""
    assert detect_signals(
        "MVP is send-code and check-code over SMS. Separately: is cancel in MVP scope?"
    )["startupMvp"] is True


# --------------------------------------------------------------------- the downstream consequence

def test_an_enterprise_platform_no_longer_gets_a_small_team_identity_vendor():
    """The actual harm. Before the fix this returned OneLogin / Cognito — the small-team branch —
    because one scoping question out-voted four enterprise mentions."""
    s = detect_signals(
        "Enterprise verification platform. Enterprise integrators hold the verification ID. "
        "Audit logging and role-based access are required. At 300M/day the volume is material. "
        "| 6 | Is `cancel` in MVP scope? | Product |"
    )
    assert s["enterprise"] is True and s["startupMvp"] is False
    assert "OneLogin" not in pick_iam(s)["v"], pick_iam(s)["v"]
