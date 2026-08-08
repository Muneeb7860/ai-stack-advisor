"""
Local retrieval prototype — TF-IDF/cosine-similarity proxy for testing whether the knowledge-base
corpus is *structurally* retrievable, ahead of the real backend retrieval step existing.

IMPORTANT LIMITATION, stated up front: this uses TF-IDF (lexical/keyword overlap), not a dense
embedding model (semantic similarity) — sentence-transformers could not be installed in this
environment in the time available (large torch download timed out). TF-IDF is a legitimate proxy
for catching CORPUS-LEVEL problems — two documents competing for the same query, a document that
never surfaces for its own signal keywords, negative-control queries that accidentally match
something — but it will systematically UNDER-perform a real embedding model on paraphrase-heavy
queries (e.g. "shared canvas" matching "collaborative editing" without the literal word overlap).
Treat a TF-IDF pass here as a lower bound, not a substitute for re-running RETRIEVAL-EVAL-SET.md's
cases against the real embedding-based retrieval once /api/refine exists.

Usage:
    python3 retrieval_prototype.py
"""
import json
import os
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KB_DIR = os.path.dirname(__file__)
EVAL_CASES_PATH = os.path.join(KB_DIR, "eval_cases.json")

# Docs to chunk — the 12 domain/methodology files, excluding the index/eval-set meta files.
DOC_FILES = [
    "01-realtime-collaborative-editing.md",
    "02-video-audio-conferencing.md",
    "03-micro-frontend-architecture.md",
    "04-event-driven-distributed-transactions.md",
    "05-multi-tenant-saas.md",
    "06-two-sided-marketplace.md",
    "07-ml-feature-store-and-model-serving.md",
    "08-search-and-recommendation-engine.md",
    "09-cost-estimation-methodology.md",
    "10-hexagonal-intraservice-code-organization.md",
    "11-semantic-routing-guardrail-service.md",
]


def chunk_markdown(doc_name, text):
    """Split on ## / ### headers, per the ingestion guide's own chunking rule (00-INDEX...md
    Section 2: 'chunk on ##/### headers, don't chunk mid-paragraph')."""
    # Split keeping the header with its following content.
    parts = re.split(r"\n(?=#{2,3} )", text)
    chunks = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        header_match = re.match(r"^(#{2,3})\s+(.*)", part)
        header = header_match.group(2).strip() if header_match else "(preamble)"
        chunks.append({"doc": doc_name, "header": header, "text": part})
    return chunks


def load_all_chunks():
    all_chunks = []
    for fname in DOC_FILES:
        path = os.path.join(KB_DIR, fname)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        all_chunks.extend(chunk_markdown(fname, text))
    return all_chunks


def main():
    chunks = load_all_chunks()
    print(f"Loaded {len(chunks)} chunks from {len(DOC_FILES)} documents.\n")

    corpus_texts = [c["text"] for c in chunks]
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_df=0.85)
    doc_matrix = vectorizer.fit_transform(corpus_texts)

    with open(EVAL_CASES_PATH) as f:
        eval_data = json.load(f)
    cases = eval_data["cases"]

    results_by_section = {}
    detailed_results = []

    for case in cases:
        query_vec = vectorizer.transform([case["query"]])
        sims = cosine_similarity(query_vec, doc_matrix).flatten()
        ranked_idx = sims.argsort()[::-1]

        top_k = case.get("top_k_pass") or 5
        top_chunks = [(chunks[i], sims[i]) for i in ranked_idx[:top_k]]
        top_docs_seen = []
        for c, score in top_chunks:
            if c["doc"] not in top_docs_seen:
                top_docs_seen.append(c["doc"])

        expected_docs = case.get("expected_docs", [])
        section = case["section"]

        if section == "negative_control":
            # Pass if nothing in top results clears a modest relevance bar.
            max_score = float(top_chunks[0][1]) if top_chunks else 0.0
            passed = bool(max_score < 0.15)
            detail = f"max_score={max_score:.3f} (threshold 0.15) top_doc={top_chunks[0][0]['doc'] if top_chunks else None}"
        elif case.get("requires_all_expected_docs"):
            passed = bool(all(d in top_docs_seen for d in expected_docs))
            detail = f"expected_all={expected_docs} got_top_docs={top_docs_seen}"
        else:
            passed = bool(any(d in top_docs_seen for d in expected_docs)) if expected_docs else True
            detail = f"expected_any_of={expected_docs} got_top_docs={top_docs_seen}"

        # For anti-pattern/boundary cases, also check phrase presence in matched chunks.
        phrase_check = None
        if case.get("expected_chunk_contains") and passed:
            matched_chunk_text = " ".join(
                c["text"].lower() for c, s in top_chunks if c["doc"] in expected_docs
            )
            missing_phrases = [
                p for p in case["expected_chunk_contains"] if p.lower() not in matched_chunk_text
            ]
            phrase_check = "OK" if not missing_phrases else f"MISSING: {missing_phrases}"
            if missing_phrases:
                passed = "partial"  # doc matched but not the specific decision point

        results_by_section.setdefault(section, {"pass": 0, "fail": 0, "partial": 0})
        if passed is True:
            results_by_section[section]["pass"] += 1
        elif passed == "partial":
            results_by_section[section]["partial"] += 1
        else:
            results_by_section[section]["fail"] += 1

        detailed_results.append({
            "id": case["id"],
            "section": section,
            "query": case["query"],
            "passed": passed,
            "detail": detail,
            "phrase_check": phrase_check,
            "top3": [(c["doc"], c["header"], round(float(s), 3)) for c, s in top_chunks[:3]],
        })

    # ---- Report ----
    print("=" * 78)
    print("RESULTS BY SECTION")
    print("=" * 78)
    total_pass = total_partial = total_fail = 0
    for section, r in results_by_section.items():
        total = r["pass"] + r["partial"] + r["fail"]
        total_pass += r["pass"]; total_partial += r["partial"]; total_fail += r["fail"]
        print(f"{section:20s} pass={r['pass']:2d}  partial={r['partial']:2d}  fail={r['fail']:2d}  (of {total})")
    print("-" * 78)
    grand_total = total_pass + total_partial + total_fail
    print(f"{'TOTAL':20s} pass={total_pass:2d}  partial={total_partial:2d}  fail={total_fail:2d}  (of {grand_total})")

    print("\n" + "=" * 78)
    print("DETAILED RESULTS (failures and partials shown in full; passes summarized)")
    print("=" * 78)
    for r in detailed_results:
        status = r["passed"]
        if status is True:
            print(f"[{r['id']:2d}] PASS   ({r['section']})")
        else:
            label = "PARTIAL" if status == "partial" else "FAIL"
            print(f"[{r['id']:2d}] {label} ({r['section']}): \"{r['query'][:70]}\"")
            print(f"      {r['detail']}")
            if r["phrase_check"]:
                print(f"      phrase_check: {r['phrase_check']}")
            print(f"      top-3: {r['top3']}")

    # Write machine-readable results too.
    out_path = os.path.join(KB_DIR, "retrieval_prototype_results.json")
    with open(out_path, "w") as f:
        json.dump({
            "summary": {"pass": total_pass, "partial": total_partial, "fail": total_fail, "total": grand_total},
            "by_section": results_by_section,
            "details": detailed_results,
        }, f, indent=2)
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    main()
