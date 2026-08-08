# Retrieval Evaluation Set

**Purpose:** Test whether the knowledge base actually *retrieves* correctly, not whether its
reasoning is sound (that was verified separately — see each domain doc's own research). A RAG
corpus can be well-written and still retrieve badly: two documents can compete for the same query,
an embedding model can fail to separate adjacent domains (e.g. "search" vs. "recommendations"), or
a query can land in a genuine coverage gap this corpus doesn't fill. None of that shows up until you
actually run queries against it — this eval set exists so that check happens before `/api/refine`
ships, not after a user hits a bad answer in production.

**Status:** Not yet run against the real backend retrieval pipeline (`/api/refine` doesn't exist
yet) — `test_retrieval_eval.py` remains a skipped placeholder for that. However, a **local TF-IDF
prototype pass has been run** (see `RETRIEVAL-PROTOTYPE-FINDINGS.md`) as a lower-bound sanity check
ahead of the real thing: 18/21 pass, 2 partial, 1 fail, plus one concrete, actionable finding about
how `Signals / triggers` chunks should be handled in retrieval (already folded into
`00-INDEX-AND-INGESTION-GUIDE.md`). Re-run against the real embedding-based retrieval once
`/api/refine` exists — the TF-IDF pass is informative, not a substitute. See `eval_cases.json` for
the machine-readable version and `test_retrieval_eval.py` for the ready-to-adapt harness skeleton.

**How to use this:** Once `/api/refine` (or whatever internal function does the retrieval step)
exists, run each `query` through it and check whether `expected_primary_doc` (and, for multi-hit
cases, everything in `expected_docs`) actually comes back in the top-K results. Track a simple hit
rate — this doesn't need to be sophisticated to be useful. A retrieval step that's wrong on the
easy, unambiguous cases (Section 1) is a real bug worth fixing before anything else in `/api/refine`
gets built on top of it.

---

## 1. Direct retrieval — one query per domain, unambiguous phrasing

These should be easy: realistic user language that maps cleanly to exactly one document. If any of
these miss, that's a real retrieval bug, not a hard edge case.

| # | Query | Expected doc | Notes |
|---|---|---|---|
| 1 | "We're building a Figma-like design tool where multiple people edit the same canvas at once." | `01-realtime-collaborative-editing.md` | Should land on decision point A (CRDT vs. OT). |
| 2 | "How do we handle Zoom-style group video calls with screen sharing for up to 50 people?" | `02-video-audio-conferencing.md` | Should land on decision point A (media topology). |
| 3 | "We have separate teams owning the customer app, the admin dashboard, and the driver app — how do we let them deploy independently?" | `03-micro-frontend-architecture.md` | Matches the tool's own repo-blueprint origin case almost verbatim. |
| 4 | "Our checkout needs to reserve inventory, charge payment, and book shipping across three services — how do we keep that consistent?" | `04-event-driven-distributed-transactions.md` | Should land on decision point A (choreography vs. orchestration). |
| 5 | "We're building a B2B SaaS product and each customer company's data needs to be completely isolated from every other customer." | `05-multi-tenant-saas.md` | Should land on decision point A (silo/pool/bridge). |
| 6 | "We're building a marketplace connecting freelancers with clients — how should we handle payments and escrow?" | `06-two-sided-marketplace.md` | Should land on decision point B (Stripe Connect). |
| 7 | "We want to add a fraud-scoring model to flag suspicious transactions — what infrastructure do we need to train and serve it?" | `07-ml-feature-store-and-model-serving.md` | Should NOT retrieve the RAG/vector-DB reasoning elsewhere in `index.html` — this is traditional ML. |
| 8 | "Our product catalog needs a search bar with autocomplete and a 'you may also like' section." | `08-search-and-recommendation-engine.md` | Two sub-asks (search + recs) both live in this one doc — check both decision points A and C surface. |
| 9 | "Roughly how much should we budget monthly for an AI chatbot handling a few thousand conversations a day?" | `09-cost-estimation-methodology.md` | Should surface the LLM-cost-by-model-tier table specifically, not just the general methodology. |
| 10 | "What does 'hexagonal architecture' actually look like inside one service's folder structure?" | `10-hexagonal-intraservice-code-organization.md` | Tests that this doc is distinguishable from the system-level architecture reasoning in `index.html` itself. |
| 11 | "We have multiple agents calling different LLMs — should we route and guardrail that centrally or per-agent?" | `11-semantic-routing-guardrail-service.md` | Should land on decision point A (the two problems this solves). |

## 2. Anti-pattern retrieval — "is X okay?" phrasing

The anti-patterns sections were specifically written as direct answers to this question shape (see
`00-INDEX-AND-INGESTION-GUIDE.md` Section 2) — this checks that framing actually works for
retrieval, not just readability.

| # | Query | Expected doc | Notes |
|---|---|---|---|
| 12 | "Is it okay to just use Postgres LIKE queries for our search feature?" | `08-search-and-recommendation-engine.md` | Must retrieve the anti-patterns section specifically, not just decision point A — check the retrieved chunk actually contains the "using Postgres LIKE/ILIKE... is an anti-pattern" language. |
| 13 | "Can we use two-phase commit across our microservices instead of dealing with sagas?" | `04-event-driven-distributed-transactions.md` | Must retrieve the anti-patterns section's explicit "don't use 2PC for microservices" answer. |
| 14 | "Our cursor and presence data for the collaborative editor is slowing down the database — is that normal?" | `01-realtime-collaborative-editing.md` | Tests whether retrieval connects "presence data + database" to the specific anti-pattern (ephemeral data on the durable persistence path), not just the general collab-editing topic. |

## 3. Cross-document queries — legitimately span two domains

A single query can correctly need two documents. Retrieval should surface both, not force a choice.

| # | Query | Expected docs | Notes |
|---|---|---|---|
| 15 | "We're building a virtual classroom app with live video calls and a shared collaborative whiteboard." | `01-realtime-collaborative-editing.md`, `02-video-audio-conferencing.md` | Genuinely needs both — a retrieval step that only returns one is under-serving this query. |
| 16 | "We're an on-demand delivery marketplace connecting drivers and customers, and we need real-time driver location tracking on a map." | `06-two-sided-marketplace.md` (+ see note) | **Known gap:** geospatial/location-tracking reasoning exists in `index.html`'s `pickDatabase()` (the `geospatial` signal, PostGIS/Redis Geo guidance) but was never written up as its own knowledge-base document. Retrieval should surface doc 06, and this case documents — rather than hides — that the location-tracking half of the query has no dedicated KB doc to retrieve. If this gets built later, update this case to expect it. |

## 4. Boundary / decision-point-specific queries

Harder than Section 1: the query should retrieve the right *document* and, ideally, land close to
the right *decision point* inside it, not just anywhere in the file.

| # | Query | Expected doc | Expected decision point |
|---|---|---|---|
| 17 | "Should our video conferencing app use peer-to-peer or a server-based approach for 8 participants?" | `02-video-audio-conferencing.md` | Decision point A — specifically the "P2P mesh only holds up to roughly 3-5 participants" guidance. |
| 18 | "We need a model registry so we always know which model version is actually live in production." | `07-ml-feature-store-and-model-serving.md` | Decision point D (experiment tracking & model registry). |
| 19 | "Should routing between cheap and expensive models be rule-based or a trained classifier?" | `11-semantic-routing-guardrail-service.md` | Decision point C (semantic routing approaches, increasing sophistication). |

## 5. Negative controls — should NOT retrieve anything from this corpus with high confidence

These test that the system doesn't force a bad match. A retrieval step with no relevance threshold
will confidently return *something* for any query — that's a failure mode worth catching explicitly,
not something to discover the first time a user asks an out-of-scope question.

| # | Query | Expected result | Notes |
|---|---|---|---|
| 20 | "How do we set up CI/CD for our Kubernetes deployments?" | No high-confidence match in this corpus | CI/CD vendor comparison lives in `docs/alternatives-research/04-devops-frontend-cicd-observability-frameworks.md`, a different corpus not covered by this eval set. If `/api/refine` retrieves across both corpora, this should hit that file instead — if it only queries `use-case-knowledge-base/`, it should return low-confidence/nothing, not force a match against one of the 12 files here. |
| 21 | "What's the best way to configure DNS and SSL certificates for our custom domain?" | No high-confidence match in this corpus | Not covered anywhere in this corpus or in `docs/alternatives-research/`. A genuine out-of-scope query — the right behavior is an honest "not covered" rather than a forced, low-relevance retrieval. |

---

## Suggested pass criteria

- **Section 1 (11 cases):** top-1 result must be the expected doc. Anything less is a real bug —
  fix before building anything else on top of retrieval.
- **Section 2 (3 cases):** top-3 results must include the expected doc, AND the retrieved chunk(s)
  must include the anti-pattern language specifically (not just any chunk from the right file) —
  this is what makes `/api/ask` able to cite the actual guidance rather than paraphrase around it.
- **Section 3 (2 cases):** top-5 results must include all expected docs, not just one.
- **Section 4 (3 cases):** top-3 results must include the expected doc; spot-check that the specific
  decision-point content is in the returned chunk, not just the file's Signals/business-context
  section.
- **Section 5 (2 cases):** no result above whatever relevance-score threshold `/api/refine` treats
  as "confident enough to cite" — or, if the system always returns top-K regardless of score, the
  response should explicitly say the query isn't well-covered rather than presenting a low-relevance
  match as if it were authoritative.

Re-run this set any time a new document is added to the corpus (a new doc can start winning queries
it shouldn't) or the embedding/retrieval model changes.
