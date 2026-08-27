# Use-Case Knowledge Base — Index & RAG Ingestion Guide

**Status:** New corpus, August 2026. Written specifically to be fed into the v2 backend's
`/api/refine` and `/api/ask` endpoints (see `../../KICKOFF_BRIEF.md`, `../../backend/README.md`)
as grounding context for LLM-based reasoning, once those endpoints move past their current 501-stub
state. This is not documentation *about* the product — it *is* the reasoning-engine's knowledge
source, written the way you'd write retrieval content, not a blog post.

---

## 1. Business context (BRD-level — why this corpus exists)

`index.html`'s v1 rule engine (`detectSignals()` + ~55 `pickX(s)` functions) encodes architecture
decision knowledge as deterministic if/else branches. That approach is fast, transparent, and free
to run — but it hits a ceiling: every new use case (live quiz apps, ride-hailing geospatial needs,
collaborative editors) requires a developer to write new signal keywords and new branches by hand.
It cannot reason about a business requirement that doesn't match a pre-written pattern, and it can't
explain a recommendation in the user's own words.

The v2 direction (per `KICKOFF_BRIEF.md`'s build order — share links → `/api/refine` → `/api/ask` →
MCP tool wrapper) is to layer an LLM-based reasoning engine on top of the same knowledge, grounded
via RAG so it stays auditable and sourced rather than hallucinating architecture advice. This corpus
is that grounding material: the same decision logic already shipped in the rule engine, written out
as structured, retrievable knowledge, **plus** eight new use-case domains researched specifically to
extend coverage beyond what the rule engine currently handles at all.

