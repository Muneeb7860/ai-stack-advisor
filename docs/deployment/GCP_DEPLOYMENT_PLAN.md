# GCP deployment plan

Status: **plan only — nothing provisioned, nothing deployed.** Written 2026-08-31 at the user's
explicit "strictly not now." No GCP resources exist for this project. Do not execute any of this
without a fresh go-ahead.

## Why deploy at all, and what the minimum actually is

The trigger is concrete: the tool is free for six months to collect feedback, and PR #54 added
`POST /api/harness-feedback`. That endpoint currently points at `http://localhost:8000`
(`index.html`'s `API_BASE`), so for anyone using the tool it silently discards every submission —
by design they see a thank-you regardless. **No backend, no feedback.**

That framing matters because it makes the first deployment much smaller than "deploy the backend":

| Feature | Needs to be deployed for feedback? | Why |
|---|---|---|
| `POST /api/harness-feedback` | **Yes** | The whole point |
| Postgres | **Yes** | Where feedback lands |
| `POST /api/analyses/{id}/disagreements` | Yes (free) | Same app, same DB — no extra work |
| Share links | Yes (free) | Same |
| `/api/refine`, `/api/ask` | **No** | Needs a user-supplied Anthropic key per request; works without RAG grounding (see below). Deploying them is fine, but they aren't why we're deploying |
| Ollama (embeddings + local-LLM fallback) | **No** | See "The Ollama question" |
| MCP server | No | Runs on the user's own machine by design |

**Recommendation: deploy the whole FastAPI app as-is** (it's one image; excluding routes would be
more work than including them) **but do not deploy Ollama**, and treat feedback capture as the
only thing that must actually work on day one.

## Target shape

- **Backend** → **Cloud Run** (container, scales to zero, HTTPS + a managed certificate for free).
  Fits the existing `backend/Dockerfile` almost as-is.
- **Database** → **Cloud SQL for PostgreSQL**, smallest tier. Connect over the Cloud SQL
  connector/Unix socket rather than exposing a public IP.
- **Frontend** (`index.html`) → **Cloud Storage bucket + Cloud CDN**, or Firebase Hosting. It's a
  single static file with no build step, so this is close to trivial. Firebase Hosting is simpler
  and gives HTTPS by default; a GCS bucket needs a load balancer in front for a custom domain +
  TLS.
- **Secrets** → **Secret Manager** for the database password only (see "What we don't need to
  secure").

Scale-to-zero matters here: outside of a launch spike this app will be idle most of the time, and
Cloud Run bills per request rather than per hour.

## What has to change in the repo before any of this works

**Status: done** (2026-09-01) — all of these were fixed locally, before any provisioning, since
none of them needed GCP to find or to fix. A fourth was found while doing so: the Dockerfile
hardcoded port 8000, but Cloud Run injects `$PORT` and routes to it, so a fixed port means the
container is up and nothing reaches it. Kept below as the record of what was wrong and why.

These were real gaps in the code, not boilerplate:

1. **`API_BASE` is hardcoded to `http://localhost:8000`** (`index.html`). This is the single
   most important change and the easiest to forget. It needs to become the deployed Cloud Run
   URL. Suggested: keep localhost as the default and override it for the hosted copy, so a
   developer opening the file locally still hits their own backend.
2. **The Dockerfile never runs migrations.** `docker-compose.yml` runs
   `alembic upgrade head && uvicorn ...` in its `command:`, but that's compose-only — the
   Dockerfile's `CMD` is just `uvicorn`. On Cloud Run the schema would simply never be created.
   Options, best first:
   - A separate one-off **Cloud Run job** (or `gcloud sql` migration step) run at deploy time.
     Cleanest: migrations are a deploy concern, not a per-instance startup concern.
   - An entrypoint that runs `alembic upgrade head` before `uvicorn`. Simpler, but every
     cold-started instance races the others to migrate. Acceptable at this scale; not correct
     in general.
   - **Do not** rely on `Base.metadata.create_all()` — it would drift from the alembic history
     that already has three revisions.
3. **`CORS_ORIGINS` must include the real frontend origin.** It currently defaults to
   `localhost:3000,localhost:8080`. If this is wrong, every browser call fails with an opaque
   CORS error while `curl` works fine — a genuinely confusing failure mode, so set it early.
4. **HTTPS on both sides.** A page served over HTTPS calling an `http://` API is blocked as mixed
   content. Cloud Run gives HTTPS by default, so this is mostly a reminder not to hand-write an
   `http://` `API_BASE`.
5. **`--reload` must not reach production.** It's in `docker-compose.yml`'s command, not the
   Dockerfile, so Cloud Run is already safe — noted only so nobody "helpfully" copies the compose
   command into the deploy config.

## The Ollama question

`app/retrieval.py` (embeddings for RAG grounding) and `app/llm_providers.py` (opt-in local-model
fallback) both call a local Ollama daemon. **There is no Ollama in this deployment and there
should not be one initially** — it would mean a GPU or a large always-on CPU instance, which is
wildly disproportionate to collecting feedback.

Verified in the code rather than assumed: this degrades gracefully. `_get_index()` catches
`OSError`/`httpx.HTTPError`/`RuntimeError`, sets a module-level sentinel, logs **once** (not per
request), and returns `None`. `/api/refine` and `/api/ask` still work — they just answer without
RAG grounding. The local-LLM fallback is opt-in twice over (deployment sets `LLM_PROVIDER=ollama`
*and* the caller passes `provider: "ollama"`), so leaving it at the default means it's simply
never offered.

**Consequence to accept knowingly:** refine/ask answers from the hosted backend will be
ungrounded — no citations from `docs/use-case-knowledge-base/`. If grounding turns out to matter
for the feedback round, the options are a managed embeddings API (breaks the "local-first, no
cloud embeddings" stance in `retrieval.py`'s docstring — a real product decision, not a config
change) or pre-computing embeddings at build time and shipping the vectors in the image.

## Security: the part that needs a decision, not just a checklist

`POST /api/harness-feedback` is **unauthenticated and world-writable**, which is correct for its
purpose (asking users to log in to leave feedback would collapse the response rate this feature
exists to protect). On a public URL that means anyone can POST arbitrary rows, and the endpoint's
whole value is the integrity of what's in the table.

Before going live, at minimum:

- **Rate limiting.** Cloud Armor in front of Cloud Run, or a simple per-IP limit in the app. Not
  optional on a public write endpoint.
- **Body size limits** — `comment` is capped at 4,000 chars by the schema, which helps, but the
  request body itself should be bounded at the edge too.
- Decide what to do about junk rows. The table is append-only by design (no update/delete route,
  deliberately), so cleanup means direct SQL. That's fine, but it should be a conscious choice
  rather than a discovery.

The same applies to `/api/analyses/{id}/disagreements` and share-link creation, which become
publicly writable at the same moment.

### What we don't need to secure

Worth stating because it removes the usual hardest part: **there is no server-side Anthropic API
key.** Per the locked decision in `.env.example` and `docs/design-doc-v2.md` §7, each request
carries the user's own key in the body, used once, never persisted or logged. So there is no
high-value credential in this deployment beyond the database password — a genuinely smaller blast
radius than a typical LLM-backed service.

## Data protection

New with this deployment: user data leaves user machines and lands in a database we operate.
Currently collected — `total`, `band`, per-component `answers`, `helpful`, `comment`, timestamp.
Deliberately **not** collected: no email, no user id, no IP stored by the app, no requirement text
from other modes.

That's a deliberately thin footprint, but "no identifiers" is a property of the current schema,
not a guarantee — the free-text `comment` field can contain anything a user chooses to type,
including their own contact details. Worth deciding before launch:

- Where the Cloud SQL instance lives (region choice is also a data-residency choice).
- Whether the hosted page needs a short privacy note. The in-product disclosure added in PR #54
  says what is sent; it does not say who stores it, where, or for how long. If this is offered
  publicly, that gap should close.
- A retention position. "Kept indefinitely" is a choice; it should be an explicit one.

## Rough cost

Directional only — verify against current pricing before committing:

- **Cloud Run**: near zero at this traffic. Scales to zero; the free tier likely covers a
  feedback-collection launch entirely.
- **Cloud SQL**: the real recurring cost, and it does **not** scale to zero. Smallest shared-core
  instance is on the order of **$8–15/month**, which dominates the bill.
- **Static hosting + egress**: cents.
- **Cloud Armor** (if used for rate limiting): has a per-policy monthly floor — check whether it's
  worth it versus in-app limiting at this scale.

If the Cloud SQL floor is unattractive for a six-month experiment, the honest alternative is a
managed Postgres with a free tier (Neon or Supabase — both already in this product's own vendor
catalog) with Cloud Run still hosting the API. Same code, `DATABASE_URL` is the only change.

## Sequence when this is greenlit

1. ~~Fix `API_BASE`, migrations-on-deploy, and `CORS_ORIGINS` in the repo first.~~ **Done** —
   plus the `$PORT` gap found alongside them. `API_BASE` now resolves from a
   `<meta name="api-base">` tag or a `window.__API_BASE__` global, falling back to localhost;
   the image runs migrations (opt out with `RUN_MIGRATIONS=0` for a separate job) and binds
   `$PORT`; and the effective CORS allowlist is logged at startup so the most confusing failure
   mode is visible in logs rather than only as an opaque browser error.
2. Provision Cloud SQL; set `DATABASE_URL` via Secret Manager.
3. Build and deploy the image to Cloud Run; run `alembic upgrade head` as a one-off job.
4. Verify `/health`, then a real feedback POST end-to-end from the deployed page.
5. Add rate limiting **before** publicising the URL, not after.
6. Deploy `index.html` to static hosting with the corrected `API_BASE`.
7. Only then promote the mode (the discoverability work that was deliberately deferred behind
   feedback capture).

## Explicitly out of scope for the first deployment

- Ollama / RAG grounding in the cloud (see above).
- Any admin or reporting UI for reading feedback — `psql` is sufficient until there's data worth
  building a dashboard for.
- Autoscaling tuning, multi-region, IaC/Terraform. A single region and console-or-`gcloud` setup
  is proportionate to a six-month experiment; codifying infrastructure that may be torn down is
  premature.
- CI/CD auto-deploy from `master`. Manual deploys are fine at this cadence and one less thing to
  debug during launch.
