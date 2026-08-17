"""
Retrieval eval suite — wired to the real retrieval implementation (app/retrieval.py).

Ported from docs/use-case-knowledge-base/test_retrieval_eval.py, the original loud-placeholder
template (same convention as app/mcp/server.py's old NotImplementedError-at-import stub) —
that file's retrieve() function raised NotImplementedError and every test was skip-marked on
purpose, "until /api/refine's retrieval step exists." It now does; this is that wiring.

What this tests: retrieval quality specifically (does the right document/chunk come back for a
given query), not generation quality (does the LLM's final answer read well) — kept separate
on purpose, per the original template's own rationale, since a retrieval bug and a prompting
bug look identical from the outside but need different fixes.

See docs/use-case-knowledge-base/RETRIEVAL-EVAL-SET.md for full per-case rationale, and
eval_cases.json (copied alongside this file) for the case data. No live Postgres needed —
retrieval is pure functions over the corpus, no DB access.
"""
import json
import os

import pytest

from app.retrieval import retrieve

EVAL_CASES_PATH = os.path.join(os.path.dirname(__file__), "eval_cases.json")


def load_cases():
    with open(EVAL_CASES_PATH) as f:
        data = json.load(f)
    return data["cases"]


CASES = load_cases()
DIRECT_CASES = [c for c in CASES if c["section"] == "direct"]
ANTI_PATTERN_CASES = [c for c in CASES if c["section"] == "anti_pattern"]
CROSS_DOC_CASES = [c for c in CASES if c["section"] == "cross_document"]
BOUNDARY_CASES = [c for c in CASES if c["section"] == "boundary"]
NEGATIVE_CASES = [c for c in CASES if c["section"] == "negative_control"]

# --- Status history, real per-case numbers each time, not assumed or eyeballed off aggregate
# pass/fail counts (see app/retrieval.py's module docstring for the full narrative):
#
#   1. TF-IDF (pre-migration, commit 9cd8b48):
#        21 passed, 1 xfailed (case 21), 1 xpassed (case 15) / 23 tests.
#      Case 15 was marked xfail (expected paraphrase-gap failure per
#      RETRIEVAL-PROTOTYPE-FINDINGS.md) but actually XPASSED — TF-IDF already retrieved it
#      correctly at the time, the xfail marker was just stale/pessimistic, not a real failure.
#
#   2. Pure embeddings (commit 5c01dc1/280bed8, ChromaDB + nomic-embed-text, no lexical
#      signal): 20 passed, 3 xfailed (cases 7, 20, 21), 0 xpassed / 23 tests.
#      A later review's aggregate-count math ("before 22 correct, after 20 correct, net -2")
#      was right on the arithmetic but wrong on the story it told from it ("fixed 1, cost 3,
#      net -2, including an xpass-to-xfail flip"): re-deriving this directly from a real
#      worktree re-run at each commit shows NO case ever transitioned xpass->xfail. What
#      actually happened, case by case: case 15 went from "xfail-marked but passing" to
#      "unmarked and passing" (a label correction, not a behavior change — it was never
#      actually broken) while cases 7 and 20 are the only two GENUINE new regressions (correct
#      under TF-IDF, wrong under pure embeddings); case 21 was broken before the migration too
#      and stayed broken (unchanged, not a regression). Net correct-count effect: 2 real
#      regressions, 0 real fixes, 1 relabeling — same -2 net number as the aggregate math, a
#      different (and less flattering) explanation than "fixed 1, broke 3."
#      Case 7 (direct: fraud-scoring model query): 06-two-sided-marketplace.md's "Trust &
#      safety pipeline" section scored higher under embeddings (content=0.744) than the
#      correct doc's own content score (07-ml-feature-store..., content=0.654) — a genuine
#      semantic-neighbor confusion (not a paraphrase gap) that TF-IDF never had a chance to
#      make since "trust & safety" and "fraud-scoring model" share almost no exact tokens.
#      Case 20 (negative control: CI/CD/Kubernetes query): top score (~0.60-0.65) sat ABOVE
#      the lowest genuine direct-hit score (~0.59) — cosine similarity's narrower/higher score
#      band doesn't separate cleanly at a threshold tuned for TF-IDF's wider spread.
#
#   3. Hybrid retrieval (current — embeddings + BM25 lexical, fused via Reciprocal Rank
#      Fusion, see app/retrieval.py's module docstring): 20 passed, 1 xfailed (case 21),
#      2 xpassed (cases 7, 20) / 23 tests.
#      Case 7: FIXED — BM25's routing/content signal (Signals/triggers chunks are literally
#      keyword-dense, exactly what BM25 is built for) gives doc 07 enough of a lexical edge
#      that RRF fusion flips the blended rank without needing to over-weight routing globally.
#      Case 20: FIXED, but not by reordering alone — its top RRF-fused CONTENT score (0.0281)
#      sits measurably below every genuine-hit case's peak fused score (>=0.0323 out of a
#      ~0.0328 ceiling), a real, measured gap that raw embedding cosine similarity (what
#      `score` still reports, unchanged, for threshold compatibility elsewhere — see
#      retrieve()'s docstring) never had. app/retrieval.py's MIN_CONFIDENT_RRF abstention gate
#      uses that fused-confidence gap to return [] for this query outright, rather than
#      serving a guess. See that constant's own comment for the exact numbers.
#      Case 21: STILL xfailed, unchanged since before the embeddings migration even started —
#      its peak fused RRF score (0.0320) sits inside the same margin as genuine hits, not
#      reliably separable by this gate either. This is the one case, across the whole history
#      above, that hybrid retrieval was not able to recover — consistent with its
#      long-documented conclusion that it needs a learned reranker, not a threshold (lexical,
#      embedding, or fused).
KNOWN_XFAIL_IDS = {21}

