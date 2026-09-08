# Deploying the backend

The frontend is already live on GitHub Pages and needs nothing. This is about the API that
`/api/refine`, `/api/ask`, saved analyses and share links depend on — everything that has been
dark since launch because `index.html` resolved its API base to `http://localhost:8000`.

Everything below was run end to end against the real image on 2026-09-08. Where a step says
"verified", that is what it means.

## What you need

A Render account. Nothing else — no API keys, no secrets.

**There is no Anthropic key in this deployment, deliberately.** Callers pass their own per request
(`anthropic_api_key` in the body, read in `routers/ask.py` and `routers/refine.py`), so the service
holds no LLM credential and carries no per-request cost. Do not add a shared server-side key: the
"bring your own key, we store nothing" posture is a product decision, recorded in `.env.example`.

## Deploy

1. **Render → New → Blueprint**, point it at `Muneeb7860/ai-stack-advisor`.
   It reads `render.yaml` and creates two linked resources: the web service (built from
   `backend/Dockerfile`) and a managed Postgres. Nothing needs filling in by hand.

2. **Check the hostname Render assigns.** `index.html` has
   `<meta name="api-base" content="https://ai-stack-advisor-api.onrender.com">` pre-wired. If
   Render appends a suffix for uniqueness, update that tag and push —
   `test_deployed_page_reaches_a_backend.py` fails on a localhost or path-carrying value, but it
   cannot know Render renamed your service.

3. **Confirm it is live**, replacing the host if step 2 changed it:

   ```
   curl https://ai-stack-advisor-api.onrender.com/health
   ```

   Expect `{"status":"ok"}`. Render will not route traffic until this returns 200, so a failing
   deploy shows up here rather than as a half-working service.

## What was verified locally, and how

Run as `docker run` with **no bind mounts** — the same shape Render uses, where the code is baked
into the image rather than mounted:

| Check | Result |
|---|---|
| Image builds from `backend/Dockerfile` | `backend-api:latest`, 865 MB |
| `postgres://` URL accepted | migrations and app both start (see below) |
| `alembic upgrade head` | ran to `c91d4a7e2f18` |
| Uvicorn binds `$PORT` | `Uvicorn running on http://0.0.0.0:8000` |
| `GET /health` | `{"status":"ok"}` |
| CORS from `https://muneeb7860.github.io` | 200 |
| CORS from an unlisted origin | 400 (refused) |
| `POST /api/analyses` | 201 |
| Tracebacks / 500s in the whole run | 0 |

The `postgres://` line matters more than it looks. Render's managed Postgres hands out that legacy
scheme; SQLAlchemy 2.x removed the alias, so `create_engine()` raises at import — from `db.py`,
before a single request — and the host reports it only as a container that "won't start". It would
have failed twice over, because the image runs `alembic upgrade head` before uvicorn and alembic
reads the same setting. `Settings._normalise_pg_scheme` rewrites it; the verification above used a
literal `postgres://` URL specifically to prove that path.

## Known limitations of this deployment

**No RAG grounding.** `retrieval.py` embeds the knowledge-base corpus through a local Ollama
daemon, which no managed host provides. `/api/refine` and `/api/ask` still work and still answer —
they just answer without corpus citations. This degrades rather than breaking: `_get_index()`
returns `None` instead of raising, and neither endpoint 500s. Verified with no corpus present at
all: zero tracebacks.

**The corpus is not in the image.** `retrieval.py` resolves it as `../../docs` relative to itself,
a sibling of `backend/`, while the Docker build context is `backend/` only. Moot while retrieval is
off, and it must be fixed in the same change that restores embeddings — not before, or you ship a
larger image for no benefit.

**Free tier sleeps.** The first request after idle takes roughly 50 seconds. The frontend probes
`/health` once on load, so a cold start can mark the backend unavailable until the page is
reloaded. Worth knowing before reading it as a failure.

**Render's free Postgres expires after 30 days.** Fine for proving the loop works; not a permanent
home for anything you want to keep.

## Rollback

Render keeps previous deploys — roll back from the service's Deploys tab. If the frontend is the
problem rather than the service, reverting the `<meta name="api-base">` tag returns the page to
its previous behaviour: the backend features go dark again, and the core analysis, which never
touches the network, is unaffected either way.

## Local development

Unchanged, and still the fastest way to work on this:

```
cd backend && docker compose up -d --build
```

That stack bind-mounts `app/`, `alembic/` and the docs corpus, so retrieval works locally and
edits reload. One environment note: on colima with virtiofs, alembic can fail to read the mounted
`env.py` with `OSError: [Errno 35] Resource deadlock avoided`. That is the bind mount, not the
code — the same image runs cleanly with no mounts, which is what Render does.
