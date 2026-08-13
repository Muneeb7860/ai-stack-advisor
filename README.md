# 🧭 AI Stack Advisor

Describe a product or business requirement in plain language, get back a full technical + AI
architecture recommendation — cloud, database, compute, LLM strategy, RAG, guardrails, cost,
governance, and more — with confidence levels and cited reasoning, grounded in signals detected
in your text.

Two layers, built to work independently:

- **v1 — a single static HTML file.** A deterministic rule engine (`detectSignals()` + 45
  `pickX()` category functions) runs entirely in your browser. No server, no signup, no data
  leaves the page. This is the whole product if you never touch the backend.
- **v2 — an optional FastAPI + Postgres backend.** Adds LLM-assisted refinement of the rule
  engine's picks, grounded follow-up Q&A, shareable read-only links, and an MCP tool so an agent
  (Claude Desktop/Code) can call the same recommendation engine directly. Everything in v2 is
  opt-in — v1 never requires it, and every AI feature degrades to a friendly inline message
  instead of breaking if the backend isn't running.

---

## Quickstart

### v1 only — zero setup

```bash
open index.html
```

That's it. No build step, no dependencies, no server. Works offline.

### v2 — backend for refine/ask/share/MCP

```bash
cd backend
cp .env.example .env
docker compose up --build
```

Serves the API at `http://localhost:8000` (check `/health`), runs Alembic migrations
automatically, and hot-reloads on code changes. Then serve `index.html` from anything on an
origin listed in `backend/.env`'s `CORS_ORIGINS` (`http://localhost:8080` works out of the box:
`python3 -m http.server 8080` from the repo root) — the per-card "✨ Refine with AI" and
"💬 Ask a question" buttons will light up once the backend is reachable.

Every AI call needs **your own** Anthropic API key, entered once in the browser
(`sessionStorage` only, never sent anywhere but your own backend's one Anthropic call for that
request — see `backend/.env.example` for the full rationale). This app never asks for or stores
a shared server-side key.

See [`backend/README.md`](backend/README.md) for the full backend setup, test suite, and
troubleshooting (notably: a native Postgres already bound to port 5432 needs tests run inside
the container, not from the host).

---

## What it actually does

**Free-text or guided input.** Paste a requirement paragraph, or answer a 6-question wizard
(equal-weight choice, neither is the default) that synthesizes the same kind of paragraph the
rule engine already knows how to parse — no separate signal-mapping logic, same engine either
way.

**A full recommendation, not just a stack pick.** Cloud, gateway, IAM, languages, architecture
style, compute, messaging, service mesh, caching, database(s), containers, observability,
frontend, CI/CD, DNS, LLM strategy, RAG architecture, guardrails, MCP servers, cost optimization
and estimate, concurrency/throughput targets, and governance (KRA/KPI/SLA/reliability) — 16
sections, each with a confidence level and a cited "why."

**"Why this pick," made inspectable.** Every stack card shows exactly which detected signals
drove that specific recommendation — not just a confidence badge, the actual signal keys the
rule engine's function checked.

**Optional LLM refinement, with real cost shown.** Click "Refine with AI" on any card and the
model reviews the rule engine's picks against your original text — it can only adjust a pick if
it can cite something specific, never re-derives from scratch. Every refinement pass is kept
(not just the latest), so you can compare how the reasoning changed across repeated passes. Real
token usage from the Anthropic response is shown next to the existing directional cost estimate,
not just guessed.

**Grounded follow-up Q&A, independent of refine.** Ask a question about any card's recommendation
— it doesn't require having clicked refine first, just a real analysis to ground the answer in.
Both refine and ask are grounded against an 11-domain use-case knowledge base (two-stage TF-IDF
retrieval) when the requirement touches a covered domain.

**Shareable, read-only.** Share a completed analysis via a link (`?shared=SLUG`) — renders the
exact same 16-section view, minus the input form and AI buttons.

**Callable from an agent.** The same rule engine is exposed as an MCP tool
(`recommend_stack()`) — verified byte-for-byte against the browser JS via an automated diff
harness, not just code-reviewed.

---

## Project structure

```
index.html                    v1 — the entire client-side app (rule engine, UI, guided
                               mode, backend-wiring JS), single file by design
backend/                       v2 — FastAPI + Postgres + Alembic
  app/rule_engine.py            Python port of index.html's rule engine (verified identical)
  app/routers/{refine,ask}.py   LLM-assisted refinement / grounded Q&A endpoints
  app/retrieval.py               Two-stage TF-IDF RAG retrieval
  app/mcp/server.py              MCP tool wrapper
  tests/                         93 tests — see backend/README.md for the breakdown
docs/                          BRD, PRD, DDD, design docs, ADRs, use-case knowledge base
diagrams/                      C4 architecture diagram, ERD, UI mockups, guided-mode sketch
KICKOFF_BRIEF.md               Full decision record + current status — read this first if
                               you're picking this project back up
```

---

## Design principles worth knowing before you change anything

- **v1 must always work with zero backend dependency** (NFR-5). Nothing in the backend is
  allowed to become a hard requirement for the core recommendation flow.
- **The rule engine is the one source of truth.** `backend/app/rule_engine.py` is a disciplined
  *transliteration* of `index.html`'s JavaScript, not a re-derivation — every port has been
  verified against the live JS with an automated diff harness, zero tolerated differences. If
  you change the rule engine, change JS first, then port the exact same logic to Python.
- **Never a shared server-side API key.** Every LLM call carries the caller's own key in the
  request body; the backend passes it straight through and never logs or persists it. This was
  an explicit, discussed decision — don't "simplify" it into a shared key without raising that
  first.
- **Disclosed limitations over hidden ones.** Known gaps (TF-IDF vs. real embeddings, one
  documented xfail in the retrieval eval set, etc.) are recorded as tests/comments, not silently
  patched over or hidden.

For the full history of what's been decided, verified, and what's still open, start with
[`KICKOFF_BRIEF.md`](KICKOFF_BRIEF.md).

---

## Docs & diagrams

- [`diagrams/architecture-diagram.html`](diagrams/architecture-diagram.html) — C4 context +
  container diagrams, plus v1 and v2 data-flow sequence diagrams
- [`diagrams/erd.html`](diagrams/erd.html) — database schema
- [`diagrams/ui-mockup.html`](diagrams/ui-mockup.html) — annotated screen-by-screen UI spec
- [`docs/adr/0001-mcp-rule-engine-port.md`](docs/adr/0001-mcp-rule-engine-port.md) — how the
  Python rule-engine port was verified
- [`docs/use-case-knowledge-base/`](docs/use-case-knowledge-base/) — the RAG grounding corpus
  and its retrieval eval set

This is a heuristic advisor, not a substitute for architecture review. Recommendations are
directional starting points meant to be validated against real constraints — existing vendor
contracts, team skills, budget, latency SLAs, and compliance scope.
