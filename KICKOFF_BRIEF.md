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
- **`backend/`** — FastAPI + Postgres + Alembic scaffold. Share-links (PRD FR-28),
  `/api/refine` (PRD FR-27), and `/api/ask` are all built and tested (24 passing tests,
  verified end-to-end against a real Postgres instance — not just unit-tested against mocks).
  The MCP tool wrapper is the only remaining stub, spec in its module docstring. **Read
  `backend/README.md` first** — it has the quickstart, test instructions, and build-order
  detail this brief doesn't repeat.
  <br>_Status as of this update: this brief's original "prompt to paste into Claude Code"
  section (below) has already been acted on in full — share links, refine, and ask are all
  done. It's kept for the historical record of what was originally handed off; treat
  `backend/README.md`'s "Build order" section as the current source of truth — the only
  thing left is the MCP tool wrapper._

## Decisions already made (don't re-litigate without a reason)

These were explicitly discussed and chosen, not just defaulted into — if you want to change
one, that's a real conversation to have with the user, not a silent implementation choice:

1. **API keys**: user's own Anthropic API key, passed per-request, never stored server-side.
   No shared server-side key. See `backend/.env.example` and the docstrings in
   `refine.py`/`ask.py` for the full reasoning.
2. **Database**: Postgres via Docker Compose for local dev, matching production — not SQLite.
   `backend/docker-compose.yml` is ready to go (`docker compose up --build`).
3. **Build order**: share links (done) → `/api/refine` (done) → `/api/ask` (done) → MCP tool
   wrapper. Each milestone was chosen to be buildable and testable independently; don't skip ahead to MCP
   before refine/ask exist, since the MCP wrapper is supposed to expose the same recommend
   logic those endpoints will eventually also call.
4. **Sharing has no auth** — `GET /api/analyses/shared/{slug}` is intentionally public and
   unauthenticated (matches the ERD's "Deliberately Excluded: no accounts" scope). Don't add
   auth to it without flagging that as a scope change against the PRD first.
5. **No revoke-share feature yet** — also intentional (ERD note), not an oversight.

## Known traps (things that will look like bugs in review if you don't know this context)

- `app/mcp/server.py` raises `NotImplementedError` at **import time** — that's deliberate
  (a loud placeholder, not broken code). Don't import it from anywhere until it's real.
- The v1 rule engine (`index.html`'s `detectSignals()`/`pickX()` functions) already went
  through a recursive audit that found and fixed several real bugs (false-positive keyword
  matches, a same-report contradiction between two cards, an on-prem detection edge case).
  If the MCP wrapper re-implements this logic in Python from scratch instead of porting it
  faithfully, it will likely reintroduce bugs that were already found and fixed once.
- `RefinementResult` is **append-only by design** — never update/overwrite a row, always
  insert a new one. This is what makes the "disagreement rate" success metric (BRD Section 7)
  measurable later. It'll look like a missing UPDATE endpoint in review; it isn't missing,
  it's intentional.
- `ConversationMessage` queries must filter by `analysis_id` in every single query, not just
  restrict via system-prompt wording — the DDD calls this out as a structural invariant, not
  a suggestion.

## Prompt to paste into Claude Code (historical — already acted on, kept for the record)

_This was the original kickoff prompt for this repo's first Claude Code session. Share links
`/api/refine`, and `/api/ask` are all done now (24 passing tests) — a new session picking
this up should use `backend/README.md`'s "Build order" section instead, which starts at
the MCP tool wrapper, the only milestone left._

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
