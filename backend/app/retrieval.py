"""RAG retrieval over docs/use-case-knowledge-base/ — grounding content for /api/refine and
/api/ask (decision #6 in KICKOFF_BRIEF.md: retrieve from the corpus, don't let the model
free-associate architecture advice from parametric memory).

Design follows docs/use-case-knowledge-base/RETRIEVAL-PROTOTYPE-FINDINGS.md's preferred fix
(option 1, two-stage retrieval) for the real, confirmed bug that research found: a corpus
doc's `Signals / triggers` chunk (a dense keyword list, meant for query-expansion metadata
per 00-INDEX-AND-INGESTION-GUIDE.md §2) systematically out-ranks the actual decision-point
content a query is looking for under naive top-K similarity — in one eval case by nearly 5x,
because keyword density is exactly what a similarity metric rewards even though that chunk has
no real answer in it.

Two-stage design implemented here:
  1. ROUTING stage — similarity against each doc's Signals/triggers + preamble text only,
     producing a per-document relevance score. Signals chunks are used for routing, never
     returned as retrievable/citable content (per the ingestion guide's explicit instruction).
  2. CONTENT stage — similarity against real content chunks (decision points, anti-patterns,
     reference implementations — everything except Signals/preamble), producing per-chunk
     scores. Final ranking blends a chunk's own content-relevance with its parent document's
     routing score, so a document that's clearly on-topic (per its Signals) gets its content
     chunks ranked higher even if a chunk's own wording doesn't share much vocabulary with the
     query — without ever letting a Signals chunk itself become the returned/cited context.

TF-IDF / cosine similarity, not a dense embedding model — same choice and same disclosed
limitation as the research prototype this ports from (RETRIEVAL-PROTOTYPE-FINDINGS.md):
lexical/keyword-overlap similarity is a legitimate lower bound and catches corpus-structural
problems, but will underperform real embeddings on paraphrase-heavy queries (that prototype's
one documented fail, case 15, is exactly this — "shared whiteboard" vs "collaborative
editing"). No embedding provider was part of any decision already made for this project: Task
10 was scoped as "wire retrieval into refine/ask," not "adopt a new embeddings vendor" — using
the already-researched, already-partially-validated TF-IDF approach avoids a new undisclosed
architectural decision. Revisit if retrieval quality on paraphrase-heavy real queries turns out
to matter — see docs/adr/ for how to record that decision if it's made.

Citation format matches 00-INDEX-AND-INGESTION-GUIDE.md §2: every retrieved chunk carries its
source document and decision-point/header name back to the caller, e.g.
"01-realtime-collaborative-editing.md § Decision Point A (CRDT vs. OT)".
"""
import os
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "use-case-knowledge-base")

# The 11 domain/methodology docs — excludes 00-INDEX (meta, not retrievable content) and the
# eval-set/prototype files in the same directory. Mirrors DOC_FILES in retrieval_prototype.py.
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

# Headers whose content is routing metadata, never citable answer content — see module
# docstring. Matched case-insensitively against the chunk's header text.
ROUTING_HEADER_PATTERN = re.compile(r"signals?\s*/?\s*triggers?", re.IGNORECASE)


def _chunk_markdown(doc_name: str, text: str) -> list[dict]:
    """Split on ##/### headers, per the ingestion guide's chunking rule (00-INDEX...md §2:
    'chunk on ##/### headers, don't chunk mid-paragraph'). Mirrors
    retrieval_prototype.py's chunk_markdown() exactly — same corpus, same chunking contract,
    intentionally not reinvented here."""
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


class _Index:
    """Lazily built, process-wide singleton — the corpus is small (11 files) and static at
    runtime, so re-chunking/re-vectorizing per request would be pure waste."""

    def __init__(self):
        self.routing_docs: list[str] = []  # doc names, one entry per document
        self.routing_matrix = None
        self.routing_vectorizer = None
        self.content_chunks: list[dict] = []  # {"doc", "header", "text"} — citable chunks only
        self.content_matrix = None
        self.content_vectorizer = None

    def build(self):
        routing_texts_by_doc: dict[str, list[str]] = {}
        content_chunks = []

        for fname in DOC_FILES:
            path = os.path.join(KB_DIR, fname)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for chunk in _chunk_markdown(fname, text):
                is_routing = chunk["header"] == "(preamble)" or ROUTING_HEADER_PATTERN.search(chunk["header"])
                if is_routing:
                    routing_texts_by_doc.setdefault(fname, []).append(chunk["text"])
                else:
                    content_chunks.append(chunk)

        self.routing_docs = DOC_FILES
        routing_texts = [" ".join(routing_texts_by_doc.get(d, [])) for d in self.routing_docs]
        self.routing_vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_df=0.85)
        self.routing_matrix = self.routing_vectorizer.fit_transform(routing_texts)

        self.content_chunks = content_chunks
        content_texts = [c["text"] for c in content_chunks]
        self.content_vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_df=0.85)
        self.content_matrix = self.content_vectorizer.fit_transform(content_texts)


_index: _Index | None = None


def _get_index() -> _Index:
    global _index
    if _index is None:
        _index = _Index()
        _index.build()
    return _index


# Weight of a chunk's parent-document routing score in the final blended ranking score, as a
# fraction of the chunk's own content-relevance score. Chosen so routing can meaningfully
# reorder near-tied content matches (fixing the Signals-chunk-outranks-content bug's ROOT
# CAUSE — a document's real relevance was never factored in before) without letting routing
# alone surface an otherwise-irrelevant chunk (content score still dominates: content + 0.2 *
# routing, not content * routing or an unweighted average).
ROUTING_BOOST_WEIGHT = 0.2


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """Two-stage retrieval over the use-case knowledge base. Returns a list of
    {"doc", "chunk_text", "header", "score"} dicts, ranked by relevance, never including a
    Signals/triggers chunk (see module docstring). `score` is the chunk's own content-relevance
    (0..1, TF-IDF cosine similarity) — used by callers (and the eval suite) as a confidence
    signal; routing only affects rank order, not the reported score itself.
    """
    if not query or not query.strip():
        return []

    idx = _get_index()

    route_vec = idx.routing_vectorizer.transform([query])
    route_sims = cosine_similarity(route_vec, idx.routing_matrix).flatten()
    route_score_by_doc = dict(zip(idx.routing_docs, route_sims))

    content_vec = idx.content_vectorizer.transform([query])
    content_sims = cosine_similarity(content_vec, idx.content_matrix).flatten()

    scored = []
    for chunk, content_score in zip(idx.content_chunks, content_sims):
        route_score = route_score_by_doc.get(chunk["doc"], 0.0)
        blended = float(content_score) + ROUTING_BOOST_WEIGHT * float(route_score)
        scored.append((blended, float(content_score), chunk))

    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for _blended, content_score, chunk in scored[:top_k]:
        results.append({
            "doc": chunk["doc"],
            "chunk_text": chunk["text"],
            "header": chunk["header"],
            "score": content_score,
        })
    return results


def format_citation(result: dict) -> str:
    """Matches 00-INDEX-AND-INGESTION-GUIDE.md §2's citation format: source doc + decision-
    point/header name, so /api/ask can cite its reasoning rather than paraphrase it."""
    return f"{result['doc']} § {result['header']}"
