"""A rule about where a secret must NOT go is not a rejection of the place.

Found by running a real OTP-verification design document through the engine. §6 of that document
says "The code must not appear in any observability surface" — a security requirement that secrets
stay out of logs — and the engine deleted the Observability card at HIGH confidence, reporting
"Not recommended — you excluded an observability vendor" to a document whose §8 separately requires
record retention for "Reporting, disputes, audit".

The phrasing that gave the tool more security information produced the less secure recommendation.
That is the same shape as the NON_EXCLUSION_QUALIFIERS bug ("not only a website" deleting the
Frontend card), and it is worse here because the deletion is silent and the category is one an
auditor would ask about.

The grammar: in "must not <verb> in <X>", the prohibited subject sits BEFORE the verb ("the code")
and X is a DESTINATION, not the thing being declined. The check reads the text immediately before
the matched term rather than the start of the clause, because that is where the qualifying words
sit — the same reason _QUANTITY_QUALIFIER_RE is anchored that way.

Deliberately conservative in the same direction as the existing qualifiers: where a phrase is
genuinely ambiguous ("must not be stored in Redis" could mean either), not excluding is the cheaper
error. An unwanted recommendation is visible on the page; a silently deleted card is not.
"""
import pytest

from app.rule_engine import detect_signals


def _excluded(text):
    return detect_signals(text).get("excluded") or {}


# --------------------------------------------------- containment: a destination, not a rejection

@pytest.mark.parametrize("text", [
    "The code must not appear in any observability surface.",
    "Secrets must not be logged to Datadog.",
    "The token must never be written to the database.",
    "PII must not be stored in the cache.",
    "Credentials must not be sent to any monitoring vendor.",
    "The plaintext code must not be included in the API response.",
    "Card numbers must never be recorded in Splunk.",
])
def test_a_destination_is_not_an_exclusion(text):
    assert _excluded(text) == {}, f"{text!r} wrongly excluded {_excluded(text)}"


def test_the_reported_document_sentence_verbatim():
    """The exact sentence from the design document that produced the bug."""
    assert _excluded(
        "**Never store or return the plaintext code.** Hashed at rest, and absent from every API "
        "response, log line, trace, and error message. The code must not appear in any "
        "observability surface."
    ) == {}


# ------------------------------------------------------------- genuine rejections still register

@pytest.mark.parametrize("text,key", [
    ("We do not want an observability vendor.", "observability"),
    ("No monitoring tooling — we will not buy Datadog.", "observability"),
    ("Avoid Splunk entirely.", "observability"),
    ("Build it without a cache.", "cache"),
    ("We don't need a database.", "database"),
    ("No Kubernetes.", "kubernetes"),
])
def test_a_real_exclusion_is_still_detected(text, key):
    """Over-correcting would be the worse bug: this mechanism exists to stop the engine
    recommending things the user ruled out, and silently disabling it fails open."""
    assert _excluded(text).get(key) is True, f"{text!r} produced {_excluded(text)}"
