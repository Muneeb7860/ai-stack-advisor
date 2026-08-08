"""
Retrieval eval harness — TEMPLATE, not wired to a real retrieval function yet.

This is deliberately a loud placeholder, same convention as `app/mcp/server.py`'s
NotImplementedError-at-import stub in the backend: it's meant to fail obviously and immediately if
run as-is, not silently pass or silently do nothing. Once `/api/refine` (or whatever internal
function performs the retrieval step) exists, copy this file into `backend/tests/`, wire up
`retrieve()` below to call that real function, and delete this module-level guard.

What this tests: retrieval quality specifically (does the right document/chunk come back for a
given query), not generation quality (does the LLM's final answer read well). Keep those separate —
a retrieval bug and a prompting bug look identical from the outside ("the answer was wrong") but
need completely different fixes, and this harness exists so you can tell them apart.

See RETRIEVAL-EVAL-SET.md for full rationale per case, and eval_cases.json for the case data this
script loads. Both live in docs/use-case-knowledge-base/ alongside the corpus itself.

Usage once wired up:
    pytest docs/use-case-knowledge-base/test_retrieval_eval.py -v
    # or, after copying into backend/tests/:
    pytest tests/test_retrieval_eval.py -v
"""
import json
import os

import pytest

EVAL_CASES_PATH = os.path.join(os.path.dirname(__file__), "eval_cases.json")


def load_cases():
    with open(EVAL_CASES_PATH) as f:
        data = json.load(f)
    return data["cases"]


def retrieve(query: str, top_k: int = 5):
    """
    PLACEHOLDER — replace with a call into the real retrieval step once it exists.

    Expected return shape: a list of dicts, ranked by relevance, each with at least:
        {"doc": "01-realtime-collaborative-editing.md", "chunk_text": "...", "score": 0.83}

    Until this is wired up, every test in this file is skipped (not failed, not silently passed) —
    see the `pytest.mark.skip` on each test function below. Do not remove the skip marks without
    actually wiring this function up first; a version of this file that "passes" without a real
    retrieve() implementation is worse than no test at all, because it looks like coverage that
    doesn't exist.
    """
    raise NotImplementedError(
        "retrieve() is a template — wire it up to the real /api/refine retrieval step "
        "(or whatever internal function performs retrieval) before removing the skip marks below."
    )


CASES = load_cases()
DIRECT_CASES = [c for c in CASES if c["section"] == "direct"]
ANTI_PATTERN_CASES = [c for c in CASES if c["section"] == "anti_pattern"]
CROSS_DOC_CASES = [c for c in CASES if c["section"] == "cross_document"]
BOUNDARY_CASES = [c for c in CASES if c["section"] == "boundary"]
NEGATIVE_CASES = [c for c in CASES if c["section"] == "negative_control"]


@pytest.mark.skip(reason="retrieve() not wired up yet — see module docstring")
@pytest.mark.parametrize("case", DIRECT_CASES, ids=[str(c["id"]) for c in DIRECT_CASES])
def test_direct_retrieval(case):
    """Section 1: unambiguous queries — top-1 result must be the expected doc."""
    results = retrieve(case["query"], top_k=case["top_k_pass"])
    top_docs = [r["doc"] for r in results[: case["top_k_pass"]]]
    for expected in case["expected_docs"]:
        assert expected in top_docs, (
            f"Case {case['id']}: expected '{expected}' in top-{case['top_k_pass']}, "
            f"got {top_docs}"
        )


@pytest.mark.skip(reason="retrieve() not wired up yet — see module docstring")
@pytest.mark.parametrize("case", ANTI_PATTERN_CASES, ids=[str(c["id"]) for c in ANTI_PATTERN_CASES])
def test_anti_pattern_retrieval(case):
    """Section 2: 'is X okay?' phrasing must retrieve the anti-patterns section specifically,
    not just any chunk from the right document — check expected_chunk_contains, not just doc match."""
    results = retrieve(case["query"], top_k=case["top_k_pass"])
    top_docs = [r["doc"] for r in results[: case["top_k_pass"]]]
    for expected in case["expected_docs"]:
        assert expected in top_docs, f"Case {case['id']}: expected doc missing from results"
    matched_chunks = [r["chunk_text"] for r in results if r["doc"] in case["expected_docs"]]
    combined_text = " ".join(matched_chunks).lower()
    for phrase in case.get("expected_chunk_contains", []):
        assert phrase.lower() in combined_text, (
            f"Case {case['id']}: expected phrase '{phrase}' not found in retrieved chunks — "
            f"the right doc came back but not the anti-pattern section itself"
        )


@pytest.mark.skip(reason="retrieve() not wired up yet — see module docstring")
@pytest.mark.parametrize("case", CROSS_DOC_CASES, ids=[str(c["id"]) for c in CROSS_DOC_CASES])
def test_cross_document_retrieval(case):
    """Section 3: queries that legitimately need two documents — both must come back."""
    results = retrieve(case["query"], top_k=case["top_k_pass"])
    top_docs = {r["doc"] for r in results[: case["top_k_pass"]]}
    for expected in case["expected_docs"]:
        assert expected in top_docs, (
            f"Case {case['id']}: cross-document query only returned {top_docs}, "
            f"missing '{expected}'"
        )


@pytest.mark.skip(reason="retrieve() not wired up yet — see module docstring")
@pytest.mark.parametrize("case", BOUNDARY_CASES, ids=[str(c["id"]) for c in BOUNDARY_CASES])
def test_boundary_retrieval(case):
    """Section 4: retrieval should land close to the specific decision point, not just the
    right file — check expected_chunk_contains against the matched chunk text."""
    results = retrieve(case["query"], top_k=case["top_k_pass"])
    top_docs = [r["doc"] for r in results[: case["top_k_pass"]]]
    for expected in case["expected_docs"]:
        assert expected in top_docs, f"Case {case['id']}: expected doc missing from results"
    matched_chunks = [r["chunk_text"] for r in results if r["doc"] in case["expected_docs"]]
    combined_text = " ".join(matched_chunks).lower()
    for phrase in case.get("expected_chunk_contains", []):
        assert phrase.lower() in combined_text, (
            f"Case {case['id']}: right doc, but expected phrase '{phrase}' not in matched chunk — "
            f"retrieval may have landed on the wrong decision point within the file"
        )


@pytest.mark.skip(reason="retrieve() not wired up yet — see module docstring")
@pytest.mark.parametrize("case", NEGATIVE_CASES, ids=[str(c["id"]) for c in NEGATIVE_CASES])
def test_negative_controls(case):
    """Section 5: out-of-scope queries should NOT produce a confident match — checks that the
    system has (or should have) a relevance threshold rather than always forcing a top-K result."""
    results = retrieve(case["query"], top_k=5)
    # Adjust this threshold to whatever your retrieval step treats as "confident enough to cite."
    CONFIDENCE_THRESHOLD = 0.5
    high_confidence_hits = [r for r in results if r.get("score", 0) >= CONFIDENCE_THRESHOLD]
    assert not high_confidence_hits, (
        f"Case {case['id']}: expected no high-confidence match for an out-of-scope query, "
        f"got {high_confidence_hits} — check whether a relevance threshold is applied at all"
    )
