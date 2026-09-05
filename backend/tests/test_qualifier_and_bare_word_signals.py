"""Three over-matches found by running two real documents through the engine.

All three are the same failure: a word that means one thing in a requirement and something else in
ordinary prose, matched without the context that separates them. The engine already had two
qualifier mechanisms for exactly this (_QUANTITY_QUALIFIER_RE, _CONTAINMENT_DESTINATION_RE) and two
prior bare-word fixes (`mvp`, `ai`); these extend the same pattern rather than inventing one.

1. "(no outbound API calls required)" excluded the API category, deleting the gateway card from a
   document describing an API product. The negation does target "API calls" — but `outbound` scopes
   it to a DIRECTION of traffic. The requirement is "we make no calls out", not "we expose no API".

2. `search` fired on the bare word "recommendation", so a design document containing
   "**Recommendation:** A as primary" was classified as a search/recommender product.

3. `globalMultiRegion` fired on the bare word "global", so "Per tenant | Global check rate" in a
   rate-limiting table made a single-region product look geographically distributed — and that
   signal drives four cost and trade-off branches.
"""
import pytest

from app.rule_engine import detect_signals


def _excluded(text):
    return detect_signals(text).get("excluded") or {}


# ------------------------------------------------------------------ direction is not a category

@pytest.mark.parametrize("text", [
    "All LLM inference routes through local Ollama (no outbound API calls required).",
    "No external API calls from the worker tier.",
    "No third-party API dependencies at runtime.",
    "No inbound webhooks from the payment provider.",
])
def test_a_direction_scoped_negation_does_not_exclude_the_category(text):
    assert "api" not in _excluded(text), f"{text!r} -> {_excluded(text)}"


def test_public_is_not_a_directional_qualifier():
    """The risk this fix had to avoid. "no public cloud" is a real, common exclusion of the cloud
    category — if `public` had been added to the qualifier list it would have stopped working, and
    on-prem detection with it."""
    assert _excluded("No public cloud — everything runs in our own data centre.").get("cloud") is True


@pytest.mark.parametrize("text,key", [
    ("We do not need an API for the pilot.", "api"),
    ("No database, no cache.", "database"),
    ("Kubernetes must not be used.", "kubernetes"),
])
def test_an_unqualified_exclusion_still_registers(text, key):
    assert _excluded(text).get(key) is True, f"{text!r} -> {_excluded(text)}"


# ------------------------------------------------------------------------- bare-word over-match

@pytest.mark.parametrize("text", [
    "**Recommendation:** A as primary. Enterprise integrators already hold the ID.",
    "Our recommendation is to use verification IDs rather than phone numbers.",
])
def test_making_a_recommendation_is_not_building_a_recommender(text):
    assert detect_signals(text)["search"] is False, text


@pytest.mark.parametrize("text", [
    "Build an e-commerce recommendation engine.",
    "We need a recommendation system for the product catalogue.",
    "Semantic search over internal documents.",
])
def test_a_real_search_or_recommender_product_still_fires(text):
    assert detect_signals(text)["search"] is True, text


@pytest.mark.parametrize("text", [
    "| Per tenant | Global check rate | Runaway client, credential compromise |",
    "A global rate limit protects the shared pool.",
])
def test_the_word_global_alone_is_not_multi_region(text):
    assert detect_signals(text)["globalMultiRegion"] is False, text


@pytest.mark.parametrize("text", [
    "We serve global users across three continents.",
    "Multi-region active-active deployment.",
    "Our audience is worldwide.",
    "An international customer base with data-residency requirements.",
    "The service is globally distributed.",
])
def test_genuine_geographic_distribution_still_fires(text):
    assert detect_signals(text)["globalMultiRegion"] is True, text
