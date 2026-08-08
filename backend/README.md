# AI Stack Advisor — v2 Backend

Optional backend for v2 features. **v1 (`../index.html`) works with zero backend calls and
must stay that way** (PRD NFR-5) — nothing here is a hard dependency for the core product.

## What's built vs. stubbed

| Feature | Status | Endpoint(s) |
|---|---|---|
| Share links | **Built, tested** | `POST /api/analyses`, `POST /api/analyses/{id}/share`, `GET /api/analyses/shared/{slug}` |
| LLM refinement | **Built, tested** | `POST /api/refine` — see `app/routers/refine.py` docstring for the constrained-reasoning design, RAG grounding, and a resolved gap (optional `analysis_id`) not covered by the original spec |
| Grounded follow-up Q&A | **Built, tested** | `POST /api/ask` — see `app/routers/ask.py` docstring; scoped structurally to one `analysis_id`, replays full conversation history each turn, RAG-grounded on the follow-up question |
| RAG retrieval | **Built, tested** | `app/retrieval.py` — two-stage TF-IDF retrieval over `../docs/use-case-knowledge-base/`, backs both endpoints above; see `RETRIEVAL-PROTOTYPE-FINDINGS.md` in that folder for the design rationale and `tests/test_retrieval_eval.py` for the 21-case eval (20 pass, 1 disclosed limitation) |
| MCP tool wrapper | **Built, tested** | `app/mcp/server.py` — `recommend_stack()` tool, backed by `app/rule_engine.py` (Python port of `index.html`'s rule engine, verified against it — see `../docs/adr/0001-mcp-rule-engine-port.md`) |

Full requirement traceability: `../docs/AI-Stack-Advisor-PRD.docx` FR-27/28/29, the ERD
(`../diagrams/erd.html`), and the DDD (`../docs/AI-Stack-Advisor-DDD.docx`).

## Quickstart (Docker — recommended)

```bash
docker compose up --build
```

This starts Postgres, runs `alembic upgrade head` automatically, and serves the API on
`http://localhost:8000` with hot reload. Check `http://localhost:8000/health`.

## Quickstart (no Docker)

Needs a local Postgres reachable at the URL in `.env` (copy `.env.example` first).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit if your local Postgres isn't the default advisor/advisor/advisor
alembic upgrade head
uvicorn app.main:app --reload
```

## Running tests

```bash
# needs the same live Postgres as above
pytest tests/ -v
```

85 tests currently (83 passing, 1 xfailed by design, 1 xpassed):
- `test_share.py` (7): health check, create/share/fetch round-trip, share idempotency (same
  slug on repeat calls), 404s on unknown analysis/slug, and a sanity check that the MCP
  server module is fully built (replaces the old import-time-stub tripwire now that there's
  nothing left stubbed).
- `test_refine.py` (11): analysis creation-vs-reuse based on whether `analysis_id` is passed,
  the exact inputs forwarded to the model, the API key never appearing in the response,
  append-only persistence of `RefinementResult` across repeat calls, the input-length
  guardrail (422), Anthropic API failures surfacing as 502 rather than a crash, and RAG
  grounding (`_build_grounding_context`) returning citable content for covered domains, empty
  for zero-overlap queries, and never gating the core refine flow either way.
- `test_ask.py` (12): 404 on unknown analysis, the system prompt actually grounding in the
  analysis's requirement text/recommendations, question+answer persistence, conversation
  history replay across turns, strict per-analysis scoping (a second analysis never sees the
  first's history — the DDD 4.3 invariant), the API key never appearing in the response, the
  input-length guardrail (422), Anthropic failures surfacing as 502, no orphaned
  question-with-no-answer row when the model call fails, and RAG grounding keyed on the
  follow-up question (not the original requirement text) per the ingestion guide's own
  "anti-patterns answer 'is X okay?' phrasing" note.
- `test_rule_engine.py` (23): regression tests for `app/rule_engine.py`, one per bug
  `../validation-report.md` found and fixed in the original JS (negation handling, on-prem
  override, warehouse detection, team-size conflicts, the small-team regex fallback), one per
  new dimension from the frontend-expansion pass (live-multiplayer, collaborative editing,
  video conferencing, social-feed fan-out, geospatial, fixed-scope delivery, cost estimator,
  the `compute_tier` replacement of `vram_tier`, the vendor-comparison layer), plus structural
  checks (all recommendation categories present, signal dict keys stay camelCase matching
  `index.html`). Pure functions, no DB/network needed.
- `test_mcp_server.py` (8): invocation logging (with and without a client name), the
  nullable-then-populated `analysis_id` (DDD 4.4), logging still happening even when the rule
  engine raises, and two regression tests for a real bug a validation round's manual
  end-to-end testing caught: the client-name extraction read `.clientInfo` (camelCase) on a
  pydantic model whose real Python attribute is `.client_info` (snake_case) — silently
  swallowed by a broad exception handler instead of erroring, so no unit test calling the
  function with a hand-built argument could have caught it. Only driving a real stdio
  JSON-RPC session end-to-end and checking what actually landed in Postgres did.
- `test_retrieval_eval.py` (23): the 21-case retrieval eval set from
  `../docs/use-case-knowledge-base/` (direct retrieval, anti-pattern "is X okay?" phrasing,
  cross-document queries, decision-point boundary cases, negative controls) wired to the real
  `app/retrieval.py` implementation — 20 genuine passes, 1 xfail (a disclosed TF-IDF-vs-real-
  embeddings paraphrase limitation, not silently hidden), a structural check that a
  Signals/triggers chunk is never returned as citable content for any of the 21 queries, and
  a regression test (found during audit) confirming a genuinely missing corpus degrades to
  "no grounding" instead of a 500 — see `app/retrieval.py`'s `_get_index()` docstring.

`test_refine.py` and `test_ask.py` monkeypatch the real Anthropic call
(`app.routers.refine._run_refinement` / `app.routers.ask._run_ask`) — no live API key or
network access needed to run either file. `test_mcp_server.py` calls
`app.mcp.server._log_and_recommend()` directly rather than going through the MCP
transport/protocol layer — see that module's docstring for why.

Note: if you're on a machine with a native Postgres already bound to host port 5432 (Docker's
own `db` container will lose that port silently — you'll get a real `password authentication
failed` from the *other* Postgres, not a connection error, which is a confusing failure mode
if you don't know to look for it), run tests inside the container instead of against
`localhost:5432` from the host:
```bash
docker exec -e DATABASE_URL=postgresql+psycopg2://advisor:advisor@db:5432/advisor \
  <api-container-name> python -m pytest tests/ -v
```
`tests/` is bind-mounted into the container alongside `app/` and `alembic/` for this reason.

## Schema changes

This project uses Alembic. If you change `app/models.py`:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

Then **update the ERD (`../diagrams/erd.html`) and DDD to match** — do this every time, not
just when it's convenient. A previous docs pass already found and fixed a case where the
generated PRD had drifted from what was actually shipped; don't let this schema do the same
thing to the ERD.

## API key handling (read before touching `/api/refine` or `/api/ask`)

This backend does **not** hold a shared Anthropic API key anywhere in its own environment.
Each request that needs an LLM call carries the user's own key in the request body, the
backend passes it straight to the Anthropic SDK for that one call, and it's never logged or
persisted. See `.env.example` for the full reasoning — this was an explicit, discussed
decision (not a default), so don't "simplify" it into a shared server-side key without
raising that with the user first.

## Build order (as agreed)

1. ✅ Share links — done.
2. ✅ `/api/refine` — done. See docstring in `app/routers/refine.py`, including a design gap
   it resolves explicitly (the original spec's request body had no `analysis_id`, but
   `RefinementResult` requires one — resolved as "optional; omitted creates a new Analysis").
3. ✅ `/api/ask` — done. See docstring in `app/routers/ask.py`. Also fixes a pre-existing
   doc-citation bug: the original spec cited "design-doc-v2.md Section 9.2," which doesn't
   exist in that file — the real cites are design-doc-v2.md §3.2 (refine) / §3.3 (ask), and
   PRD §9.2 (the section number that was actually meant).
4. ✅ MCP tool wrapper — done. See `app/mcp/server.py` and `app/rule_engine.py` (the Python
   port of `index.html`'s rule engine — verified against the actual JS with zero diffs, and
   re-verified after a later frontend-expansion pass — see
   `../docs/adr/0001-mcp-rule-engine-port.md` for both rounds).
5. ✅ RAG grounding retrofit — done, added after a parallel frontend/knowledge-base session
   produced `../docs/use-case-knowledge-base/`. See `app/retrieval.py` and both routers'
   `_build_grounding_context()` functions.

## MCP tool (`recommend_stack`)

Run the server: `python -m app.mcp.server` (stdio transport). Point Claude Desktop's or
Claude Code's MCP config at this command (needs `DATABASE_URL` set, same as the API). Once
connected, `recommend_stack(requirement_text: str)` returns the same `{signals,
recommendations}` shape as `POST /api/analyses` expects as input — the same rule engine
`index.html` runs client-side, just callable from inside an agent conversation instead of a
web form.

Every invocation is logged as an `McpInvocation` row the instant the tool is called — before
the rule engine has necessarily produced a result (DDD 4.4) — including the calling client's
self-reported name (e.g. "Claude Desktop") when available. A successful call also persists
an `Analysis` row and links it back to the invocation; a failed call (e.g. empty
`requirement_text`) still leaves the invocation logged, just with `analysis_id` left null.
