# AI Stack Advisor — v2 Backend

Optional backend for v2 features. **v1 (`../index.html`) works with zero backend calls and
must stay that way** (PRD NFR-5) — nothing here is a hard dependency for the core product.

## What's built vs. stubbed

| Feature | Status | Endpoint(s) |
|---|---|---|
| Share links | **Built, tested** | `POST /api/analyses`, `POST /api/analyses/{id}/share`, `GET /api/analyses/shared/{slug}` |
| LLM refinement | **Built, tested** | `POST /api/refine` — see `app/routers/refine.py` docstring for the constrained-reasoning design, RAG grounding, and a resolved gap (optional `analysis_id`) not covered by the original spec |
| Grounded follow-up Q&A | **Built, tested** | `POST /api/ask` — see `app/routers/ask.py` docstring; scoped structurally to one `analysis_id`, replays full conversation history each turn, RAG-grounded on the follow-up question |
| RAG retrieval | **Built, tested** | `app/retrieval.py` — two-stage retrieval (routing + content, see module docstring) over `../docs/use-case-knowledge-base/`, backed by ChromaDB + a local Ollama embedding model (`nomic-embed-text`), not TF-IDF anymore; backs both endpoints above. `tests/test_retrieval_eval.py`'s 23-test eval: **before** (TF-IDF) 21 passed/1 xfailed/1 xpassed, **after** (embeddings) 20 passed/3 xfailed/0 xpassed — the embeddings swap fixed the one paraphrase-gap case TF-IDF was known to fail, and surfaced two new disclosed semantic-neighbor-confusion cases in exchange; see that file's `KNOWN_XFAIL_IDS`/`_XFAIL_REASONS` for the real per-case detail |
| Local-model fallback | **Built, tested (opt-in, degraded)** | `POST /api/refine` / `POST /api/ask` with `provider: "ollama"` — see `app/llm_providers.py`. Claude stays primary/default; this only activates when the deployment sets `LLM_PROVIDER=ollama` AND the caller explicitly opts in per-request. Real measured structured-output pass rates against `qwen2.5:7b`/`mistral:latest` (native tool-calling + a JSON-parse fallback) are in that module's docstring — shipped as a genuine fallback for both endpoints, not narrowed to ask-only, because the measured combined reliability supported it |
| MCP tool wrapper | **Built, tested — exercised end-to-end over real stdio** | `app/mcp/server.py` — `recommend_stack()` tool, backed by `app/rule_engine.py` (Python port of `index.html`'s rule engine, verified against it — see `../docs/adr/0001-mcp-rule-engine-port.md`). A real stdio JSON-RPC client (initialize → tools/list → tools/call) confirmed it end-to-end; found in the process that the `mcp` SDK does not inherit arbitrary env vars into the server subprocess by default (`mcp.client.stdio.get_default_environment()` only passes an allowlist like `PATH`/`HOME`) — a real Claude Desktop/Code MCP config for this server needs an explicit `"env": {"DATABASE_URL": "..."}` block, or it falls back to `config.py`'s default and silently can't reach Postgres |

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

93 tests currently (90 passing, 3 xfailed by design — see `test_retrieval_eval.py` below for
why that count changed from the TF-IDF era):
- `test_guided_synthesis.py` (7): validates `index.html`'s guided-mode wizard synthesis
  (`synthesizeRequirementText()`) via a Python mirror, verified byte-for-byte against the real
  JS before being trusted — 7 scenarios covering every wizard branch including the skip-logic
  case, multi-select compliance/AI, and a free-text override with negation.
- `test_share.py` (8): health check, create/share/fetch round-trip, share idempotency (same
  slug on repeat calls), 404s on unknown analysis/slug, a sanity check that the MCP
  server module is fully built (replaces the old import-time-stub tripwire now that there's
  nothing left stubbed), and a CORS test confirming `/health` actually returns
  `access-control-allow-origin` for a whitelisted origin — the frontend's guided-mode +
  refine/ask/share wiring (see `../index.html`, `../KICKOFF_BRIEF.md` "What's next") depends on
  this working, not just being configured.
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
  `app/retrieval.py` implementation — a structural check that a Signals/triggers chunk is
  never returned as citable content for any of the 21 queries, and a regression test (found
  during audit) confirming a genuinely missing corpus degrades to "no grounding" instead of a
  500. Real before/after numbers from the TF-IDF → ChromaDB/embeddings migration: **before**
  21 passed / 1 xfailed (case 15, a paraphrase gap) / 1 xpassed (case 21, a negative-control
  false positive that happened to squeak under threshold); **after** 20 passed / 3 xfailed —
  case 15 is now a genuine pass (embeddings closed that paraphrase gap, the whole reason for
  the migration), case 21 stays a disclosed gap, and two NEW disclosed gaps appeared (case 7:
  a semantic-neighbor confusion — "fraud-scoring model" vs. a marketplace doc's "Trust &
  safety pipeline" section; case 20: a negative control whose score now sits above the
  weakest genuine hit, a known property of embedding cosine similarity's narrower score band).
  See that file's `KNOWN_XFAIL_IDS`/`_XFAIL_REASONS` for the full per-case reasoning — nothing
  here was tuned away to force green.

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
6. ✅ Retrieval upgraded from TF-IDF to embeddings (ChromaDB + local Ollama
   `nomic-embed-text`) — see `app/retrieval.py`'s module docstring and the retrieval-eval
   numbers above.
7. ✅ Opt-in local-model (Ollama) fallback for `/api/refine` and `/api/ask` — see
   `app/llm_providers.py` and "Local-model fallback" below. Claude remains primary/default.

## MCP tool (`recommend_stack`)

Run the server: `python -m app.mcp.server` (stdio transport). Point Claude Desktop's or
Claude Code's MCP config at this command, with an explicit `"env": {"DATABASE_URL": "..."}`
block — **do not assume the server subprocess inherits your shell's environment.** Verified by
driving a real stdio JSON-RPC session end-to-end (initialize → tools/list → tools/call via the
`mcp` Python SDK's own `ClientSession`/`stdio_client`, not just the in-process unit tests):
`mcp.client.stdio.get_default_environment()` only passes an allowlist (`PATH`, `HOME`, and a
few others) into the subprocess, not the full parent environment, so a config that omits the
`env` block gets a server that silently falls back to `config.py`'s default `DATABASE_URL`
(`localhost:5432`) and fails with a Postgres connection error the moment the tool is actually
called — `tools/list` still succeeds either way, so this only shows up on the first real
`recommend_stack` call, not at connection time. With `DATABASE_URL` passed explicitly, a real
end-to-end call (`"Fintech startup, small team, real-time fraud detection, HIPAA not
required."`) returned the full `{signals, recommendations}` payload and a corresponding
`McpInvocation` row was confirmed in Postgres afterward. Once connected correctly,
`recommend_stack(requirement_text: str)` returns the same `{signals, recommendations}` shape
as `POST /api/analyses` expects as input — the same rule engine `index.html` runs
client-side, just callable from inside an agent conversation instead of a web form.

Every invocation is logged as an `McpInvocation` row the instant the tool is called — before
the rule engine has necessarily produced a result (DDD 4.4) — including the calling client's
self-reported name (e.g. "Claude Desktop") when available. A successful call also persists
an `Analysis` row and links it back to the invocation; a failed call (e.g. empty
`requirement_text`) still leaves the invocation logged, just with `analysis_id` left null.

## Local-model fallback (opt-in, clearly degraded — Claude stays primary)

`POST /api/refine` and `POST /api/ask` accept `provider: "ollama"` on the request body to
route that one call to a local Ollama model instead of Claude. Off by default on both sides —
the deployment must set `LLM_PROVIDER=ollama` (`.env`) AND the caller must explicitly pass
`provider: "ollama"` per request; setting the env var alone does not reroute existing traffic.
See `app/llm_providers.py`'s module docstring for the real test methodology and numbers this
is based on: structured tool-calling against `REFINEMENT_TOOL`'s exact schema was run for real
(not assumed) against the two largest locally-installed models, `qwen2.5:7b` and
`mistral:latest`, 3 requirement/recommendation cases × 3 repeated runs each, with `num_ctx`
explicitly set to 8192 to rule out Ollama's default context window as a confound (both models'
native context is 32768; ruled out, not assumed away). Native `tool_calls` alone: 8/9 (89%)
for qwen, 4/9 (44%) for mistral — mistral's Ollama chat template frequently emits the function
call as JSON text in the message body instead of the structured `tool_calls` field even though
the API nominally supports tools. Adding a fallback JSON-parse of the message content when
`tool_calls` is empty/malformed (`_extract_tool_result()`) raised both to 8/9 and 9/9
respectively across the sampled runs. Shipped as a real fallback for **both** endpoints (not
narrowed to ask-only) because the measured reliability supported it — not because it was
assumed to work. Every local-model response is prefixed with a visible
`[Local model — offline/degraded mode, not Claude...]` disclaimer and carries
`provider: "ollama"` in the JSON response so a caller can render it with visibly lower
confidence than a Claude-backed result. `/api/refine`'s local path retries once on a parse
failure before surfacing a 502; `/api/ask`'s local path is plain prose (no schema to satisfy),
inherently lower-risk. Both check that the configured `OLLAMA_MODEL` is actually installed
before calling it, and fail with a clear `ollama pull <model>` message if not — no attempt to
silently substitute a different model.

Also new: `app/retrieval.py`'s RAG grounding now runs on ChromaDB + a local Ollama embedding
model (`nomic-embed-text`, default `OLLAMA_EMBED_MODEL`) instead of TF-IDF — see that module's
docstring for the design (the two-stage routing/content split is unchanged) and the
"Running tests" section above for real before/after eval numbers.
