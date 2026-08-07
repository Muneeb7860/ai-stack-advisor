# AI Stack Advisor — Backend Kickoff Brief

Handoff document for picking this up in a fresh Claude Code session on your own machine.
Paste the "Prompt to paste into Claude Code" section at the bottom to get going immediately
with full context — everything above it is the reasoning for someone (or some future you)
to read once, not every session.

## What already exists

- **`index.html`** — the whole shipped v1 product. Single-file client-side rule engine +
  Flow View canvas. Fully functional, zero backend dependency, and must stay that way
  (locked as PRD NFR-5 — don't let backend work turn this into a hard dependency).
- **`docs/`** — BRD, PRD, DDD (Word docs) + the generator scripts (`*_gen.js`) that produced
  them. PRD Section 7.7 and the Release Plan (Section 11) are the authoritative feature spec
  for what v2 needs to build.
- **`diagrams/`** — architecture C4 diagrams, ERD, and a Figma-style UI mockup (all
  self-contained HTML with inlined Mermaid).
- **`market-analysis.md`**, **`design-doc-v2.md`**, **`validation-report.md`** — background
  research, the v2 architecture design, and a log of bugs found/fixed during a validation
  pass on the rule engine (worth reading before touching `index.html`'s signal-detection
  logic — several non-obvious false-positive bugs were already found and fixed there).
- **`backend/`** — FastAPI + Postgres + Alembic scaffold. **All four v2 milestones from the
  PRD are now built and tested**: share-links (FR-28), `/api/refine` (FR-27), `/api/ask`, and
  the MCP tool wrapper (FR-29) — 42 passing tests, verified end-to-end against a real
  Postgres instance, not just unit-tested against mocks. The MCP tool's rule-engine port
  (`backend/app/rule_engine.py`) was verified byte-for-byte against `index.html`'s actual
  JavaScript across 13 scenarios before anything depended on it — see
  `docs/adr/0001-mcp-rule-engine-port.md`. **Read `backend/README.md` first** — it has the
  quickstart, test instructions, and full status detail this brief doesn't repeat.
  <br>_Status as of this update: this brief's original "prompt to paste into Claude Code"
  section (below) has been acted on in full — nothing from the original v2 scope remains
  unbuilt. It's kept for the historical record of what was originally handed off. What's next
  is genuinely open — see "What's next" below — not a continuation of a fixed build order._

## Decisions already made (don't re-litigate without a reason)

These were explicitly discussed and chosen, not just defaulted into — if you want to change
one, that's a real conversation to have with the user, not a silent implementation choice:

1. **API keys**: user's own Anthropic API key, passed per-request, never stored server-side.
   No shared server-side key. See `backend/.env.example` and the docstrings in
   `refine.py`/`ask.py` for the full reasoning.
2. **Database**: Postgres via Docker Compose for local dev, matching production — not SQLite.
   `backend/docker-compose.yml` is ready to go (`docker compose up --build`).
3. **Build order** (complete): share links → `/api/refine` → `/api/ask` → MCP tool wrapper.
   Each milestone was built and tested independently, in that order, per the original plan.
4. **Sharing has no auth** — `GET /api/analyses/shared/{slug}` is intentionally public and
   unauthenticated (matches the ERD's "Deliberately Excluded: no accounts" scope). Don't add
   auth to it without flagging that as a scope change against the PRD first.
5. **No revoke-share feature yet** — also intentional (ERD note), not an oversight.
6. **Rule engine port** (ADR 0001): `app/rule_engine.py` is a Python port of `index.html`'s
   JS, not a shared-source dependency — the two files WILL drift if one changes without the
   other. Any future change to `index.html`'s `detectSignals()`/`pickX()` functions needs the
   equivalent change in `rule_engine.py` in the same or a clearly-linked commit. No automated
   check currently catches drift between them (flagged as a real gap in the ADR, not silently
   accepted) — worth revisiting if this becomes a real maintenance cost.

## Known traps (things that will look like bugs in review if you don't know this context)

- `app/mcp/server.py` and `app/rule_engine.py` are BOTH real now — the old "raises
  NotImplementedError at import time" trap no longer applies (that was true of the stub, not
  the current file). See ADR 0001 for the port decision and how it was verified.
- `RefinementResult` is **append-only by design** — never update/overwrite a row, always
  insert a new one. This is what makes the "disagreement rate" success metric (BRD Section 7)
  measurable later. It'll look like a missing UPDATE endpoint in review; it isn't missing,
  it's intentional.
- `ConversationMessage` queries must filter by `analysis_id` in every single query, not just
  restrict via system-prompt wording — the DDD calls this out as a structural invariant, not
  a suggestion.
- `McpInvocation.analysis_id` is nullable and gets populated AFTER the row is first inserted
  (logged the instant the tool is called, before the rule engine has run) — a query that
  filters `WHERE analysis_id IS NOT NULL` expecting "all invocations" will silently miss any
  invocation whose rule-engine call failed. That's intentional (DDD 4.4), not a bug.
- `app/rule_engine.py`'s signal dict keys are deliberately camelCase (`onPrem`, not
  `on_prem`), unlike everything else in this Python codebase — this is a conscious exception
  (see that module's docstring) to keep it a diffable port of `index.html`, not an
  inconsistency to "fix."

## What's next

There is no fixed build order left — the BRD (Section 12, "High-Level Roadmap") frames what
comes after v2 as "v3 — informed by real user feedback, scope not yet defined." Candidates
raised in the BRD/PRD's own open-questions sections, none committed:
- **BR-7 (not met):** get the tool in front of real external users — flagged in the BRD as
  higher priority than further feature work once v2 ships.
- **BR-8 (not met):** commit to one of the three target segments (non-technical founder /
  developer / enterprise architect) instead of building for all three.
- Success-metrics instrumentation (completion/re-use/disagreement rate) without violating
  NFR-1's "no data leaves the browser unless the backend is explicitly used" posture — still
  an open tension, not resolved by anything built so far.
- Wiring the MCP server into an actual Claude Desktop/Code config for a real end-to-end test
  from inside an agent conversation (built and unit-tested, but not yet exercised through a
  live MCP client connection outside this session's own manual verification).

## Prompt to paste into Claude Code (historical — already acted on, kept for the record)

_This was the original kickoff prompt for this repo's first Claude Code session. All four v2
milestones (share links, `/api/refine`, `/api/ask`, MCP tool wrapper) are done now — 42
passing tests. A new session picking this up should read "What's next" above instead; there
is no fixed build order left to resume._

```
I'm continuing work on AI Stack Advisor, an app that recommends AI/tech architecture from a
free-text business requirement. Read KICKOFF_BRIEF.md at the repo root first for full
context, then backend/README.md for the backend specifically.

The backend scaffold is already built and tested: FastAPI + Postgres + Alembic, with the
share-links milestone (PRD FR-28) fully working — 7 passing tests in backend/tests/. Verify
it still works on your machine first: `cd backend && docker compose up --build`, confirm
`/health` responds, then `pytest tests/ -v` (needs the Postgres from docker compose running).

Once that's confirmed working, the next milestone is POST /api/refine — full spec is in
backend/app/routers/refine.py's docstring. Build it, write tests for it following the pattern
in tests/test_share.py, and don't move on to /api/ask until refine is solid.

Ask me before making any of the decisions listed under "Decisions already made" differently
than documented — those were deliberate, not defaults.
```