_XFAIL_REASONS = {
    21: "Documented limitation across TF-IDF, pure embeddings, AND hybrid RRF retrieval: this "
        "false positive's confidence (by raw score under either single-signal approach, and "
        "by peak fused RRF score under hybrid) sits inside the same margin as genuine weak "
        "hits, not reliably separable by any of the three approaches tried on this corpus. "
        "Needs a learned reranker to fix properly, not a threshold tweak — see the file-level "
        "comment above and app/retrieval.py's MIN_CONFIDENT_RRF for the real numbers.",
}


def _apply_known_xfail(case):
    if case["id"] in KNOWN_XFAIL_IDS:
        return pytest.param(case, marks=pytest.mark.xfail(reason=_XFAIL_REASONS[case["id"]], strict=False))
    return case


def _normalize_dashes(text: str) -> str:
    """Markdown source uses typographic en-dashes (–) in ranges like '3–5 participants'; some
    eval-case expected_chunk_contains phrases were written with a plain ASCII hyphen ('3-5').
    Normalizing both sides before comparison is a legitimate robustness fix — the underlying
    retrieval already found the correct chunk in this case; only the literal-string
    dash-character comparison was too strict."""
    return text.replace("–", "-").replace("—", "-")


@pytest.mark.parametrize("case", [_apply_known_xfail(c) for c in DIRECT_CASES], ids=[str(c["id"]) for c in DIRECT_CASES])
def test_direct_retrieval(case):
    """Section 1: unambiguous queries — top-1 result must be the expected doc."""
    results = retrieve(case["query"], top_k=case["top_k_pass"])
    top_docs = [r["doc"] for r in results[: case["top_k_pass"]]]
    for expected in case["expected_docs"]:
        assert expected in top_docs, (
            f"Case {case['id']}: expected '{expected}' in top-{case['top_k_pass']}, "
            f"got {top_docs}"
        )


@pytest.mark.parametrize("case", ANTI_PATTERN_CASES, ids=[str(c["id"]) for c in ANTI_PATTERN_CASES])
def test_anti_pattern_retrieval(case):
    """Section 2: 'is X okay?' phrasing must retrieve the anti-patterns section specifically,
    not just any chunk from the right document."""
    results = retrieve(case["query"], top_k=case["top_k_pass"])
    top_docs = [r["doc"] for r in results[: case["top_k_pass"]]]
    for expected in case["expected_docs"]:
        assert expected in top_docs, f"Case {case['id']}: expected doc missing from results"
    matched_chunks = [r["chunk_text"] for r in results if r["doc"] in case["expected_docs"]]
    combined_text = _normalize_dashes(" ".join(matched_chunks).lower())
    for phrase in case.get("expected_chunk_contains", []):
        assert _normalize_dashes(phrase.lower()) in combined_text, (
            f"Case {case['id']}: expected phrase '{phrase}' not found in retrieved chunks — "
            f"the right doc came back but not the anti-pattern section itself"
        )


@pytest.mark.parametrize("case", [_apply_known_xfail(c) for c in CROSS_DOC_CASES], ids=[str(c["id"]) for c in CROSS_DOC_CASES])
def test_cross_document_retrieval(case):
    """Section 3: queries that legitimately need two documents — both must come back."""
    results = retrieve(case["query"], top_k=case["top_k_pass"])
    top_docs = {r["doc"] for r in results[: case["top_k_pass"]]}
    for expected in case["expected_docs"]:
        assert expected in top_docs, (
            f"Case {case['id']}: cross-document query only returned {top_docs}, "
            f"missing '{expected}'"
        )


@pytest.mark.parametrize("case", BOUNDARY_CASES, ids=[str(c["id"]) for c in BOUNDARY_CASES])
def test_boundary_retrieval(case):
    """Section 4: retrieval should land close to the specific decision point, not just the
    right file."""
    results = retrieve(case["query"], top_k=case["top_k_pass"])
    top_docs = [r["doc"] for r in results[: case["top_k_pass"]]]
    for expected in case["expected_docs"]:
        assert expected in top_docs, f"Case {case['id']}: expected doc missing from results"
    matched_chunks = [r["chunk_text"] for r in results if r["doc"] in case["expected_docs"]]
    combined_text = _normalize_dashes(" ".join(matched_chunks).lower())
    for phrase in case.get("expected_chunk_contains", []):
        assert _normalize_dashes(phrase.lower()) in combined_text, (
            f"Case {case['id']}: right doc, but expected phrase '{phrase}' not in matched chunk — "
            f"retrieval may have landed on the wrong decision point within the file"
        )


