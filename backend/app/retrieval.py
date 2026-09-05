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

Two-stage design implemented here (UNCHANGED across both the TF-IDF -> embeddings swap and the
hybrid-retrieval change below — this file has changed *how similarity is computed*, twice now,
but never *what gets compared to what*):
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

HYBRID RETRIEVAL (added after a review of the pure-embeddings migration found a real, measured
regression — see tests/test_retrieval_eval.py's top-of-file comment for the exact per-case
numbers, not just aggregate pass/fail counts). The concern: this product's whole value
proposition is telling apart precisely-named, similar-sounding technologies (Qdrant vs.
Weaviate, Kafka vs. RabbitMQ, fraud-scoring vs. trust-and-safety pipelines). Pure embedding
similarity is *optimized* to compress exactly those fine-grained lexical distinctions in
service of catching paraphrases — the right trade for general-purpose RAG, the wrong one for a
tool whose job is precise technology-name disambiguation. So this module now fuses two
independent retrieval signals per stage (routing and content, both still kept structurally
separate per the design above) via Reciprocal Rank Fusion (RRF):
  - an embedding ranking (nomic-embed-text cosine similarity — unchanged from above, still
    catches paraphrase/intent matches like "shared whiteboard" ~ "collaborative editing"), and
  - a lexical ranking (BM25 Okapi over the same chunk text — catches exact
    technology-name/identifier overlap that embeddings compress away, e.g. "fraud-scoring
    model" against a chunk that literally contains "feature store" and "model serving" but
    only loosely resembles the marketplace doc's "Trust & safety pipeline" section in
    embedding space).
RRF (see _rrf_scores() below) combines two rankings by RANK POSITION, not raw score — this
sidesteps the exact problem case 20 in the eval suite exposed: cosine similarity's score band
is narrow ("everything is somewhat similar" in embedding space), so raw-score blending lets
one system's noise dominate. Rank-based fusion is immune to that: a chunk has to rank well
under BOTH systems (or exceptionally well under one) to end up highly fused, which is exactly
the conjunction a precise-tech-name query and a paraphrase-heavy query each need in opposite
proportions.
BM25, not TF-IDF, for the lexical half: this project already had a TF-IDF implementation
before the embeddings migration (now removed, git history has it) and could have restored it
verbatim, but BM25's term-frequency saturation (a term matching 5 times isn't 5x as relevant
as matching once) and document-length normalization make it the better-established choice for
exactly this pairing — it's the standard lexical half of hybrid dense+sparse retrieval systems
elsewhere (Elasticsearch/Lucene's default scorer, Weaviate's and Qdrant's own hybrid-search
lexical component). Implemented by hand below (~40 lines) rather than adding a dependency
(`rank_bm25` or scikit-learn): the corpus is 18 files/~240 chunks, BM25 over that is a few dozen
lines of arithmetic, and this project already goes out of its way to avoid an unnecessary
runtime dependency (see the ChromaDB-default-embedding-function rejection above) — the same
discipline applies here.
The `score` field returned by retrieve() is UNCHANGED in meaning: it's still the chunk's own
embedding cosine similarity, exactly as before RRF was added. RRF only changes *rank order*
(and, in the routing stage, contributes to the blended tiebreak score used for
ROUTING_BOOST_WEIGHT) — callers' tuned thresholds (refine.py's/ask.py's
GROUNDING_SCORE_THRESHOLD, the eval suite's CONFIDENCE_THRESHOLD, both re-tuned for
embeddings' score band) keep meaning exactly what they already mean. This was a deliberate
choice to keep the blast radius of the hybrid change scoped to *ranking*, not to every
threshold downstream of `score`.

Chroma collections are rebuilt in-memory (EphemeralClient) once per process, mirroring the old
module-level singleton — the corpus is small (11 files) and static at runtime, so there is no
reason to persist an on-disk index or pay embedding cost more than once per process lifetime.