**The two are meant to work together, not replace each other:** the rule engine stays as the
zero-cost, zero-dependency v1 path (locked by PRD NFR-5 — must keep working with no backend). The
RAG-grounded LLM path is for `/api/refine` (turning a rule-engine-generated cover page into a
richer, conversational recommendation) and `/api/ask` (answering follow-up questions the fixed rule
set can't anticipate) — both should retrieve from this corpus rather than let the model free-associate
architecture advice from parametric memory, which is exactly the failure mode a transparent,
sourced tool is trying to avoid in the first place.

## 2. Product requirements (PRD-level — what the reasoning engine should do with this corpus)

- **Retrieval unit = one domain document's numbered section**, not the whole file. Each file in this
  folder is written with stable `##`/`###` headers precisely so a chunker can split on them without
  losing "which decision point is this" context. Don't chunk mid-paragraph.
- **Every retrieved chunk must carry its source domain and decision-point name back to the LLM
  prompt**, e.g. "From: 01-realtime-collaborative-editing.md § Decision Point A (CRDT vs. OT)" —
  this is what lets `/api/ask` answer "why did you recommend Yjs over Automerge" by pointing at the
  actual reasoning, not a paraphrase.
- **Signal keywords sections are for query expansion, not literal string matching** — when a user's
  free-text requirement is embedded for retrieval, phrases like "real-time cursors" or "shared
  whiteboard" in a document's Signals section should pull that document into the candidate set even
  if the user's exact wording differs. This mirrors (and can eventually replace) `detectSignals()`'s
  `has()` keyword-array pattern in `index.html`.
- **Do not let a `Signals / triggers` chunk itself become citable context handed to the LLM** — a
  TF-IDF retrieval prototype run against this corpus (see `RETRIEVAL-PROTOTYPE-FINDINGS.md`) found
  that these chunks, being dense keyword lists, systematically out-rank the actual decision-point/
  anti-pattern content a query is looking for (in one case by nearly 5x). Use Signals chunks for a
  first-stage routing pass — "which document(s) is this about" — then retrieve that document's real
  content chunks for what actually goes into the LLM's context. Returning a Signals chunk as a cited
  answer produces "here's a list of keywords," not a real answer.
- **Recommendations are conditional, not absolute** — every decision point below states *when* a
  recommendation changes (team size, scale, compliance need, self-host vs. managed preference). The
  reasoning engine should surface the condition alongside the recommendation, not just the pick —
  this is the same "why + when to switch" shape as `pickTradeoffs()` in `index.html`, deliberately
  kept consistent so a user comparing v1's rule-engine output against v2's LLM output sees the same
  underlying logic, not two disconnected opinions.
- **Anti-patterns sections are high-value retrieval targets for `/api/ask`** — a large share of
  real follow-up questions are "is X okay?" where X is a known anti-pattern (e.g. "can we just use
  Postgres LIKE for search", "can we do 2PC across services"). These sections are written as direct,
  quotable answers to that question shape.
- **Sources are citations, not decoration** — every claim with a specific number, vendor name, or
  "as of 2026" framing traces to a URL in that document's Sources section. If `/api/ask` surfaces a
  claim from this corpus, it should be able to cite the source, matching the citation discipline
  already used in `market-analysis.md` and the `docs/alternatives-research/` files.

## 3. Domain index

| # | File | Domain | Extends rule-engine coverage? |
|---|---|---|---|
| 1 | `01-realtime-collaborative-editing.md` | CRDT/OT sync, presence, Figma/Notion/Linear-style multiplayer docs | Yes — wired into `pickMessaging()`'s `collabEditing` branch |
| 2 | `02-video-audio-conferencing.md` | WebRTC, SFU/MCU/mesh topology, TURN/STUN, signaling | Yes — wired into `pickCompute()`'s `videoConferencing` note + a new trade-off card |
| 3 | `03-micro-frontend-architecture.md` | Module Federation, single-spa, shared design systems, team-ownership boundaries | Yes — new trade-off card |
| 4 | `04-event-driven-distributed-transactions.md` | Saga (choreography/orchestration), CQRS, transactional outbox, event sourcing | Yes — new trade-off card |
| 5 | `05-multi-tenant-saas.md` | Silo/pool/bridge isolation, Postgres RLS, cell-based blast-radius containment | Yes — new trade-off card |
| 6 | `06-two-sided-marketplace.md` | Matching/search, Stripe Connect payments/escrow, trust & safety, supply/demand app split | Yes — new trade-off card |
| 7 | `07-ml-feature-store-and-model-serving.md` | Feature stores, training/serving skew, model registries — traditional ML, distinct from LLM/RAG | Yes — new trade-off card |
| 8 | `08-search-and-recommendation-engine.md` | Search index selection, hybrid search/RRF, collaborative vs. content-based recommendation, cold start | Yes — new trade-off card |
| 9 | `09-cost-estimation-methodology.md` | Directional monthly cost estimate methodology (compute/database/LLM API bands) — sourcing for `pickCostEstimate()` | Yes — new "Directional monthly cost estimate" block in the Cost section |
| 10 | `10-hexagonal-intraservice-code-organization.md` | Ports & adapters folder structure within one service — one level deeper than the system-level hexagonal pick | Yes — `pickArchitecture()`'s `hexagonalNote` |
| 11 | `11-semantic-routing-guardrail-service.md` | Dedicated AI-gateway pattern for LLM routing + centralized guardrails, distinct from the guardrails vendor comparison | Yes — new trade-off card |
| 12 | `12-secure-delivery-pipeline.md` | CI security gates (secrets/SAST/SCA/image scan/sign+SBOM), GitOps promotion, progressive delivery, admission control | No — `pickCICD()` picks a CI product, nothing reasons about pipeline controls |
| 13 | `13-private-network-egress-control.md` | Private endpoints vs. one audited egress path; single public entry; private model endpoints for regulated AI | No — `pickHybridConnectivity()` covers on-prem↔cloud links, not in-cloud network boundary |
| 14 | `14-request-path-layer-ordering.md` | Layer order (DNS→edge→LB→gateway→platform), and which boxes are mutually exclusive alternatives | Partial — tiers exist in the canonical graph; ordering and exclusivity are not surfaced |

Documents 12–14 were contributed later, from reference architectures authored by the project owner
for a BFSI architecture review (the source SVGs are committed at
`diagrams/reference-architecture/`). They are the first entries in this corpus that are **not**
web-researched: their primary source is that author's own design work, and each one's Sources
section says so explicitly and lists the specific claims that still need external citation before
`/api/ask` repeats them as fact rather than as design guidance. They were added because they cover
three questions the corpus could not answer at all — what has to happen inside a delivery pipeline
for a regulated buyer to accept it, whether an LLM call leaves the network, and what order the
layers actually go in.

Each of the original 8 was chosen because the existing rule engine had **zero coverage** for it before this
research pass — confirmed by testing representative requirement text against the live tool and
finding no dedicated reasoning, only generic fallback branches. This list is not exhaustive of every
possible architecture pattern; it's the set of gaps that surfaced from (a) the user's own prior-project
experience shared in this session (live quiz app, API gateway iteration, a real multi-service repo
blueprint spanning micro-frontends and event-driven services) and (b) a systematic stress-test pass
(collaborative doc editor, video conferencing, stock trading, social feed, ride-hailing) run against
the live tool to find further gaps beyond what had already been flagged.

## 4. Research method

Each domain document was produced via live web search grounded in 2026-current sources — not
generated from training-data memory alone, per the same discipline used in `market-analysis.md` and
`docs/alternatives-research/*.md`. Every named vendor, library, or specific technical claim (e.g.
"P2P mesh caps out around 3-5 participants," "Postgres RLS is the dominant 2026 pattern for
shared-schema multi-tenancy") is sourced in that document's Sources section.

## 5. Retrieval evaluation — test this before trusting it

Everything above describes what the corpus *should* do once retrieved — it says nothing about
whether retrieval actually works. `RETRIEVAL-EVAL-SET.md` (+ `eval_cases.json` +
`test_retrieval_eval.py` in this same folder) is a 27-case eval set built specifically to catch
retrieval bugs before they reach a user: wrong-document matches, anti-pattern sections that don't
surface for "is X okay?" phrasing, cross-document queries that only return one hit, and — just as
important — out-of-scope queries that shouldn't return a confident match at all but do anyway
because no relevance threshold was applied.

This was written ahead of `/api/refine` existing, on purpose — `test_retrieval_eval.py` is a loud,
skipped placeholder (same convention as `app/mcp/server.py`'s import-time `NotImplementedError`)
until someone wires its `retrieve()` function up to the real retrieval step. Run it as part of
building `/api/refine`, not after — a retrieval bug found early is a query-tuning fix; found late,
after generation logic is built on top of it, it's a harder one to isolate.

## 6. Status of previously-flagged gaps

The three gaps flagged at the end of the first research pass — cost estimator, semantic-routing/
guardrail microservice pattern, hexagonal intra-service code organization — were closed in a
follow-up pass (docs 9–11 above). Prioritization logic: cost estimator first (named competitor
differentiator, highest business leverage), then semantic-routing/guardrails (moderate effort, real
architectural gap), then hexagonal intra-service (lowest effort, primarily a documentation
clarification of a pattern already referenced by name in `pickArchitecture()`).

No further gaps are currently flagged as open from this project's own review. New gaps will surface
the same way these did — through real user scenarios and stress-testing, not a fixed checklist — so
this section should be revisited each time a new domain gets added rather than treated as ever
fully "done."
