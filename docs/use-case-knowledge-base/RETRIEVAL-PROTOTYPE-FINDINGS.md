# Retrieval Prototype Findings

**Run date:** this session, ahead of `/api/refine` existing. **Method:** TF-IDF + cosine similarity
over the 12-document corpus, chunked on `##`/`###` headers per the ingestion guide's own rule —
NOT a dense embedding model (sentence-transformers could not be installed in this environment; the
torch download timed out). See `retrieval_prototype.py` for the full script and
`retrieval_prototype_results.json` for raw per-case output.

**Explicit limitation, stated up front:** TF-IDF is lexical (keyword-overlap) similarity, not
semantic similarity. It is a legitimate lower-bound proxy for catching corpus-structural problems
(chunk competition, keyword dilution) but will systematically underperform a real embedding model
on paraphrase-heavy queries. Treat everything below as "at least this good, probably better with
real embeddings" — not as a final verdict on retrieval quality. Re-run `RETRIEVAL-EVAL-SET.md`'s
cases against the actual backend retrieval once `/api/refine` exists; don't skip that step because
this prototype passed.

## Results: 18 pass / 2 partial / 1 fail (of 21)

| Section | Pass | Partial | Fail |
|---|---|---|---|
| Direct (11 cases) | 11 | 0 | 0 |
| Anti-pattern (3 cases) | 2 | 1 | 0 |
| Cross-document (2 cases) | 1 | 0 | 1 |
| Boundary (3 cases) | 2 | 1 | 0 |
| Negative control (2 cases) | 2 | 0 | 0 |

All 11 direct-retrieval cases passed cleanly — the corpus is well-separated for straightforward
queries even under plain lexical matching, which is a reasonable floor to clear before worrying
about harder cases. Both negative controls correctly scored below the relevance threshold (0.136
and 0.113 against a 0.15 cutoff), meaning the corpus doesn't force a false match for genuinely
out-of-scope queries — worth confirming this holds with a real threshold once the actual retrieval
step exists, since the 0.15 cutoff here is arbitrary/TF-IDF-specific.

## The one real, actionable finding: "Signals / triggers" chunks out-rank content chunks

Both partial cases (12 and 17) failed for the *same* underlying reason, confirmed by checking the
full ranking (not just top-3) for each:

**Case 12** ("Is it okay to just use Postgres LIKE queries for our search feature?") correctly
retrieved `08-search-and-recommendation-engine.md`, but the chunk that actually contains the
anti-pattern language ("Using Postgres LIKE/ILIKE... is the most common early mistake") ranked
**5th** (score 0.111) — just outside a top-3 cutoff — behind that same document's `Signals /
triggers`, `(preamble)`, and `Sources` chunks.

**Case 17** ("Should our video conferencing app use peer-to-peer or server-based for 8
participants?") is the clearer example: the actual answer — decision point A, "Media topology — P2P
mesh vs. SFU vs. MCU," which states the P2P-mesh-caps-at-3-5-participants guidance this query is
directly asking about — ranked **7th** (score 0.067), while that same document's `Signals /
triggers` chunk ranked **1st** (score 0.335), nearly 5x higher.

**Why this happens:** the `Signals / triggers` section in every domain doc is, by design, a dense,
comma-separated list of keywords and short phrases (see `00-INDEX-AND-INGESTION-GUIDE.md` Section
2's stated purpose — "for query expansion, not literal string matching"). That density is exactly
what TF-IDF rewards: high term frequency, low document-length dilution. But that chunk has no
actual reasoning in it — citing it back to a user would produce "here's a list of keywords," not an
answer. The chunk that has the real answer (a full decision-point section with explanatory prose)
scores lower precisely because it's longer and more varied, which is normal TF-IDF behavior but
means naive "return the top-K chunks and hand them to the LLM" retrieval would sometimes hand the
model a keyword list instead of the reasoning that keyword list was supposed to route toward.

## Recommendation for the real implementation

This is a concrete, actionable fix, not just an observation — three options, in order of
preference:

1. **Two-stage retrieval (preferred):** use `Signals / triggers` chunks (and each doc's
   `(preamble)`/business-context chunk) for a first-stage *routing* pass — "which document(s) is
   this query about" — then, once a document is selected, retrieve its actual decision-point/
   anti-pattern/reference-implementation chunks for the *content* that goes into the LLM's context.
   Don't let a Signals chunk itself become citable context.
2. **Exclude Signals/triggers chunks from the citable index entirely**, and instead fold their
   keywords into the metadata used for query expansion (per the ingestion guide's original intent)
   rather than treating them as retrievable prose.
3. **Down-weight short, keyword-dense chunks** in whatever ranking function the real retrieval step
   uses — a length-normalized or MMR-style (maximal marginal relevance) reranking pass after initial
   retrieval would likely fix this without restructuring the chunking scheme at all.

This finding should be read into `00-INDEX-AND-INGESTION-GUIDE.md`'s retrieval contract (done — see
its Section 2) so whoever builds `/api/refine`'s retrieval step doesn't rediscover this by shipping
it and getting "here are some keywords" as a cited answer in production.

## The one real fail: cross-document under-retrieval (case 15)

"We're building a virtual classroom app with live video calls and a shared collaborative
whiteboard" only surfaced `02-video-audio-conferencing.md` in the top-3 docs — `01-realtime-
collaborative-editing.md` (which should also match, given "shared whiteboard" is a listed signal
phrase in that doc) never appeared, and `03-micro-frontend-architecture.md` surfaced instead,
likely on generic word overlap ("app").

This is the clearest case where TF-IDF's lexical-only matching is expected to underperform a real
embedding model — "shared whiteboard" and "collaborative editing" are semantically close but share
few exact tokens, exactly the paraphrase gap dense embeddings exist to close. Flagging it here
rather than assuming it'll just work: **re-run this specific case (eval case 15) against the real
embedding-based retrieval once it exists, and don't assume it's fixed just because it's the kind of
case embeddings are supposed to handle better** — verify, don't assume.

## What this exercise validated about the corpus itself

Independent of the retrieval-implementation findings above, this run is good evidence that:
- The 12 documents are lexically well-separated for their core, unambiguous use cases (11/11 direct
  cases passed).
- The anti-patterns sections do contain distinctively-matchable language for "is X okay?" phrasing
  (case 12's target chunk was findable, just underranked — a ranking problem, not a content
  problem).
- The negative controls don't accidentally overlap with in-scope content (both scored low).

None of that would have been known with confidence before actually running queries against the
corpus — this is exactly the kind of check `RETRIEVAL-EVAL-SET.md` was built to force before
trusting the corpus in production.
