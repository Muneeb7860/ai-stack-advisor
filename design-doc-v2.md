# AI Stack Advisor — v2 Design Document

> **⚠️ SUPERSEDED — this is the original pre-implementation planning draft, frozen since the
> project's first commit. Everything proposed below has since been built, tested, deployed to
> a real backend, and extended well past this document's original scope** (guided-input wizard,
> per-card refine/ask buttons actually wired into `index.html`, refinement-pass history, real
> LLM cost display, why-this-pick signal inspection — none of which this document anticipated).
> Field names in Section 5's data-contract sketch are camelCase placeholders; the real API uses
> snake_case (`requirement_text`, `adjusted_picks`, etc. — see `backend/app/schemas.py`).
> **For current state, read [`KICKOFF_BRIEF.md`](KICKOFF_BRIEF.md) and
> [`diagrams/architecture-diagram.html`](diagrams/architecture-diagram.html) instead of this
> file.** Kept here as a historical record of the original design intent, not as a spec to
> build against — found stale via a documentation-vs-code validation pass that checked every
> claim against real code rather than against other docs.

**Status (historical, at time of writing):** Design complete, ready for development
**v1 (shipped):** single-file HTML, client-side rule engine, no backend
**v2 (this doc, historical):** hybrid rule + LLM reasoning engine, with an optional backend for persistence, sharing, and MCP exposure

---

## 1. Goal

