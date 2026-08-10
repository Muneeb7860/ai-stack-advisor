# AI Stack Advisor — Kickoff Brief

Handoff document for picking this up in Claude Code. Paste the "Prompt to paste into Claude Code"
section at the bottom to get going immediately with full context — everything above it is the
reasoning for someone (or some future you) to read once, not every session.

**This is a merged brief.** Frontend/knowledge-base design work happened in a separate cloud session
in parallel with backend build-out in this one. This version reconciles both — the frontend
changelog below is theirs (verified against the actual repo before merging in), the backend status
is accurate as of this repo's current state (not as of whenever either session last checked in).

---

## 0. What changed on the frontend/knowledge-base side (parallel session, not this one)

The original brief described a v1 rule engine (`index.html`) that was already feature-complete. A
**separate design/research session** then did two full passes of expansion work, entirely inside
`index.html` and `docs/` — no backend files were touched, and NFR-5 (zero backend dependency for v1)
was never violated:

**Pass 1 — dimension expansion:**
1. UI/UX polish — typography (Inter font), left-sidebar nav, a pricing-data bug fix, neutral
   confidence-badge colors.
2. Six architecture-decision dimensions added/corrected: Waterfall-vs-Agile (scope certainty/contract
   type is the real driver, not team size), BFF (folded into the API-gateway trade-off card),
   TOGAF-vs-SAFe, plus verification that modular-monolith/Istio/hexagonal were already correct.
3. Compute-tier taxonomy overhaul — a 5-tier continuum (Mobile/Tablet → Laptop → Workstation →
   Server → Enterprise datacenter) replacing `pickVRAMTier()`, plus Ollama-vs-OpenRouter-vs-direct-SDK
   runtime selection, per-agent-role model mapping, 3-layer topology reasoning.
