"""A cloud pick must say whether it was detected or guessed.

Found by running a real OTP-verification design document through the engine. It named no cloud at
all, and the report came back:

    Microsoft Azure  [medium]
    "Azure mentioned, or enterprise context with likely existing Microsoft 365/AD investment."

One sentence covering both a detection and an inference, so the reader cannot tell which happened —
and the leading clause says "Azure mentioned", which is the reading most people will take. Nothing
in that document mentions Azure, Microsoft, or any cloud; the `enterprise` signal alone routed
there. This is the second time an unfounded Azure surfaced in review, by a different mechanism than
the first (an unfiltered IAM alternatives table).

The same defect was present on the GCP branch ("GCP mentioned, or agentic/data-heavy workload") and
is fixed with it, since leaving half of one function's defect in place is how it grows back.

The AWS and Huawei branches immediately above were already correct ("Explicit AWS usage detected"),
so this makes the function internally consistent rather than inventing a convention.
"""
import pytest

from app.rule_engine import detect_signals, pick_cloud


def _cloud(text):
    return pick_cloud(detect_signals(text))


ENTERPRISE_NO_CLOUD = ("Large regulated enterprise building an internal verification platform for "
                       "employee access, with audit logging and role-based access.")


# ------------------------------------------------------------------ detection stays a detection

@pytest.mark.parametrize("text,vendor", [
    ("We run everything on Azure today.", "Microsoft Azure"),
    ("Our infrastructure is on GCP.", "Google Cloud (GCP)"),
    ("We are an AWS shop.", "AWS"),
])
def test_a_named_cloud_is_high_confidence_and_says_it_was_detected(text, vendor):
    c = _cloud(text)
    assert c["v"] == vendor and c["conf"] == "high"
    assert "explicit" in c["why"].lower(), c["why"]


# ------------------------------------------------------------------- inference admits it guessed

def test_enterprise_alone_does_not_claim_azure_was_mentioned():
    """The exact defect: the requirement names no cloud, so the reason must not read 'mentioned'."""
    c = _cloud(ENTERPRISE_NO_CLOUD)
    assert c["v"] == "Microsoft Azure"
    assert "mentioned" not in c["why"].lower(), c["why"]
    assert "no cloud provider named" in c["why"].lower(), c["why"]


def test_an_inferred_cloud_is_not_presented_as_confidently_as_a_detected_one():
    """It was 'medium' — the same band used for genuine technical-fit arguments. A guess about a
    vendor footprint, drawn from an org-size signal, does not deserve that."""
    assert _cloud(ENTERPRISE_NO_CLOUD)["conf"] == "low"


def test_the_inference_tells_the_user_how_to_override_it():
    """A weak default is only honest if the reader is told what would change it."""
    why = _cloud(ENTERPRISE_NO_CLOUD)["why"].lower()
    assert "aws" in why and "gcp" in why, why


def test_the_agentic_gcp_branch_is_labelled_the_same_way():
    """Same defect, same function — fixed together. This one keeps 'medium' because it rests on a
    real technical-fit argument (Vertex AI/BigQuery/Gemini), not on an assumed footprint."""
    c = _cloud("Build an agentic multi-step research assistant with tool use over internal data.")
    assert c["v"] == "Google Cloud (GCP)"
    assert "mentioned" not in c["why"].lower(), c["why"]
    assert "no cloud provider named" in c["why"].lower(), c["why"]


def test_an_explicit_cloud_still_beats_the_enterprise_inference():
    """Ordering regression guard: the detection branches must stay above the inference ones."""
    assert _cloud("Large regulated enterprise on AWS with audit logging.")["v"] == "AWS"
