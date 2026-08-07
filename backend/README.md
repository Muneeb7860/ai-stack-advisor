# AI Stack Advisor — v2 Backend

Optional backend for v2 features. **v1 (`../index.html`) works with zero backend calls and
must stay that way** (PRD NFR-5) — nothing here is a hard dependency for the core product.

## What's built vs. stubbed

| Feature | Status | Endpoint(s) |
|---|---|---|
| Share links | **Built, tested** | `POST /api/analyses`, `POST /api/analyses/{id}/share`, `GET /api/analyses/shared/{slug}` |
| LLM refinement | **Built, tested** | `POST /api/refine` — see `app/routers/refine.py` docstring for the constrained-reasoning design and a resolved gap (optional `analysis_id`) not covered by the original spec |
| Grounded follow-up Q&A | **Built, tested** | `POST /api/ask` — see `app/routers/ask.py` docstring; scoped structurally to one `analysis_id`, replays full conversation history each turn |
| MCP tool wrapper | Stub (raises on import) | `app/mcp/server.py` — spec in module docstring |

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

24 tests currently, all passing:
- `test_share.py` (7): health check, create/share/fetch round-trip, share idempotency (same
  slug on repeat calls), 404s on unknown analysis/slug, and a tripwire test that fails loudly
  if `app/mcp/server.py` (the one remaining stub) ever becomes importable without actually
  being built.
- `test_refine.py` (8): analysis creation-vs-reuse based on whether `analysis_id` is passed,
  the exact inputs forwarded to the model, the API key never appearing in the response,
  append-only persistence of `RefinementResult` across repeat calls, the input-length
  guardrail (422), and Anthropic API failures surfacing as 502 rather than a crash.
- `test_ask.py` (9): 404 on unknown analysis, the system prompt actually grounding in the
  analysis's requirement text/recommendations, question+answer persistence, conversation
  history replay across turns, strict per-analysis scoping (a second analysis never sees the
  first's history — the DDD 4.3 invariant), the API key never appearing in the response, the
  input-length guardrail (422), Anthropic failures surfacing as 502, and no orphaned
  question-with-no-answer row when the model call fails.

Both `test_refine.py` and `test_ask.py` monkeypatch the real Anthropic call
(`app.routers.refine._run_refinement` / `app.routers.ask._run_ask`) — no live API key or
network access needed to run either file.

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
4. MCP tool wrapper — the only milestone left. See `app/mcp/server.py`. Decision already made
   (see kickoff Q&A): port `detectSignals()`/`pickX()` to Python rather than shelling out to
   Node — port faithfully against the bugs already found/fixed in `../validation-report.md`,
   don't re-derive the logic from first principles.