@pytest.mark.parametrize("case", [_apply_known_xfail(c) for c in NEGATIVE_CASES], ids=[str(c["id"]) for c in NEGATIVE_CASES])
def test_negative_controls(case):
    """Section 5: out-of-scope queries should NOT produce a confident match. Threshold tuned
    to app/retrieval.py's actual score scale (TF-IDF cosine similarity over this corpus size —
    see the research prototype's own 0.15 threshold on a comparable single-stage setup); this
    is NOT the eval template's placeholder 0.5, which assumed an unspecified scoring scale."""
    results = retrieve(case["query"], top_k=5)
    CONFIDENCE_THRESHOLD = 0.15
    high_confidence_hits = [r for r in results if r.get("score", 0) >= CONFIDENCE_THRESHOLD]
    assert not high_confidence_hits, (
        f"Case {case['id']}: expected no high-confidence match for an out-of-scope query, "
        f"got {high_confidence_hits} — check whether a relevance threshold is applied at all"
    )


def test_signals_chunks_are_never_returned():
    """The core bug this whole retrieval design exists to fix (RETRIEVAL-PROTOTYPE-FINDINGS.md):
    a Signals/triggers chunk must never be returned as retrievable/citable content, for any
    query — not just the two cases the original eval happened to catch it on."""
    from app.retrieval import ROUTING_HEADER_PATTERN

    for case in CASES:
        for result in retrieve(case["query"], top_k=10):
            assert not ROUTING_HEADER_PATTERN.search(result["header"]), (
                f"Case {case['id']}: a Signals/triggers chunk was returned as content — "
                f"{result['doc']} § {result['header']}"
            )


def test_missing_corpus_degrades_gracefully_instead_of_crashing(monkeypatch):
    """Audit finding: a genuinely missing corpus (not just 'no relevant match' — the actual
    files aren't there, e.g. a deployment shipping only backend/ without the sibling
    docs/use-case-knowledge-base/) used to let a bare FileNotFoundError propagate out of
    retrieve() and 500 the whole /api/refine or /api/ask request. That directly contradicted
    this module's own 'best-effort grounding, never gates the core flow' design — which only
    actually covered the 'nothing relevant matched' case, not 'the corpus isn't there at
    all'. Fixed: _get_index() catches the load failure, logs once, and returns None; retrieve()
    treats that the same as an empty result set."""
    import app.retrieval as retr

    monkeypatch.setattr(retr, "DOC_FILES", ["nonexistent-file.md"])
    monkeypatch.setattr(retr, "_index", None)
    monkeypatch.setattr(retr, "_index_load_failed", False)

    result = retr.retrieve("Video conferencing app", top_k=3)
    assert result == []

    # Second call must not re-attempt the (expensive, doomed) build every time.
    result_again = retr.retrieve("Another query", top_k=3)
    assert result_again == []
    assert retr._index_load_failed is True


def test_embedding_model_stamp_mismatch_fails_loudly_not_silently(monkeypatch, caplog):
    """Problem 3 (embedding-model fitness function): app/retrieval.py's module docstring
    ('EMBEDDING-MODEL FITNESS FUNCTION') documents a real failure mode this guards against —
    the Chroma index's stored vectors were computed by one embedding-model version, but Ollama
    can silently swap the weights behind the SAME model tag mid-process-lifetime (`ollama pull`
    re-pulling `nomic-embed-text`), so every subsequent query would silently compare
    old-weight document vectors against new-weight query vectors with no error. This confirms
    the guard actually fires: a real (built) index whose recorded stamp no longer matches the
    currently-reported stamp must make retrieve() return [] AND log at ERROR (not the routine
    degraded-mode WARNING used for 'corpus missing'/'Ollama unreachable' elsewhere in this
    module) — a silent wrong-answer is worse than an empty one."""
    import logging

    import app.retrieval as retr

    idx = retr._get_index()
    assert idx is not None, "requires a real local Ollama + nomic-embed-text to build the index"

    monkeypatch.setattr(idx, "embedding_stamp", "nomic-embed-text::deadbeefdeadbeefdead")
    monkeypatch.setattr(retr, "_embedding_stamp", lambda: "nomic-embed-text::0a109f422b47e3a30ba")

    with caplog.at_level(logging.ERROR, logger="app.retrieval"):
        result = retr.retrieve("Video conferencing app", top_k=3)

    assert result == []
    assert any(r.levelno >= logging.ERROR for r in caplog.records), (
        "a confirmed embedding-model stamp mismatch must log at ERROR, not silently degrade"
    )
    # Self-healing: the stale singleton was torn down, so the next call rebuilds fresh rather
    # than staying permanently broken for the rest of the process.
    assert retr._index is None
