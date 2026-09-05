"""Two defects from one reported requirement, both in the "stated constraint ignored" family.

The requirement: "As we are cpaas company need to modernising otp generation and otp validation
system for cpaas. strictly no cloud and ai we should be deploy in our own servers."

Reported symptom was "answers suggests azure as priority". The primary picks were all correct —
cloud said on-premises, IAM said Keycloak/FreeIPA. What produced Azure was the IAM card's
*alternatives* table, which was `alternatives: IAM_VENDORS` unconditionally: eleven vendors led
by Okta and Microsoft Entra ID, every one of them needing the public cloud the requirement had
just excluded, and none of them the self-hosted IdP being recommended one line above.

The card contradicted itself in a single view — its own `why` said those products "cannot run
air-gapped" while listing them as the shortlist. Same defect class the domain floors exist for
(AGENTS.md): a hosted SaaS offered to a stack with nothing to host it on.

The second defect was in the same sentence. "strictly no cloud and ai" excluded the cloud half
and kept every AI card, because EXCLUSION_TERMS["llm"] listed 'llm', 'gpt', 'openai', 'genai'
and 'generative ai' but not the bare word the user actually typed.
"""
import pytest

from app.rule_engine import IAM_VENDORS, detect_signals, pick_iam

REPORTED = ("As we are cpaas company need to modernising otp generation and otp validation system "
            "for cpaas. strictly no cloud and ai we should be deploy in our own servers.")


# ------------------------------------------------------- the alternatives table respects on-prem

def test_on_prem_alternatives_contain_no_hosted_only_vendor():
    """The reported bug, stated as an assertion: no 'saas' vendor may appear under an air-gapped
    requirement. Okta and Entra ID were both in this list."""
    alts = pick_iam(detect_signals(REPORTED))["alternatives"]
    hosted = [v["name"] for v in alts if v["deploy"] == "saas"]
    assert not hosted, f"hosted-only vendors offered to an air-gapped stack: {hosted}"


def test_on_prem_alternatives_include_the_thing_actually_recommended():
    """Keycloak and FreeIPA are what the pick names, and neither was in the comparison at all —
    so the table could not contain the recommendation it sat underneath."""
    r = pick_iam(detect_signals(REPORTED))
    names = {v["name"] for v in r["alternatives"]}
    assert "Keycloak" in names and "FreeIPA" in names, f"self-hosted options missing: {sorted(names)}"
    assert "Keycloak" in r["v"]


def test_non_on_prem_still_gets_the_full_catalogue():
    """The filter must not leak into the ordinary path — over-filtering would be a worse bug than
    the one being fixed, and silent."""
    s = detect_signals("We are a 200-person SaaS company on AWS needing enterprise SSO and SCIM.")
    assert not s["onPrem"]
    alts = pick_iam(s)["alternatives"]
    assert len(alts) == len(IAM_VENDORS)
    assert any(v["id"] == "okta" for v in alts)


def test_every_vendor_declares_a_deployment_model():
    """A vendor added without `deploy` would silently pass the on-prem filter, since the filter
    tests `!= 'saas'`. Absence must fail loudly here rather than quietly there."""
    missing = [v.get("name", v.get("id")) for v in IAM_VENDORS if v.get("deploy") not in ("saas", "self", "both")]
    assert not missing, f"IAM vendors with no/invalid deploy field: {missing}"


# --------------------------------------------------------------------- "no ai" is an exclusion

def test_no_ai_is_detected_as_an_llm_exclusion():
    assert detect_signals(REPORTED)["excluded"].get("llm") is True


@pytest.mark.parametrize("text", [
    "We need reliable email delivery for receipts.",
    "The system must remain available during maintenance windows.",
    "We maintain a chain of custody for every document.",
])
def test_bare_ai_does_not_fire_inside_ordinary_words(text):
    """'ai' is short enough to be dangerous. find_exclusions anchors terms with \\b...\\b, so it
    cannot match inside email/available/maintain/chain — asserted rather than assumed, because
    this is the risk the term was added against."""
    assert not detect_signals("We do not want " + text)["excluded"].get("llm")


def test_a_real_ai_exclusion_still_fires_on_the_bare_word():
    assert detect_signals("Build an OTP service. No AI anywhere in it.")["excluded"].get("llm") is True