EMBEDDING-MODEL FITNESS FUNCTION (see EmbeddingModelStampMismatch below). Embeddings are
model-specific: a document vector computed by one model version is not comparable to a query
vector computed by a different version of "the same" model, even if the config still says
`nomic-embed-text` both times — Ollama can silently swap the weights behind a tag (`ollama
pull nomic-embed-text` re-pulls the same name at a new digest) without this process restarting.
Concretely, in THIS module's architecture: the Chroma index is built once per process
(`_get_index()`'s singleton), but every `retrieve()` call re-embeds the query fresh against
whatever model Ollama is CURRENTLY serving for that tag. If the underlying weights drift mid-
process-lifetime, stored document vectors (old weights) get compared against fresh query
vectors (new weights) with no error — just silently wrong similarity scores. That's the exact
failure mode this exists to catch loudly instead of letting it degrade silently.
Where the stamp lives: Chroma's own collection metadata (confirmed to support arbitrary
string key/value pairs, and to round-trip through get_collection() — see the routing/content
collections' `metadata=` below), not a Postgres table via Alembic. Reasoning: the stamp's
lifetime is identical to the collection's lifetime — both are rebuilt together, in the same
process, from the same `_Index.build()` call. A DB row would either have to be a permanent
record of something inherently transient (misleading), or would need its own cross-process
invalidation logic mirroring what's already built here (redundant). This is retrieval infra
scoped to a single process's in-memory index, not a knowledge-base content entry — there's no
`data/stack-kb.json`-style "fitness function" convention in this repo to hang it on either
(checked; no such file exists here), so a direct version-stamp-and-compare at the collection
that would actually go stale is the most direct fix, not a detour through a schema migration
for data that was never relational to begin with.
The check runs on every `retrieve()` call (see _verify_embedding_stamp()) — one extra `GET
/api/tags` against the local Ollama daemon, cheap relative to the `/api/embed` call already
happening every query. A mismatch is logged at ERROR (not the routine WARNING the rest of this
module uses for "corpus missing" / "Ollama unreachable" degraded-mode logging — this is a
distinct, unmistakable failure, not a routine one) and the singleton is torn down so the NEXT
call rebuilds fresh against the new weights (self-healing); the CURRENT call still returns []
rather than serving comparisons known to be invalid — consistent with this module's existing
"never gates the core flow, but never silently serves known-wrong results either" contract. If
the digest check itself can't complete (Ollama transiently unreachable for that one GET), that
is NOT treated as a mismatch — only a positive, confirmed digest mismatch trips this path.

If Ollama (or the configured embedding model) isn't reachable when the index is first built,
retrieval degrades to "no grounding" exactly like a missing corpus does — see _get_index()'s
docstring — never a 500 out of /api/refine or /api/ask.

Citation format matches 00-INDEX-AND-INGESTION-GUIDE.md §2: every retrieved chunk carries its
source document and decision-point/header name back to the caller, e.g.
"01-realtime-collaborative-editing.md § Decision Point A (CRDT vs. OT)".
"""
import logging
import math
import os
import re
from collections import Counter

import chromadb
import httpx
from chromadb.api.types import Documents, Embeddings

from .config import settings

logger = logging.getLogger(__name__)

KB_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "use-case-knowledge-base")

# The corpus is DISCOVERED, not enumerated. It used to be a hardcoded list, which made the corpus
# directory and the actual corpus two different things: adding a domain document to
# docs/use-case-knowledge-base/ indexed nothing and failed silently — no error, no warning, just a
# document that could never be retrieved. That is exactly what happened when documents 12-14 were
# contributed, and it is the same duplicated-source-of-truth shape this project has been bitten by
# elsewhere (see backend/tests/test_engine_differential.py).
#
# Numbered `NN-*.md` files from 01 upward are domain/methodology content. 00-INDEX is meta, and the
# eval-set/prototype/JSON files in the same directory are tooling — both are excluded by the
# pattern rather than by name, so a new document is indexed by existing and a new tooling file
# cannot accidentally become corpus.
DOC_PATTERN = re.compile(r"^(?!00-)\d{2}-.+\.md$")


def _discover_doc_files() -> list[str]:
    try:
        names = os.listdir(KB_DIR)
    except OSError:
        return []
    return sorted(n for n in names if DOC_PATTERN.match(n))


DOC_FILES = _discover_doc_files()

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


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class _BM25Index:
    """Minimal Okapi BM25 lexical index — see module docstring for why hand-rolled instead of
    a dependency. Standard textbook defaults (k1=1.5, b=0.75, the same values Elasticsearch/
    Lucene ship as defaults) — no reason to deviate for this corpus.

    Built once per _Index.build() call, over whatever set of (id, text) pairs it's given —
    used for both the routing stage (per-document Signals/preamble text) and the content
    stage (per-chunk text), mirroring the embedding side's two separate collections.
    """

    K1 = 1.5
    B = 0.75

    def __init__(self, ids: list[str], texts: list[str]):
        self.ids = ids
        tokenized = [_tokenize(t) for t in texts]
        self.doc_len = [len(t) for t in tokenized]
        self.avg_doc_len = (sum(self.doc_len) / len(self.doc_len)) if self.doc_len else 0.0
        self.term_freqs = [Counter(t) for t in tokenized]
        doc_freq: Counter = Counter()
        for tf in self.term_freqs:
            for term in tf:
                doc_freq[term] += 1
        n = len(texts)
        # Okapi BM25 idf, floored at a small positive epsilon via the "+1" inside the log so
        # very common terms never go negative (the classic BM25 idf formula can dip negative
        # for terms in >50% of documents; the "+1" variant used by Lucene/Elasticsearch avoids
        # that without changing behavior for this corpus's realistic term distribution).
        self.idf = {
            term: math.log((n - freq + 0.5) / (freq + 0.5) + 1.0) for term, freq in doc_freq.items()
        }

    def ranked_ids(self, query: str) -> list[str]:
        """Returns ids sorted best-first by BM25 score. Ids with zero lexical overlap with the
        query still appear (score 0.0), at the bottom, stably ordered — RRF only cares about
        rank position, and every id needs a rank in both systems for a fair fusion (see
        _rrf_scores())."""
        q_terms = _tokenize(query)
        scored = []
        for i, doc_id in enumerate(self.ids):
            tf = self.term_freqs[i]
            dl = self.doc_len[i]
            score = 0.0
            for term in q_terms:
                freq = tf.get(term)
                if not freq:
                    continue
                idf = self.idf.get(term, 0.0)
                denom = freq + self.K1 * (1 - self.B + self.B * dl / (self.avg_doc_len or 1))
                score += idf * (freq * (self.K1 + 1)) / (denom or 1)
            scored.append((score, doc_id))
        scored.sort(key=lambda x: (-x[0], self.ids.index(x[1])))
        return [doc_id for _score, doc_id in scored]


# Reciprocal Rank Fusion constant — the standard choice (Cormack et al. 2009's original RRF
# paper, and the value Elasticsearch/Vespa/most hybrid-search implementations default to). Not
# re-tuned for this corpus: RRF is deliberately insensitive to the exact value of k across a
# wide range (it only controls how quickly the 1/(k+rank) curve flattens out for low-ranked
# items) — 60 was tried first and never needed changing while fixing eval cases 7/20, unlike
# ROUTING_BOOST_WEIGHT below which WAS re-tuned against real eval numbers.
RRF_K = 60


def _rrf_scores(*ranked_id_lists: list[str]) -> dict[str, float]:
    """Reciprocal Rank Fusion: combine any number of rank-ordered id lists into one fused
    score per id, by RANK POSITION not raw score — see module docstring for why rank-based
    fusion (not a weighted sum of raw scores) is the fix for case 20's regression specifically.
    An id absent from a given list contributes 0 for that list (not penalized further; RRF's
    own literature treats "not in this system's top results at all" as just a very low rank,
    which the +k floor already handles gracefully)."""
    fused: dict[str, float] = {}
    for ranked_ids in ranked_id_lists:
        for rank, doc_id in enumerate(ranked_ids, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (RRF_K + rank)
    return fused


class EmbeddingModelStampMismatch(RuntimeError):
    """Raised when the embedding model that actually produced the vectors in a Chroma
    collection differs from what's currently configured/pulled — see module docstring's
    'EMBEDDING-MODEL FITNESS FUNCTION' section. A RuntimeError subclass so it's still caught
    by _get_index()'s existing except clause (never a 500 out of /api/refine or /api/ask) —
    but see retrieve()'s handling for why it's logged distinctly (ERROR, not the routine
    degraded-mode WARNING) before falling into that shared path."""


def _ollama_model_digest(base_url: str, model: str) -> str | None:
    """Returns the currently-pulled digest for `model` from the local Ollama daemon's
    /api/tags, or None if it can't be determined (daemon unreachable, model not found, or an
    unexpected response shape) — callers treat None as 'can't verify, don't block on it', not
    as a mismatch. Matches Ollama's own name normalization: a bare 'nomic-embed-text' is the
    same model as 'nomic-embed-text:latest'."""
    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=10.0)
        resp.raise_for_status()
        models = resp.json().get("models", [])
    except (httpx.HTTPError, ValueError):
        return None
    wanted = model if ":" in model else f"{model}:latest"
    for m in models:
        if m.get("name") == wanted or m.get("model") == wanted:
            digest = m.get("digest")
            return digest[:19] if digest else None
    return None


def _embedding_stamp() -> str:
    """The expected fitness-function stamp for the CURRENTLY configured model — 'name::digest'
    if a digest could be determined, else just 'name' (still catches a model NAME change, just
    not a same-name weight swap — see _ollama_model_digest())."""
    digest = _ollama_model_digest(settings.ollama_base_url, settings.ollama_embed_model)
    return f"{settings.ollama_embed_model}::{digest}" if digest else settings.ollama_embed_model


class _Index:
    """Lazily built, process-wide singleton — the corpus is small (11 files) and static at
    runtime, so re-chunking/re-embedding per request would be pure waste. Backed by two
    in-memory Chroma collections (routing, content) plus two parallel BM25 lexical indices
    (same split) — see module docstring for the two-stage design and hybrid-retrieval fusion
    these implement."""

    def __init__(self):
        self.client = None
        self.routing_collection = None
        self.content_collection = None
        self.content_chunks_by_id: dict[str, dict] = {}  # id -> {"doc", "header", "text"}
        self.routing_bm25: _BM25Index | None = None
        self.content_bm25: _BM25Index | None = None
        self.embedding_stamp: str = ""

    def build(self):
        embed_fn = _OllamaEmbeddingFunction(settings.ollama_base_url, settings.ollama_embed_model)
        self.embedding_stamp = _embedding_stamp()

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

        # In-memory client, rebuilt fresh each process — no on-disk persistence needed for a
        # static corpus (matches the old singleton's lifetime exactly).
        self.client = chromadb.EphemeralClient()

        # Drop any collections a PREVIOUS build left behind. chromadb.EphemeralClient() does not
        # give you a private database: clients constructed with identical settings share one
        # in-process System, so a second build() sees the first build's collections and
        # create_collection() raises "Collection [kb_routing] already exists".
        #
        # That made the embedding-stamp guard's promised self-healing a no-op. _get_index()
        # discards the stale index on a confirmed stamp mismatch and the docstring says "the next
        # retrieve() call will rebuild it fresh" — but the rebuild crashed with an unhandled
        # chromadb.errors.InternalError, so retrieval stayed broken for the rest of the process
        # instead of recovering. Exactly backwards from the guard's intent, and worse than the
        # silent-wrong-answer it exists to prevent, because it takes the whole endpoint down.
        #
        # Found when a new test file happened to run after the stamp-mismatch test and every
        # retrieval in it returned nothing. The existing test asserted only that the index was
        # discarded (`assert retr._index is None`) and never that the rebuild afterwards worked,
        # which is why a broken rebuild path sat green.
        for _stale in ("kb_routing", "kb_content"):
            try:
                self.client.delete_collection(_stale)
            except Exception:  # noqa: BLE001 - absent is the normal case, not an error
                pass

        routing_docs = list(routing_texts_by_doc.keys())
        routing_texts = [" ".join(routing_texts_by_doc[d]) for d in routing_docs]

        self.routing_collection = self.client.create_collection(
            name="kb_routing",
            embedding_function=embed_fn,
            metadata={"hnsw:space": "cosine", "embedding_model_stamp": self.embedding_stamp},
        )
        if routing_texts:
            self.routing_collection.add(
                ids=routing_docs, documents=routing_texts, metadatas=[{"doc": d} for d in routing_docs]
            )
        self.routing_bm25 = _BM25Index(routing_docs, routing_texts)

        self.content_collection = self.client.create_collection(
            name="kb_content",
            embedding_function=embed_fn,
            metadata={"hnsw:space": "cosine", "embedding_model_stamp": self.embedding_stamp},
        )
        content_ids = [f"chunk-{i}" for i in range(len(content_chunks))]
        self.content_chunks_by_id = {cid: c for cid, c in zip(content_ids, content_chunks)}
        if content_chunks:
            self.content_collection.add(
                ids=content_ids,
                documents=[c["text"] for c in content_chunks],
                metadatas=[{"doc": c["doc"], "header": c["header"]} for c in content_chunks],
            )
        self.content_bm25 = _BM25Index(content_ids, [c["text"] for c in content_chunks])


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


def _verify_embedding_stamp(idx: _Index) -> bool:
    """The embedding-model fitness function (see module docstring). Returns True if the live
    index's stamp still matches what's currently configured/pulled, False on a CONFIRMED
    mismatch. A digest that can't be determined right now (Ollama transiently unreachable for
    this one /api/tags call) is NOT a mismatch — returns True, i.e. 'proceed, unverified' — so
    a flaky network blip on the cheap verification call never blocks a query that the actual
    /api/embed call would otherwise have served fine."""
    current = _embedding_stamp()
    if "::" not in current or "::" not in idx.embedding_stamp:
        # Digest unavailable on one side or the other right now — can't do a confirmed
        # comparison; don't block on an unverifiable check.
        return True
    return current == idx.embedding_stamp


def _invalidate_index(reason: str) -> None:
    global _index, _index_load_failed
    logger.error(
        "RAG knowledge-base index invalidated: %s — this Chroma index's stored vectors no "
        "longer match the currently-pulled embedding model, so similarity comparisons against "
        "it would be silently meaningless (not a routine 'no grounding available' condition — "
        "see app/retrieval.py's EMBEDDING-MODEL FITNESS FUNCTION docstring section). "
        "Discarding the stale index; the next retrieve() call will rebuild it fresh.",
        reason,
    )
    _index = None
    _index_load_failed = False


# Weight of a chunk's parent-document routing score in the final blended ranking score, as a
# fraction of the chunk's own content-relevance score. Chosen so routing can meaningfully
# reorder near-tied content matches (fixing the Signals-chunk-outranks-content bug's ROOT
# CAUSE — a document's real relevance was never factored in before) without letting routing
# alone surface an otherwise-irrelevant chunk (content score still dominates: content + 0.4 *
# routing, not content * routing or an unweighted average).
#
# NOTE on scale: this weight multiplies the chunk's RRF-fused ROUTING score (a small number,
# typically ~0.01-0.033 — see RRF_K/_rrf_scores() above) against the RRF-fused CONTENT score
# (same scale) — both sides of the blend are RRF scores now, not raw cosine similarities, so
# this constant's *meaning* (how much a document's routing relevance can reorder near-tied
# content matches) is preserved even though the numbers it multiplies changed when hybrid
# retrieval replaced the single embedding-cosine blend. Re-verified empirically against the
# real eval suite after the hybrid change (not re-derived from scratch) — 0.4 still fixes case
# 12's near-tie without over-promoting routing alone, same as it did for the pure-embeddings
# version.
#
# History: 0.2 under TF-IDF -> 0.4 when this module moved to embeddings (embeddings compress
# semantic-neighbor content into a narrower, higher score band than TF-IDF's sparse lexical
# scores, so routing needed more relative weight to keep breaking near-ties correctly — see
# case 12 in tests/test_retrieval_eval.py). Kept at 0.4 for the hybrid-retrieval change: RRF
# fusion (not this weight) is what fixed case 7 — see module docstring and MIN_CONFIDENT_RRF
# below for case 20.
ROUTING_BOOST_WEIGHT = 0.4

# Abstention gate: the minimum top-1 content score (raw embedding cosine) required for
# retrieve() to return anything at all, checked after ranking.
#
# REPLACES a peak-fused-RRF gate (MIN_CONFIDENT_RRF = 0.0316), removed after measuring it rather
# than re-tuning it. That constant's own comment said the gap was narrow and told the next person
# to re-run the measurement instead of nudging by feel. Re-run, it turned out the two classes no
# longer merely sat close — they overlapped completely:
#
#     genuine hits      0.0301 - 0.0328 peak RRF
#     should-be-blocked 0.0311 - 0.0320 peak RRF
#
# "How should I train for my first marathon" (0.031778) outscored three genuine queries, and two
# unrelated queries produced the IDENTICAL peak to fourteen decimal places (0.03149801587301).
# That is the tell: an RRF score is a sum of 1/(K + rank) terms, so the peak mostly encodes
# whether the two rankers AGREE ON A TOP ITEM, not how relevant that item is. It was never a
# confidence measure, which is why no value of it could separate the classes.
#
# Its calibration had also gone stale in a way worth recording. It was set just above eval case
# 20 ("CI/CD for our Kubernetes deployments"), then believed to be a true negative because no
# document covered CI/CD. Document 12 (secure delivery pipeline) has since been added and case 20
# now has an expected doc — so the gate was tuned to sit above a case the corpus can now answer.
#
# MEASURED SEPARATION for the replacement, across all 47 positive eval cases, the 1 negative
# control, 5 off-domain probes and 3 real queries the old gate wrongly blocked:
#
#     lowest genuine top-1 cosine     0.5484
#     highest off-domain top-1 cosine 0.4868
#     gap                             0.0615   (the old gate's gap was 0.00074)
#
# 0.52 sits mid-gap with ~0.03 margin on both sides. Re-run the measurement after any corpus or
# embedding-model change — the method is: query every eval case plus a handful of deliberately
# off-domain probes directly against _get_index(), and compare the top-1 `score` distributions.
#
# Case 21 (DNS/SSL certs) is still NOT separated: its top-1 cosine is 0.5324, above this gate and
# between two genuine cases. Unchanged and still xfailed, consistent with that case's own
# long-documented conclusion that it needs a learned reranker, not a threshold of any kind. The
# module docstring's older claim that every chunk scores "~0.5+ regardless of relevance" is what
# ruled cosine out originally; that is no longer true on this corpus with BM25 in the blend —
# off-domain queries measure 0.42-0.49.
MIN_CONFIDENT_COSINE = 0.52


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """Two-stage, hybrid retrieval over the use-case knowledge base. Returns a list of
    {"doc", "chunk_text", "header", "score"} dicts, ranked by relevance, never including a
    Signals/triggers chunk (see module docstring). `score` is the chunk's own content-relevance
    (0..1, cosine similarity from the embedding model) — used by callers (and the eval suite)
    as a confidence signal; ranking blends RRF-fused embedding+BM25 signals at both the routing
    and content stage (see module docstring's HYBRID RETRIEVAL section), but the reported
    `score` field's meaning is unchanged from the pure-embeddings version on purpose, so
    existing threshold tuning (GROUNDING_SCORE_THRESHOLD in refine.py/ask.py, CONFIDENCE_
    THRESHOLD in the eval suite) keeps meaning what it already means.

    Returns [] (not an exception) if the index itself can't be built, OR if a confirmed
    embedding-model version mismatch was just detected (see _verify_embedding_stamp()) — both
    cases degrade to 'no grounding this time' rather than serving a request off of vectors that
    can't be trusted. Callers (refine.py/ask.py's _build_grounding_context()) already treat an
    empty result as "no grounding this time."
    """
    if not query or not query.strip():
        return []

    idx = _get_index()
    if idx is None:
        return []

    if not _verify_embedding_stamp(idx):
        _invalidate_index(
            f"index was built with stamp '{idx.embedding_stamp}', currently-pulled model "
            f"stamp is '{_embedding_stamp()}'"
        )
        return []

    # Chroma distances under cosine space are (1 - cosine_similarity); convert back to a
    # similarity score in the same 0..1-ish range the TF-IDF version reported, so callers'
    # thresholds (refine.py/ask.py's GROUNDING_SCORE_THRESHOLD, the eval suite's
    # CONFIDENCE_THRESHOLD) keep meaning what they already mean.
    n_routing = idx.routing_collection.count()
    route_embed_ranked_ids: list[str] = []
    if n_routing:
        route_result = idx.routing_collection.query(query_texts=[query], n_results=n_routing)
        route_embed_ranked_ids = list(route_result["ids"][0])
    route_bm25_ranked_ids = idx.routing_bm25.ranked_ids(query) if idx.routing_bm25 else []
    route_rrf = _rrf_scores(route_embed_ranked_ids, route_bm25_ranked_ids)

    n_content = idx.content_collection.count()
    if not n_content:
        return []
    # Request every chunk's embedding distance (not just top_k*5) — the corpus is small enough
    # that this costs nothing, and it means every chunk has a real embedding rank/score to
    # fuse against its BM25 rank, rather than needing to reconcile two differently-truncated
    # candidate sets (a BM25-only hit that embeddings ranked outside a truncated window would
    # otherwise have no content_score to report).
    content_result = idx.content_collection.query(query_texts=[query], n_results=n_content)
    content_embed_ranked_ids = list(content_result["ids"][0])
    content_score_by_id = {
        chunk_id: 1.0 - float(distance)
        for chunk_id, distance in zip(content_result["ids"][0], content_result["distances"][0])
    }
    content_bm25_ranked_ids = idx.content_bm25.ranked_ids(query) if idx.content_bm25 else []
    content_rrf = _rrf_scores(content_embed_ranked_ids, content_bm25_ranked_ids)

    if not content_rrf:
        return []

    scored = []
    for chunk_id, chunk in idx.content_chunks_by_id.items():
        content_score = content_score_by_id.get(chunk_id, 0.0)
        route_score = route_rrf.get(chunk["doc"], 0.0)
        blended = content_rrf.get(chunk_id, 0.0) + ROUTING_BOOST_WEIGHT * route_score
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

    # Abstention gate. Moved here, and onto a different signal, after measuring the old one:
    # see MIN_CONFIDENT_COSINE's comment for the numbers. It has to run after ranking because
    # it reads the top result's own content score, which only exists once the blend has picked
    # a winner.
    if not results or results[0]["score"] < MIN_CONFIDENT_COSINE:
        return []
    return results


def format_citation(result: dict) -> str:
    """Matches 00-INDEX-AND-INGESTION-GUIDE.md §2's citation format: source doc + decision-
    point/header name, so /api/ask can cite its reasoning rather than paraphrase it."""
    return f"{result['doc']} § {result['header']}"


# Step 2 of the RAG-derivation-engine plan (see docs/adr/0001 and the KB-promotion work in
# PRs #6/#7): SIZE-AWARE QUERY CONSTRUCTION. Every doc in the corpus writes its decision points
# scale-conditioned — "a minimal/learning project needs none of this," "a compliance/enterprise
# requirement needs the full version" — often in the SAME chunk, since the KB's own convention
# (see 00-INDEX §2) is one decision point per header, not one header per scale tier. Retrieval
# itself (retrieve() above) is correctly blind to this: it ranks by topical relevance, and
# doesn't need to change to keep doing that right. What it doesn't have any signal for is scale
# — the same query text ("what audit logging do I need?") is retrieved identically regardless
# of whether the requirement behind it is a solo college project or a regulated bank, even
# though the corpus's own prose is written to answer differently for each. This function is
# the fix, and it is deliberately narrow: it only changes what TEXT gets passed as the query to
# retrieve() — nothing about retrieve()'s two-stage/hybrid ranking, its RRF weights, or its
# empirically-tuned thresholds (MIN_CONFIDENT_RRF, ROUTING_BOOST_WEIGHT) changes here, and none
# of that carefully-measured tuning needs to be re-verified because of this function.
#
# Signal keys match rule_engine.py's detect_signals() output exactly (camelCase, mirroring
# index.html — see that module's docstring for why). Only the flags a KB decision point is
# actually written to condition on are included; this is not every signal the rule engine
# detects, only the ones the corpus's own prose demonstrably branches on (minimal-project
# floors, compliance/finance/healthcare/enterprise escalation, onPrem-specific handling,
# highScale performance framing — the exact same guard conditions used throughout
# rule_engine.py's pickX() functions).
def build_scale_aware_query(text: str, signals: dict | None) -> str:
    """Appends a short, explicit scale/context descriptor to `text` before it's used as a
    retrieval query — nudging BOTH halves of the hybrid ranking (BM25 gets literal terms like
    "compliance"/"minimal" that the corpus's own scale-conditioned prose is dense with;
    embeddings get a semantic nudge toward the same framing) without touching retrieve()'s
    internals at all.

    `signals` may be None or {} (a real, expected case — see refine.py's docstring on why a
    refinement created without an analysis_id has no signals to hand this) — degrades to
    returning `text` unchanged, the same best-effort framing as every other missing-data path
    in this module. Never raises.
    """
    if not signals:
        return text
    descriptors = []
    # Order matters only for readability of the appended phrase, not for ranking — RRF/BM25
    # don't care about term order. minimalProject is checked first because it is the one true
    # floor in every pickX() guard chain (see e.g. pickAuditLogging/pickTestingStrategy in
    # index.html): a minimal project can still separately be onPrem or highScale, so these are
    # additive, not mutually exclusive branches.
    if signals.get("minimalProject"):
        descriptors.append("minimal personal or learning-scale project — lightweight, proportionate guidance, not enterprise-grade controls")
    if signals.get("compliance") or signals.get("finance") or signals.get("healthcare"):
        descriptors.append("regulated, compliance-driven context")
    if signals.get("enterprise"):
        descriptors.append("large enterprise organization")
    if signals.get("highScale"):
        descriptors.append("high-scale, high-traffic production system")
    if signals.get("onPrem"):
        descriptors.append("on-premises or air-gapped environment")
    if not descriptors:
        return text
    return f"{text} ({'; '.join(descriptors)})"
