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
import re
from pathlib import Path

import pytest

from app.rule_engine import detect_signals

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"


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


# ------------------------------------------------------------ a tool mention is not a hosting choice
# Fourth instance of the same failure class: bare "docker"/"kubernetes"/"k8s" in the selfHostInfra
# term list is a substring match, so naming the technology set the signal regardless of who operates
# it. But managed Kubernetes (GKE/EKS) and containerization (Docker on Fargate) are the OPPOSITE of
# self-hosting infrastructure, and "Kubernetes is not an option" across a sentence boundary survives
# negation-stripping as a bare mention. selfHostInfra gates the sensitive-data branch and the
# startup-MVP branch of pick_runtime, so this changed recommendations, not just signal bookkeeping.
# The genuine self-host terms (own gpu/servers/infrastructure/hardware, self-hosted, ollama) must
# still set it — the fix narrows the three tool names, it does not remove the signal.
def _self_host(text):
    return detect_signals(text).get("selfHostInfra")


@pytest.mark.parametrize("text", [
    "We deploy to managed GKE; Kubernetes handles our orchestration.",
    "Our app is containerized with Docker and runs on AWS Fargate.",
    "Kubernetes is not an option for us.",
    "The team has never used Kubernetes.",
    "We use Docker Compose locally but deploy to Cloud Run.",
])
def test_naming_a_container_tool_does_not_assert_self_hosting(text):
    assert not _self_host(text), f"{text!r} wrongly set selfHostInfra -> {detect_signals(text).get('selfHostInfra')}"


@pytest.mark.parametrize("text", [
    "We self-host everything on our own GPUs.",
    "Runs on our own hardware inside the data center.",
    "All inference is local via Ollama on our own servers.",
    "We run our own infrastructure end to end.",
    "Self-hosted Kubernetes on our own bare-metal servers.",   # tool name + genuine self-host verb
])
def test_genuine_self_hosting_still_sets_the_signal(text):
    assert _self_host(text), f"{text!r} should set selfHostInfra but did not"


# ------------------------------------------------ a branch's rationale must not cite its own dead trigger
# When selfHostInfra stopped firing on bare "docker"/"kubernetes", the pick_runtime branch it gates
# still justified itself with "your existing Docker/Kubernetes infrastructure" / "(Docker/K8s in the
# stack)" — evidence that, post-fix, specifically no longer triggers it. Nothing pinned the string, so
# the signal-and-prose contradiction was invisible to the suite. These tie the rationale to a genuine
# triggering input so the two can't drift apart again.
from app.rule_engine import recommend_stack


def _runtime(text):
    r = recommend_stack(text)["recommendations"]
    return r.get("llm_runtime") or r.get("runtime") or {}


def test_self_host_sensitive_runtime_still_fires_on_a_real_self_host_signal():
    rt = _runtime("We self-host on our own GPU servers and handle HIPAA-regulated patient data.")
    assert "Ollama" in rt["rec"]
    assert rt["conf"] == "high"


def test_that_runtime_rationale_does_not_cite_bare_container_tools_as_its_trigger():
    # The branch is reached by a self-hosting posture, not by naming Docker/K8s — which no longer
    # sets selfHostInfra on their own. The rationale must not claim otherwise.
    rt = _runtime("We self-host on our own GPU servers and handle HIPAA-regulated patient data.")
    why = rt["why"].lower()
    assert "docker/k8s" not in why and "docker/kubernetes" not in why, (
        f"rationale cites container tools its trigger no longer keys on: {rt['why']!r}"
    )


def test_naming_docker_kubernetes_without_a_self_host_verb_does_not_reach_that_branch():
    # The exact contradiction: production Docker/K8s mention, sensitive data, but no self-host verb.
    # Post-fix this must NOT land the "you already self-host" runtime rec.
    rt = _runtime("We run Docker and Kubernetes in production today and process PII under GDPR.")
    assert "on the infrastructure you already run" not in rt.get("rec", "")


# ------------------------------------------------------------------ "live" is two different words
# realtime held a bare "live" and has() does not anchor, so every word containing those four
# letters set a latency signal: "delivery", "deliver", "deliverables", "olive". Found by the QA
# matrix's unexpected-signal check on its first run, on "scaled agile framework delivery
# coordination" — a phrase about sprint process in a scenario with no latency requirement at all.
#
# Word boundaries alone are not enough. "We go live in March" is a launch date, and the launch
# sense is what "live" usually means when it is not attached to a noun like map or leaderboard,
# so it would have replaced one silent false positive with a commoner one.
def _realtime(text):
    return detect_signals(text).get("realtime")


@pytest.mark.parametrize("text", [
    "Scaled agile framework delivery coordination across squads.",
    "Reliable delivery of order confirmation emails.",
    "An olive oil marketplace for small producers.",
    "Deliverables for the next sprint are agreed.",
    "We go live in March with the first cohort.",
    "The platform went live last year.",
    "Planning our go-live date with the client.",
])
def test_the_word_live_inside_another_word_is_not_a_latency_requirement(text):
    assert not _realtime(text), f"{text!r} wrongly set realtime"


@pytest.mark.parametrize("text", [
    "Live leaderboards and live scoring for concurrent players.",
    "A live map showing every vehicle position.",
    "Push live updates to the client as they happen.",
    "Real-time multiplayer with sub-100ms response.",
    "Streaming analytics over the event bus.",
    "The dashboard must be low latency under load.",
])
def test_a_genuine_latency_requirement_still_sets_realtime(text):
    assert _realtime(text), f"{text!r} should set realtime but did not"


def test_both_engines_agree_on_the_live_boundary():
    """The JS twin is a regex literal, where `\\\\b` means a literal backslash rather than a word
    boundary — a double-escape that works perfectly in Python and silently does nothing in the
    browser. That exact mistake shipped once in this repo already, so the source is asserted
    rather than assumed."""
    js = INDEX_HTML.read_text(encoding="utf-8")
    m = re.search(r"const LIVE_REALTIME_RE = /(.+?)/i;", js)
    assert m, "LIVE_REALTIME_RE not found in index.html"
    assert "\\\\b" not in m.group(1), (
        "the JS regex is double-escaped: \\\\b is a literal backslash, not a word boundary"
    )
    assert m.group(1).endswith(r"\blive\b")
    assert "realtime: has(['real-time','real time','low latency','streaming'])" in js, (
        "bare 'live' is back in the JS realtime term list"
    )