4. Real-world validation fixes — a live-quiz-app bug (was recommending Postgres+Kafka for a
   Redis-sorted-set+Pub/Sub problem), Terraform→OpenTofu (HashiCorp's 2023 BSL relicense), a
   systematic single-vs-multiple-API-gateway framework.
5. Governance/security dimensions — COBIT vs. ITIL v4, edge-JWT-auth vs. service-to-service
   mTLS+SPIFFE/SPIRE; `pickMesh()` now recommends SPIFFE/SPIRE-aware Istio when relevant.
6. **8 new use-case domains**: real-time collaborative editing (CRDT/Yjs), video/audio conferencing
   (WebRTC/SFU), micro-frontends (Module Federation), event-driven Sagas, multi-tenant SaaS (Postgres
   RLS), two-sided marketplaces (Stripe Connect), ML feature stores, search/recommendation engines.
7. **3 previously-flagged gaps closed**: a directional monthly cost estimator (`pickCostEstimate()`
   — the one concrete feature StackAdvisor.ai had that this tool didn't), a semantic-routing/
   AI-guardrail-service trade-off card, hexagonal intra-service code-organization guidance.
8. **A new 12-file knowledge-base corpus** (`docs/use-case-knowledge-base/`) — RAG grounding material
   for `/api/refine`/`/api/ask`, not a product doc. See Section 3.

**Pass 2 — stress-testing + retrieval validation (after Pass 1):**
9. **Retrieval eval run for real**, ahead of `/api/refine` existing — built a local TF-IDF prototype
   over the 12-doc corpus and ran the 21-case eval set: **18 pass / 2 partial / 1 fail.** Found a
   real, actionable retrieval bug: `Signals / triggers` chunks (dense keyword lists) systematically
   out-rank the actual decision-point content a query is looking for — in one case by nearly 5x. **Do
   not build naive top-K retrieval against this corpus without reading
   `docs/use-case-knowledge-base/RETRIEVAL-PROTOTYPE-FINDINGS.md` first** — it specifies a two-stage
   fix (route on Signals chunks, then retrieve real content chunks; never hand a Signals chunk to the
   LLM as citable context), already folded into the ingestion guide. One real fail also found and
   documented, not swept under the rug: cross-document under-retrieval on a paraphrase-heavy query
   ("shared whiteboard" vs. "collaborative editing") — expected to improve with real embeddings
   instead of TF-IDF's lexical matching, but flagged to re-verify, not assumed fixed.
10. **5 more stress-test domains**: telemedicine, trading platforms, government/FedRAMP, crypto
    exchanges, fleet/logistics IoT. Found and fixed two genuine gaps — "telehealth"/"video
    consultations" phrasing wasn't triggering the video-conferencing reasoning, and "route
    optimization"/"fleet management" wasn't triggering geospatial reasoning — both existing
    dimensions, just missing realistic phrasing. Fixed, verified, full regression re-run (26
    scenarios, zero errors). **Explicitly flagged but NOT built** (time-boxed, deserves its own
    research pass): crypto wallet-custody/HSM architecture, HFT-specific low-latency datastore
    reasoning. Don't assume these are covered.
11. **BRD/PRD/DDD refreshed** by that session for the frontend-expansion content (signal/pickX
    counts, cost-estimator resolution, RAG-corpus limitation). This repo's copies have since had
    those changes ported into `docs/*_gen.js` (the source of truth) alongside separate
    backend-completion fixes — see Section 1 below for current status; don't trust either session's
    docx timestamp over what's actually in `*_gen.js` now.

Every change above was parse-checked (`new Function()` on the extracted `<script>`) and regression-
tested (5 built-in examples + 20+ dimension-specific scenarios + 5 more stress-test scenarios, 26
total, zero errors) before being considered done — this is a verified changelog, not a to-do list.

## 1. What already exists — current status (this repo, right now)

- **`index.html`** — the whole shipped v1 product, now with **65+ signal dimensions and 45 `pickX()`
  functions** (up from ~35/~30) — see Section 0. Fully functional, zero backend dependency, locked as
  PRD NFR-5.
- **`docs/`** — BRD, PRD, DDD (Word docs) + the generator scripts (`*_gen.js`) that produced them.
  **Regenerated and current** — reflect both the frontend expansion (Section 0) and full backend
  completion (below). If `docs/*.docx` and `docs/*_gen.js` ever disagree, `*_gen.js` is the source of
  truth; regenerate (`cd docs && npm run gen:all`).
- **`docs/alternatives-research/`** (5 files) — vendor-comparison research, already folded into
  `index.html`'s inline "alternatives" toggles. Reference material.
- **`docs/use-case-knowledge-base/`** (12 domain files + ingestion guide + a 21-case retrieval eval
  set + a TF-IDF retrieval prototype and its findings) — **read
  `00-INDEX-AND-INGESTION-GUIDE.md` and `RETRIEVAL-PROTOTYPE-FINDINGS.md` before touching retrieval
  logic in `/api/refine`/`/api/ask`.**
- **`market-analysis.md`, `market-audit-2026-08.md`** — competitive landscape research (original + an
  Aug-2026 refresh). No new direct competitors found.
- **`dimension-expansion-requirements.md`, `validation-report.md`** — historical logs, closed.
- **`docs/adr/0001-mcp-rule-engine-port.md`** — the decision record for porting `index.html`'s rule
  engine to Python (`backend/app/rule_engine.py`) for the MCP tool, including how that port was
  verified (byte-for-byte diff against the real JS, expanded scenario set, zero diffs) — re-verified
  after the Section 0 expansion, since the rule engine changed substantially since the ADR was first
  written.
- **`backend/`** — FastAPI + Postgres + Alembic scaffold. **All four v2 milestones are built and
  tested**: share-links (FR-28), `/api/refine` (FR-27, RAG-grounded per decision #6 below),
  `/api/ask` (RAG-grounded), and the MCP tool wrapper (FR-29, `recommend_stack()` backed by
  `rule_engine.py`, re-ported and re-verified against the expanded `index.html`). See
  `backend/README.md` for the current test count, quickstart, and full status — don't trust a stale
  count in this brief over what `pytest tests/ -v` actually reports.

## 2. Decisions already made (don't re-litigate without a reason)

1. **API keys**: user's own Anthropic API key, passed per-request, never stored server-side. No
   shared server-side key. See `backend/.env.example` and the docstrings in `refine.py`/`ask.py`.
2. **Database**: Postgres via Docker Compose for local dev, matching production — not SQLite.
   `backend/docker-compose.yml` is ready to go (`docker compose up --build`).
3. **Build order** (complete): share links → `/api/refine` → `/api/ask` → MCP tool wrapper.
4. **Sharing has no auth** — `GET /api/analyses/shared/{slug}` is intentionally public and
   unauthenticated (matches the ERD's "Deliberately Excluded: no accounts" scope).
5. **No revoke-share feature yet** — also intentional (ERD note), not an oversight.
6. **RAG grounding for `/api/refine`/`/api/ask`**: implemented, not just adopted-in-principle.
   `backend/app/retrieval.py` implements the two-stage design from
   `RETRIEVAL-PROTOTYPE-FINDINGS.md` (TF-IDF, route via Signals chunks, retrieve real content
   chunks, never cite a Signals chunk directly) and is wired into both endpoints, with citations
   formatted per the ingestion guide's contract. The 21-case eval set was copied into
   `backend/tests/test_retrieval_eval.py` and wired to this real implementation: **20/21 pass**,
   1 honestly documented `xfail` (a TF-IDF-vs-real-embeddings paraphrase gap the original
   research already flagged) rather than a tuned threshold papering over it. A second, new
   limitation was found and also documented (not hidden) while wiring this up for real: no
   single TF-IDF confidence threshold cleanly separates genuine weak matches from false
   positives on this corpus — the grounding-injection threshold (`GROUNDING_SCORE_THRESHOLD`
   in both routers) is deliberately much lower than the eval's quality-measurement threshold,
   because a stricter bar was empirically found to suppress the corpus's flagship anti-pattern
   use case for `/api/ask`. See that constant's comment in `refine.py` for the actual numbers.
7. **Rule engine port** (ADR 0001): `app/rule_engine.py` is a Python port of `index.html`'s JS, not a
   shared-source dependency — the two files WILL drift if one changes without the other. Any future
   change to `index.html`'s `detectSignals()`/`pickX()` functions needs the equivalent change in
   `rule_engine.py` in the same or a clearly-linked commit. No automated check currently catches
   drift between them — flagged as a real gap, not silently accepted.

## 3. The knowledge-base corpus — read before touching `/api/refine` or `/api/ask`

`docs/use-case-knowledge-base/00-INDEX-AND-INGESTION-GUIDE.md` is the entry point — full retrieval
contract (chunking unit = `##`/`###` header sections, citation format, signal-keyword query-expansion
behavior), plus an index of all 12 domain files.

**`RETRIEVAL-PROTOTYPE-FINDINGS.md` is required reading before implementing retrieval**, not
optional background — it documents a real bug (Signals-chunk over-ranking) with a specific fix
already adopted (decision #6 above). Building naive top-K retrieval without reading this will
reproduce a bug that's already been found and fixed once.

`RETRIEVAL-EVAL-SET.md` + `eval_cases.json` + `test_retrieval_eval.py` is the 21-case eval set. Its
`retrieve()` stub should be wired to whatever the real retrieval implementation is and the suite
re-run — the TF-IDF prototype's 18/21 pass rate is a lexical-matching lower bound, not a verdict on
the real (embedding-based) retrieval's quality.

## 4. Known traps (things that will look like bugs in review if you don't know this context)

- The v1 rule engine has been through **two** rounds of bug-finding (original `validation-report.md`
  pass, plus real-world scenario testing during the expansion pass) — port `rule_engine.py` changes
  faithfully from the current `index.html` source, not from memory of an earlier version or from
  re-deriving what it "should" do.
- `pickCostEstimate()` in `index.html` is deliberately a **range, not a point estimate**, explicitly
  caveated as directional/re-verify-before-budgeting — keep that framing in any backend-side cost
  feature; a false-precision dollar figure from a tool with no live pricing API is worse than an
  honest range.
- `RefinementResult` is **append-only by design** — never update/overwrite a row. Makes the
  "disagreement rate" success metric (BRD Section 7) measurable later.
- `ConversationMessage` queries must filter by `analysis_id` in every single query, not just via
  system-prompt wording — DDD structural invariant.
- `McpInvocation.analysis_id` is nullable and populated AFTER the row is first inserted (logged the
  instant the tool is called, before the rule engine runs) — a query filtering
  `WHERE analysis_id IS NOT NULL` expecting "all invocations" will silently miss failed calls. Intentional.
- `app/rule_engine.py`'s signal dict keys are deliberately camelCase, unlike everything else in this
  Python codebase — a conscious exception to keep it a diffable port of `index.html`.
- Crypto wallet-custody/HFT-latency architecture is explicitly **not** covered by the knowledge base
  or the rule engine — flagged as a real gap by the design session, not silently missing.

## What's next

**Update 2026-08-10: the gap below is closed.** `index.html` now has real UI wired to the v2
backend — a mode picker, guided-input wizard, per-card "Refine with AI" buttons, inline follow-up
Q&A, and a Share button, all calling the real `/api/refine`, `/api/ask`, `/api/analyses`, and
`/api/analyses/{id}/share` endpoints. This was verified against the live backend (not mocked): real
HTTP calls, a real Postgres row created from guided-mode's synthesized text, a real share slug
created and opened via `?shared=SLUG` rendering read-only. **"v2 is shipped" now means an
end-to-end, user-clickable feature, not just a tested API** — see the 13-decision record below for
what was actually built, and `backend/tests/test_guided_synthesis.py` for the guided-mode signal
mapping's own test coverage. The original gap-finding paragraph is kept below for history, since it
accurately describes how this was discovered and why it mattered at the time:

> Real, found-during-audit gap, not just a "nice to have": the v1 frontend has no UI wired up to
> call the v2 backend at all. `index.html` has zero references to `/api/refine`, `/api/ask`, or any
> `fetch()` call — confirmed by grep, not assumed. The backend API layer (both endpoints, RAG-grounded,
> tested) is genuinely done; the "Refine with AI" button and follow-up-question box a user would
> actually click are still exactly what `diagrams/ui-mockup.html`'s "Page 2 — v2 Concepts (not yet
> built)" describes — a mockup, not a shipped feature. This is correct and intentional per PRD NFR-5
> (v1 must keep working with zero backend dependency, so the backend was never allowed to become a
> hard requirement for v1's UI) — but it means "v2 is shipped" throughout this repo's docs means the
> backend API layer specifically, not an end-to-end product feature a user can click through today.

**Known open gap in the now-shipped guided-mode + backend-wiring milestone** (disclosed, not
hidden): nobody has run a real refine/ask cycle with a genuine (non-invalid) Anthropic API key yet —
every test so far, including the live manual browser pass, deliberately used an invalid key to
prove error-handling, not a valid one to prove the happy path renders correctly end-to-end. That's
the single biggest unverified claim left. Requires a human to enter their own real key directly in
the browser — not something an agent should do on their behalf.

**Closed 2026-08-10**: the follow-up Q&A box had never been manually clicked-and-typed-into before
this date. Doing so immediately surfaced a real bug — the ask box only appeared after a
*successful* refine, even though `/api/ask` has no actual dependency on refine having succeeded
(an Analysis row already exists by the time refine is attempted). Fixed: the ask box now appears
as soon as an `analysis_id` exists, independent of whether the refine call itself succeeds or
fails. Verified live with a real second `/api/ask` call (distinct `request_id` from the refine
call) and confirmed no orphaned `conversation_messages` row when that call also failed.

**Guided-input mode + backend wiring — shipped 2026-08-08/09.** Built on the standalone
click-through demo referenced from `diagrams/ui-mockup.html` (mode picker, 6-question wizard, one
real skip case) and the backend API layer (shipped earlier — see below). Thirteen decisions locked
before implementation started, all now implemented in `index.html`:

1. **Scope**: both guided mode and backend wiring (refine/ask/share) land in one milestone.
2. **Frontend architecture**: stays a single `index.html`, progressive enhancement — NFR-5
   (zero backend dependency) stays intact for the free-text path.
3. **Mode picker**: equal weight, no "Recommended" badge on either option (supersedes nothing —
   this was already the landing-UX call from the previous decision round).
4. **Results view — reversed from the standalone demo's own sketch**: both the guided and
   free-text paths render through the *existing* 14-section full result view, not the demo's
   progressive-reveal (summary + 4-cell glance strip, sections collapsed behind "Show"). The
   demo file (`diagrams/design-sketch-v3-guided.html`) still shows progressive-reveal — that's
   its own historical concept, not what got built; don't treat it as the current spec.
5. **Signal mapping**: wizard answers synthesize a natural-language paragraph, fed through the
   existing `detectSignals()` unchanged — no parallel signal-mapping code path.
6. **Wizard questions**: 6, matching the demo's set exactly (building type, audience, compliance,
   team size, AI use case, free-text catch-all).
7. **Skip logic**: only the one case that already existed in the demo — compliance question
   skipped when audience = internal. No speculative additional branching.
8. **Refine button placement**: per-card "✨ Refine with AI" button (matches mockup frame 03),
   not a single global refine action — inline follow-up Q&A box appears below the card.
9. **API key UX**: lazy — a small inline prompt appears on the first refine/ask click, key
   cached in `sessionStorage` only (cleared on tab close), never persisted to disk, never sent
   anywhere but the backend's own `/api/refine`/`/api/ask` calls (per the existing per-request
   API-key convention, see the "API key handling" note below).
10. **Backend availability**: buttons always render; a single `/health` probe on page load
    determines whether clicking one succeeds or shows a friendly inline message ("Backend
    unavailable — run `docker compose up` to enable AI features") instead of a spinner-then-error.
11. **Analysis creation**: lazy — the first refine or share click POSTs `/api/analyses` to create
    the row and caches the returned `analysis_id` for the session; nothing hits the backend if
    the user never clicks refine or share.
12. **Share links**: in scope for this milestone — a "Share" button in the results header,
    reusing the same lazily-created `analysis_id`.
13. **Shared view**: renders in the same `index.html` via a `?shared=SLUG` query param — fetches
    `GET /api/analyses/shared/{slug}` and renders read-only (no textarea, no refine buttons, a
    read-only banner per mockup frame 04).

Both design threads (frontend expansion, backend build-out) are otherwise complete and merged. Per
the design session's own note: **the next milestone is real users, not another architecture dimension or
eval case.** Candidates from the BRD's own open items, none committed:
- **BR-7 (not met):** get the tool in front of real external users.
- **BR-8 (not met):** commit to one of the three target segments.
- Success-metrics instrumentation without violating NFR-1's browser-privacy posture — still open.
- Crypto custody/HFT domain research, if it turns out to matter to real users — deliberately not
  built speculatively.

## 5. Prompt to paste into Claude Code

```
I'm continuing work on AI Stack Advisor. Read KICKOFF_BRIEF.md at the repo root first — it's a
merged brief covering both a frontend/knowledge-base expansion (parallel session) and full backend
completion (this repo). Then read backend/README.md for current backend status and test count.

Everything from both design threads is built, tested, and merged — there's no fixed build order left
to resume. If you're picking this up to extend it further, start with "What's next" in
KICKOFF_BRIEF.md, and don't re-litigate anything under "Decisions already made" without raising it
first.
```
