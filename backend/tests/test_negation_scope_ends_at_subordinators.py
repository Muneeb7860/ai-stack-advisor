"""A negation stops at the subordinator that starts a new clause.

Found by running a real agentic-platform requirements document through the engine. It says:

    REQ-7.3: Air-gapped operation: no internet connectivity required after initial container pull

The negation regex captures up to 300 characters after "no" and matches any category term in that
span, so "container" — eight words later, in a clause that exists to say containers ARE pulled —
excluded the whole containers category at high confidence. The engine reported dockerMentioned and
excluded["containers"] as true at the same time, suppressed the orchestrator vendor pick, and told
a document that specifies Kubernetes deployment that it had ruled out containers.

NEGATION_CLAUSE_END already implemented exactly this idea and carried the reasoning for it — stop
at a sentence end or at a subordinating/contrasting conjunction, so "...but we do need Postgres" is
not swept in. The list was simply incomplete: it had "while" but not "after", "once", "until",
"unless", "when", "before", "whenever", "upon" or "following", which are the same family.

The same list appears in PASSIVE_NEGATION_PREFIX and must stay identical in both. A subordinator
that ends an active-voice negation has to end a passive one too, or "no X after Y" and "X must not
be used after Y" disagree about the same sentence.
"""
import pytest

from app.rule_engine import detect_signals


def _excluded(text):
    return detect_signals(text).get("excluded") or {}


REPORTED = "REQ-7.3: Air-gapped operation: no internet connectivity required after initial container pull"


# ------------------------------------------------- the negation must not reach past the boundary

def test_the_reported_clause_does_not_exclude_containers():
    assert "containers" not in _excluded(REPORTED), _excluded(REPORTED)


def test_the_document_no_longer_contradicts_itself():
    """dockerMentioned and excluded["containers"] were both true. Whatever else is arguable, a
    document cannot be simultaneously using and refusing the same category."""
    s = detect_signals(REPORTED + " Docker images are pulled once at install time.")
    assert s["dockerMentioned"] is True
    assert "containers" not in (s.get("excluded") or {})


@pytest.mark.parametrize("text,term", [
    ("No downtime once the database migration completes.", "database"),
    ("No manual steps before the Kubernetes rollout.", "kubernetes"),
    ("No further approvals unless the cache layer changes.", "cache"),
    ("No egress until the observability stack is in place.", "observability"),
])
def test_a_term_after_a_subordinator_is_outside_the_negation(text, term):
    assert term not in _excluded(text), f"{text!r} -> {_excluded(text)}"


# --------------------------------------------------------- terms BEFORE the boundary still count

@pytest.mark.parametrize("text,expected", [
    ("We do not want Kubernetes or Docker after the migration.", {"kubernetes", "containers"}),
    ("No cloud until we have revenue.", {"cloud"}),
    ("Avoid Kafka when traffic is low.", {"messaging"}),
])
def test_the_real_exclusion_before_the_boundary_survives(text, expected):
    assert expected <= set(_excluded(text)), f"{text!r} -> {_excluded(text)}"


def test_the_comma_list_case_this_boundary_was_originally_written_for():
    """NEGATION_CLAUSE_END exists because stopping at the first comma truncated this sentence after
    'website'. Extending the list must not re-break it."""
    got = set(_excluded("I do not need a website, API, database, cloud, or a vector database."))
    assert {"frontend", "api", "database", "cloud", "rag"} <= got, got


def test_passive_voice_uses_the_same_boundary():
    """The two constants carry the same word list on purpose; this fails if they drift apart.

    Constructing this took two attempts. PASSIVE_NEGATION_PREFIX scans BACKWARD from the negation
    phrase, so a term placed after it is never in scope and the first version of this test passed
    whether the constants matched or not — it proved nothing. The term has to sit before the
    subordinator, and the phrase has to be one PASSIVE_NEGATION_PHRASES actually lists.

    With the lists aligned this yields {observability}; with the passive prefix left behind it
    yields {kubernetes, observability}, sweeping in a technology the sentence says is in use.
    """
    assert "kubernetes" in _excluded("Kubernetes must not be used.")
    got = _excluded("We standardised on Kubernetes after Datadog is not allowed.")
    assert "observability" in got, got
    assert "kubernetes" not in got, got
