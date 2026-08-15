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

Two-stage design implemented here (UNCHANGED from the TF-IDF version this replaces — this is
a similarity-metric swap, not a design change):
  1. ROUTING stage — similarity against each doc's Signals/triggers + preamble text only,
     producing a per-document relevance score. Signals chunks are used for routing, never
     returned as retrievable/citable content (per the ingestion guide's explicit instruction).
  2. CONTENT stage — similarity against real content chunks (decision points, anti-patterns,
     reference implementations — everything except Signals/preamble), producing per-chunk
     scores. Final ranking blends a chunk's own content-relevance with its parent document's
     routing score, so a document that's clearly on-topic (per its Signals) gets its content
     chunks ranked higher even if a chunk's own wording doesn't share much vocabulary with the
     query — without ever letting a Signals chunk itself become the returned/cited context.
    This still matters under embeddings: embeddings fix the *lexical*-overlap failure mode
    (paraphrase gap) but a dense keyword-stuffed Signals chunk can still be semantically
    "close" to a query about that same topic — it's about the topic, just not an answer. The
    two-stage split keeps Signals chunks out of the citable pool regardless of which
    similarity metric ranks them highly.

EMBEDDINGS, not TF-IDF (revisits the deferred decision flagged in the previous version of this
docstring — "revisit if retrieval quality on paraphrase-heavy queries turns out to matter").
Uses ChromaDB as the vector store with a local embedding model served by the same Ollama
daemon already running for this project's local-LLM fallback (see app/llm_providers.py) —
`nomic-embed-text` (768-dim), pulled locally, no network call to any cloud embeddings API.
This keeps the local-first framing already established for the rest of this environment
(config.py's ollama_base_url/ollama_embed_model). ChromaDB's own bundled default embedding
function (onnx MiniLM) was considered and rejected here: it downloads its model weights from
Hugging Face on first use, which is a *cloud* dependency at runtime even though the model then
runs locally — nomic-embed-text via the already-local, already-running Ollama daemon avoids
that entirely.

Chroma collections are rebuilt in-memory (EphemeralClient) once per process, mirroring the old
module-level singleton — the corpus is small (11 files) and static at runtime, so there is no
reason to persist an on-disk index or pay embedding cost more than once per process lifetime.

If Ollama (or the configured embedding model) isn't reachable when the index is first built,
retrieval degrades to "no grounding" exactly like a missing corpus does — see _get_index()'s
docstring — never a 500 out of /api/refine or /api/ask.

Citation format matches 00-INDEX-AND-INGESTION-GUIDE.md §2: every retrieved chunk carries its
source document and decision-point/header name back to the caller, e.g.
"01-realtime-collaborative-editing.md § Decision Point A (CRDT vs. OT)".
"""
import logging
import os
import re

import chromadb
import httpx
from chromadb.api.types import Documents, Embeddings

from .config import settings

logger = logging.getLogger(__name__)

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


class _OllamaEmbeddingFunction:
    """Chroma embedding function backed by the local Ollama daemon's /api/embed endpoint —
    see module docstring for why Ollama+nomic-embed-text over Chroma's bundled default (which
    pulls from Hugging Face at runtime, a cloud dependency this project avoids elsewhere).

    Raises (does not swallow) on any HTTP/connection failure — the caller (_Index.build(),
    via _get_index()) is responsible for catching that and degrading to "no grounding," same
    treatment as a missing corpus. Swallowing here would silently return zero vectors, which
    is worse than a loud failure at index-build time.
    """

    def __init__(self, base_url: str, model: str):
        self._base_url = base_url.rstrip("/")
        self._model = model

    def name(self) -> str:  # required by chromadb's EmbeddingFunction protocol
        return f"ollama/{self._model}"

    def __call__(self, input: Documents) -> Embeddings:
        resp = httpx.post(
            f"{self._base_url}/api/embed",
            json={"model": self._model, "input": list(input)},
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("embeddings")
        if not embeddings or len(embeddings) != len(input):
            raise RuntimeError(
                f"Ollama embeddings response malformed or incomplete for model "
                f"'{self._model}' (requested {len(input)}, got {len(embeddings or [])})."
            )
        return embeddings

    def embed_query(self, input: Documents) -> Embeddings:
        # Chroma's EmbeddingFunction protocol calls embed_query() (not __call__) for query-time
        # embedding when present, in case a model wants query/document embeddings to differ.
        # nomic-embed-text doesn't need that distinction for this corpus size, but the method
        # must exist — the protocol's own default implementation only comes for free via
        # subclassing chromadb.EmbeddingFunction, which this lightweight class deliberately
        # doesn't do (fewer chromadb-internal surface areas to track across versions).
        return self(input)


class _Index:
    """Lazily built, process-wide singleton — the corpus is small (11 files) and static at
    runtime, so re-chunking/re-embedding per request would be pure waste. Backed by two
    in-memory Chroma collections (routing, content) — see module docstring for the two-stage
    design these implement."""

    def __init__(self):
        self.client = None
        self.routing_collection = None
        self.content_collection = None
        self.content_chunks_by_id: dict[str, dict] = {}  # id -> {"doc", "header", "text"}

    def build(self):
        embed_fn = _OllamaEmbeddingFunction(settings.ollama_base_url, settings.ollama_embed_model)

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

        # In-memory client, rebuilt fresh each process — no on-disk persistence needed for an
        # 11-file static corpus (matches the old singleton's lifetime exactly).
        self.client = chromadb.EphemeralClient()

        self.routing_collection = self.client.create_collection(
            name="kb_routing", embedding_function=embed_fn, metadata={"hnsw:space": "cosine"}
        )
        routing_docs = list(routing_texts_by_doc.keys())
        routing_texts = [" ".join(routing_texts_by_doc[d]) for d in routing_docs]
        if routing_texts:
            self.routing_collection.add(
                ids=routing_docs, documents=routing_texts, metadatas=[{"doc": d} for d in routing_docs]
            )

        self.content_collection = self.client.create_collection(
            name="kb_content", embedding_function=embed_fn, metadata={"hnsw:space": "cosine"}
        )
        content_ids = [f"chunk-{i}" for i in range(len(content_chunks))]
        self.content_chunks_by_id = {cid: c for cid, c in zip(content_ids, content_chunks)}
        if content_chunks:
            self.content_collection.add(
                ids=content_ids,
                documents=[c["text"] for c in content_chunks],
                metadatas=[{"doc": c["doc"], "header": c["header"]} for c in content_chunks],
            )


_index: _Index | None = None
_index_load_failed = False  # sentinel so a missing corpus / unreachable Ollama fails fast, not
# on every call


def _get_index() -> _Index | None:
    """Returns None (not an exception) if the index can't be built — either the corpus can't
    be loaded (e.g. a deployment that ships only backend/ without the sibling
    docs/use-case-knowledge-base/ — the Docker image itself is exactly this case;
    docker-compose.yml mounts the corpus in separately for that reason, but nothing guarantees
    every deployment path does) OR the local Ollama daemon / embedding model isn't reachable
    (a new failure mode introduced by the embeddings swap — TF-IDF never had an external
    dependency to fail against). Both degrade the same way: best-effort grounding, never a
    500 out of /api/refine or /api/ask. Logged once, not on every request, via the
    module-level sentinel below."""
    global _index, _index_load_failed
    if _index_load_failed:
        return None
    if _index is None:
        try:
            built = _Index()
            built.build()
            _index = built
        except (OSError, httpx.HTTPError, RuntimeError):
            _index_load_failed = True
            logger.warning(
                "RAG knowledge-base index could not be built (corpus missing from %s, or the "
                "local Ollama embedding model '%s' at %s is unreachable/not pulled) — "
                "grounding will be disabled for the rest of this process (best-effort, not a "
                "hard failure; /api/refine and /api/ask still work without grounding). Check "
                "that docs/use-case-knowledge-base/ is present relative to this file, and that "
                "`ollama pull %s` has been run against a running Ollama daemon at the "
                "configured ollama_base_url.",
                KB_DIR,
                settings.ollama_embed_model,
                settings.ollama_base_url,
                settings.ollama_embed_model,
                exc_info=True,
            )
            return None
    return _index


# Weight of a chunk's parent-document routing score in the final blended ranking score, as a
# fraction of the chunk's own content-relevance score. Chosen so routing can meaningfully
# reorder near-tied content matches (fixing the Signals-chunk-outranks-content bug's ROOT
# CAUSE — a document's real relevance was never factored in before) without letting routing
# alone surface an otherwise-irrelevant chunk (content score still dominates: content + 0.4 *
# routing, not content * routing or an unweighted average).
#
# Raised from 0.2 (the TF-IDF version's value) to 0.4 when this module moved to embeddings —
# re-tuned empirically against the real eval suite (tests/test_retrieval_eval.py), not
# guessed: embeddings compress semantic-neighbor content into a narrower, higher score band
# than TF-IDF's sparse lexical scores (e.g. case 12's "Postgres LIKE" anti-pattern chunk in
# 08-search-and-recommendation-engine.md scored 0.627, barely ahead of an off-topic search
# chunk in 06-two-sided-marketplace.md at 0.660 — well within noise), so routing needs more
# relative weight to keep breaking those near-ties correctly. 0.4 fixed that case without
# regressing any of the other 18 cases that passed at 0.2. Raising further (tested informally
# up to ~0.75) would also fix case 7's gap (see tests/test_retrieval_eval.py's
# KNOWN_XFAIL_IDS), but was rejected — a weight that high risks routing alone promoting an
# otherwise-weak chunk, which is the exact failure mode this constant exists to prevent in the
# other direction.
ROUTING_BOOST_WEIGHT = 0.4


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """Two-stage retrieval over the use-case knowledge base. Returns a list of
    {"doc", "chunk_text", "header", "score"} dicts, ranked by relevance, never including a
    Signals/triggers chunk (see module docstring). `score` is the chunk's own content-relevance
    (0..1, cosine similarity from the embedding model) — used by callers (and the eval suite)
    as a confidence signal; routing only affects rank order, not the reported score itself.

    Returns [] (not an exception) if the index itself can't be built — see _get_index()'s
    docstring. Callers (refine.py/ask.py's _build_grounding_context()) already treat an empty
    result as "no grounding this time," so a missing corpus or unreachable embedding model
    degrades exactly like a query with no relevant matches, not like an error.
    """
    if not query or not query.strip():
        return []

    idx = _get_index()
    if idx is None:
        return []

    # Chroma distances under cosine space are (1 - cosine_similarity); convert back to a
    # similarity score in the same 0..1-ish range the TF-IDF version reported, so callers'
    # thresholds (refine.py/ask.py's GROUNDING_SCORE_THRESHOLD, the eval suite's
    # CONFIDENCE_THRESHOLD) keep meaning what they already mean.
    n_routing = idx.routing_collection.count()
    route_score_by_doc: dict[str, float] = {}
    if n_routing:
        route_result = idx.routing_collection.query(query_texts=[query], n_results=n_routing)
        for doc_id, distance in zip(route_result["ids"][0], route_result["distances"][0]):
            route_score_by_doc[doc_id] = 1.0 - float(distance)

    n_content = idx.content_collection.count()
    if not n_content:
        return []
    content_result = idx.content_collection.query(query_texts=[query], n_results=min(top_k * 5, n_content))

    scored = []
    for chunk_id, distance in zip(content_result["ids"][0], content_result["distances"][0]):
        chunk = idx.content_chunks_by_id[chunk_id]
        content_score = 1.0 - float(distance)
        route_score = route_score_by_doc.get(chunk["doc"], 0.0)
        blended = content_score + ROUTING_BOOST_WEIGHT * route_score
        scored.append((blended, content_score, chunk))

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