v1 answers "what stack should I use?" with deterministic keyword rules — fast and free, but brittle on nuance (conflicting requirements, industries it wasn't tuned for, follow-up questions like "why not Kafka here?"). v2's goal is to keep v1's instant rule-based pass as the default, and layer an LLM reasoning pass on top for cases where the rules are uncertain or the user wants to interrogate a recommendation.

Non-goals for v2: this stays an advisory tool, not a provisioning tool. It recommends; it doesn't run `terraform apply`.

---

## 2. Architecture overview (C4 — Context)

```
 User ──(types requirements)──> AI Stack Advisor
                                      │
                          ┌───────────┴───────────┐
                          │                        │
                   Rule Engine (v1, kept)   LLM Reasoning Layer (new)
                   instant, deterministic    async, on-demand
                          │                        │
                          └───────────┬────────────┘
                                      │
                              Merged Recommendation
                                      │
                         (optional) Save / Share / MCP tool
```

Two tiers, not a replacement:
- **Tier 1 — Rule engine (existing):** runs on every keystroke-free submit, zero latency, zero cost, works offline. Stays the default and the fallback if Tier 2 is unavailable.
- **Tier 2 — LLM reasoning pass (new, opt-in):** takes the Tier 1 output plus the raw requirements text, and asks an LLM to (a) flag any category where the rule engine's confidence is low or requirements conflict, (b) let the user ask follow-up questions ("why Postgres over Mongo here?"), (c) produce a short written rationale paragraph instead of just chips.

Rationale for keeping both: the rule engine is transparent and auditable — every pick traces to a specific keyword match, which matters for a tool proposing architecture decisions. The LLM layer adds judgment for ambiguity but shouldn't be the only voice.

---

## 3. Component design (C4 — Container/Component)

### 3.1 Frontend (unchanged shell, extended)
- Same single-page structure as v1.
- New: a "Refine with AI" button appears after Tier 1 results render. Triggers Tier 2 only when clicked (keeps v1's zero-cost default behavior intact).
- New: a follow-up chat box scoped to the current recommendation ("ask a question about this stack").
- New: confidence badges per category (High / Medium / Low) computed from how many signals contributed to that pick in Tier 1 — this alone is useful without any LLM call, and can ship independently.

### 3.2 Reasoning API (new, requires backend)
- Thin stateless endpoint: `POST /api/refine`
  - Input: `{ requirementsText, tier1Result }`
  - Output: `{ adjustedPicks: [...], rationale: string, openQuestions: string[] }`
- Calls an LLM with a fixed system prompt that: (1) receives the full category list and Tier 1's picks as a starting point, (2) is instructed to only override a Tier 1 pick when it has a clear, stated reason, (3) must cite which part of the requirements text drove any change — no unexplained overrides.
- Guardrails on this endpoint itself (the tool practicing what it recommends): input length cap, output schema validation, no execution of anything the model returns, rate limiting per session.

### 3.3 Follow-up Q&A (new)
- `POST /api/ask` — takes the current recommendation + conversation history + new question, returns a grounded answer. Grounded meaning: the system prompt restricts the model to reasoning about the already-generated stack, not re-deriving a new one, to keep answers consistent turn to turn.

### 3.4 Persistence (new, optional)
- If the user wants to save/share a recommendation: a small `analyses` table (Postgres) keyed by a share ID, storing the requirements text, Tier 1 result, Tier 2 result (if run), and timestamp. No auth required for v2 — a share link is the access control, matching the tool's low-stakes nature.

### 3.5 MCP exposure (new, optional)
- Wrap the same logic as an MCP tool (`recommend_stack(requirements: string)`) so it can be called from Claude Code, Claude Desktop, or any MCP client — not just the web page. This turns the advisor into something callable from inside an actual architecture/planning conversation, which is arguably the more natural place to use it than a standalone form.

---

## 4. Recommended tech stack for the app itself

Applying the tool to itself:

| Category | Pick | Why |
|---|---|---|
| Frontend | Same static HTML/JS (no framework) | Page is simple enough that React/Vue would be pure overhead |
| Backend | Python (FastAPI) | Best fit for the LLM-calling glue code and MCP server SDK |
| Reasoning model | Claude (Sonnet tier) for refine/ask endpoints | Strong instruction-following for "only override with a cited reason" constraint; Haiku tier as a cheaper fallback for simple follow-up questions |
| Database | Postgres | Simple relational share-link storage; no need for Mongo/Cassandra at this scale |
| Hosting | Vercel (frontend) + Cloud Run (API) or a single small VM | Matches the "startup/MVP, small team, move fast" profile the tool itself would recommend for a project like this |
| CI/CD | GitHub Actions → Vercel + Cloud Run | Consistent with v1's own recommendation logic for small teams |
| Guardrails | Input length caps, output schema validation, rate limiting, no code execution from model output | Reasoning endpoints are low-risk (advisory text only) but still get baseline hardening |

---

## 5. Data contracts (sketch)

```jsonc
// POST /api/refine request
{
  "requirementsText": "string",
  "tier1Result": { "cloud": "AWS", "database": "PostgreSQL · MongoDB", "...": "..." }
}

// POST /api/refine response
{
  "adjustedPicks": [
    { "category": "database", "pick": "PostgreSQL only", "reason": "Requirements mention only transactional order data, no unstructured content — Mongo isn't justified here.", "changedFromTier1": true }
  ],
  "rationale": "One paragraph summary...",
  "openQuestions": ["Do you expect to store unstructured support tickets alongside orders?"]
}
```

---

## 6. Rollout plan

1. **Ship now (no backend needed):** confidence badges on Tier 1 picks — pure frontend, computed from existing signal counts. Small, immediate value-add.
2. **Once a backend/dev environment is available:** stand up the FastAPI service, wire `/api/refine` and `/api/ask`, add the "Refine with AI" button and follow-up box to the existing page.
3. **Then:** persistence (share links) and MCP tool wrapper, in either order depending on which you'd use first.

I'll hold development on steps 2–3 until you're on a desktop session where I can set up and run a backend properly (a browser-only session can't host a live API). Step 1 I can do right now in this session if you want it — say the word and I'll add confidence badges to the existing file today.

*(Historical note: all three steps above are long since done — desktop access arrived, the backend was built and tested, and the frontend was later wired to actually call it. This paragraph is left as-written rather than edited, per this project's "disclosed limitations over hidden ones" convention — it's a snapshot of a real constraint at the time, not a claim about current state. See the superseded-notice at the top of this file.)*

---

## 7. Decisions — locked in

As of this update, the three open questions from the original v7 draft are resolved:

- **LLM access:** your own Anthropic API key, used server-side by the `/api/refine` and `/api/ask` endpoints.
- **Persistence:** yes — share links via the Postgres `analyses` table as scoped in §3.4.
- **MCP tool:** yes — wrap as `recommend_stack(...)` per §3.5, so it's callable from Claude Desktop/Code directly.

All three require a live backend, which requires desktop access (a browser-only session can't host an API). Nothing further to decide here — this section is ready to build the moment that access is available; no need to re-ask these questions.
