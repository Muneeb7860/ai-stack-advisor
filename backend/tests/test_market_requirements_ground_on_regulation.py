"""A requirement that names a market must ground on the regulatory section, not around it.

Found by running the eval harness's own r01-india-otp-verify case through the advisor. The rule
engine produced a competent stack (AWS, Spring Boot, Postgres, serverless) and said nothing about
DLT registration, template pre-approval or transactional category — the things that decide whether
the product can send a single message. That part is a known gap: doc 19 is Status "target design".

The retrieval half was the fixable part, and it failed in a specific, generalisable way. A
requirement states its geography in plain language ("for Indian businesses") and its technology in
jargon ("OTP", "send-code", "REST API"), so the technical sections legitimately out-rank the
regulatory one whenever the requirement is technically dense. Measured on r01, the regulatory
chunk ranked 4th behind the verification ladder, anti-patterns and sender strategy — so a top_k of
3 handed the model three true-but-secondary chunks and cut the only one that changes the answer.

Two changes were made together and are asserted together here, because either alone leaves the
case failing: doc 19 §E gained plain-language market vocabulary, and GROUNDING_TOP_K went 3 -> 5.

When this was written, a plain-language US-market query still returned zero results and this
docstring said so, deliberately refusing to assert a fix that had not been made. That abstention
was a separate defect in retrieval.py's gate — it read peak fused RRF, which encodes rank
agreement rather than relevance — and has since been fixed by replacing it with a top-1 cosine
gate (MIN_CONFIDENT_COSINE). The US case is now asserted below, because it now works.
"""
import pytest

from app.retrieval import retrieve
from app.routers.refine import GROUNDING_SCORE_THRESHOLD, GROUNDING_TOP_K

from ollama_gate import requires_ollama


def _grounded(query):
    return [h for h in retrieve(query, top_k=GROUNDING_TOP_K) if h["score"] >= GROUNDING_SCORE_THRESHOLD]


INDIA_OTP = (
    "We are launching an OTP verification API for Indian businesses. MVP is send-code and "
    "check-code over SMS, with a REST API and a dashboard. Target customers are fintech and "
    "e-commerce companies. We plan to launch in eight weeks on AWS Mumbai with a Spring Boot backend."
)


@requires_ollama
def test_a_market_naming_requirement_grounds_on_the_regulatory_section():
    """The reported failure, as an assertion. This chunk was rank 4 and cut at top_k=3."""
    headers = [str(h["header"]) for h in _grounded(INDIA_OTP)]
    assert any("Regulatory" in h for h in headers), (
        f"the binding constraint was not grounded; got: {headers}"
    )


@requires_ollama
@pytest.mark.parametrize("requirement", [
    "Rolling out transactional SMS notifications to users in Germany and France for our marketplace.",
    "We plan to launch an SMS verification product for businesses in Brazil.",
])
def test_market_vocabulary_generalises_beyond_the_case_it_was_written_for(requirement):
    """Brazil is named in doc 19 only as a market it explicitly does NOT cover in detail, and the
    EU query shares no wording with the India case. Both had to improve without the document
    being written around either probe, or the change is overfitting rather than a fix."""
    headers = [str(h["header"]) for h in _grounded(requirement)]
    assert any("Regulatory" in h for h in headers), f"got: {headers}"


@requires_ollama
@pytest.mark.parametrize("query,expected", [
    ("how do we stop SMS pumping and AIT fraud on our signup flow", "Fraud"),
    ("should we use silent network authentication or push approval instead of SMS codes", "verification ladder"),
    ("we want to run our own SMSC and hold direct carrier interconnects", "Buy versus build"),
])
def test_technical_queries_still_reach_their_own_section(query, expected):
    """The regulatory section must not become a sink. Each of these ranked 1st before the change
    and must still be grounded after it — over-boosting §E would be the quieter, worse bug."""
    headers = [str(h["header"]) for h in _grounded(query)]
    assert any(expected.lower() in h.lower() for h in headers), f"got: {headers}"


@requires_ollama
def test_an_off_domain_query_still_leaves_the_communications_document():
    """Doc 19 is large and keyword-dense; a corpus-wide regression would show up here first."""
    docs = {h["doc"] for h in retrieve("which database for a multi-tenant SaaS with strict tenant isolation", top_k=3)}
    assert "05-multi-tenant-saas.md" in docs, docs


@requires_ollama
def test_a_plain_language_us_market_query_now_retrieves():
    """Was zero hits until the abstention gate was replaced. Kept as its own test, separate from
    the market-vocabulary ones above, because it failed for a different reason: not ranking, but a
    gate that refused the query outright before ranking ran."""
    hits = retrieve("We want to send SMS one-time passcodes to customers across the United States.", top_k=3)
    assert hits, "the US-market query returned nothing"
    assert any(h["doc"] == "19-cpaas-communications.md" for h in hits), [h["doc"] for h in hits]
