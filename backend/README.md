# AI Stack Advisor — v2 Backend

Optional backend for v2 features. **v1 (`../index.html`) works with zero backend calls and
must stay that way** (PRD NFR-5) — nothing here is a hard dependency for the core product.

## What's built vs. stubbed

| Feature | Status | Endpoint(s) |
|---|---|---|
| Share links | **Built, tested** | `POST /api/analyses`, `POST /api/analyses/{id}/share`, `GET /api/analyses/shared/{slug}` |
| LLM refinement | Stub (501) | `POST /api/refine` — spec in `app/routers/refine.py` docstring |
| Grounded follow-up Q&A | Stub (501) | `POST /api/ask` — spec in `app/routers/ask.py` docstring |
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

7 tests currently, all passing — health check, create/share/fetch round-trip, share
idempotency (same slug on repeat calls), 404s on unknown analysis/slug, and a tripwire test
that fails loudly if `/api/refine` or `/api/ask` ever silently stop being 501 without
actually being implemented.

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

1. ✅ Share links — done, this milestone.
2. `/api/refine` — see docstring in `app/routers/refine.py`.
3. `/api/ask` — see docstring in `app/routers/ask.py`. Builds on #2's prompt-constraint pattern.
4. MCP tool wrapper — see `app/mcp/server.py`. Needs a Python port-vs-shell-out decision for
   the v1 rule engine first (documented as an open question in that file — write it up as an
   ADR when you decide).
