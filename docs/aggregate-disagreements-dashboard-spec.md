# Aggregate disagreements dashboard — spec

Status: **design spec, not built**. `docs/challenge-this-pick-spec.md` explicitly deferred this
("a real, separate feature needing its own scoping... once there's actual data to look at") —
this document is that scoping pass. Every claim about the current codebase below was checked
directly (`backend/app/models.py`, `backend/app/routers/`, `backend/app/main.py`,
`backend/tests/conftest.py`, `backend/alembic/versions/`) before writing this, not assumed from
the earlier spec's own framing.

## What exists today (verified)

- **`Disagreement`** (`backend/app/models.py`): `id`, `analysis_id` (FK → `analyses.id`, no ORM
  `relationship()` either direction — a bare column), `category`, `current_pick`,
  `proposed_alternative`, `reason`, `created_at`. Append-only, no update/delete route.
- **`Analysis`**: `id`, `requirement_text`, `signals` (JSONB), `recommendations` (JSONB),
  `share_slug`, `created_at`, `updated_at`. **No user/session/segment field anywhere.**
- **One route touches this table**: `POST /api/analyses/{analysis_id}/disagreements`
  (`backend/app/routers/disagreements.py`) — write-only, no GET, no listing, no aggregation.
- **No auth mechanism exists anywhere in this backend.** Every `Depends(...)` across every
  router is `Depends(get_db)`. `main.py`'s CORS config is explicit about this being deliberate:
  `allow_credentials=False  # no auth/cookies in this design`. The one precedent for a read
  endpoint, `share.py`'s `GET /api/analyses/shared/{slug}`, has a docstring stating point-blank:
  *"Public, unauthenticated, read-only — this is the ENTIRE access-control model... by design.
  Don't add auth here without first updating the ERD/PRD."* There is no admin role, no API key
  gate, no session anywhere to extend.
- **No segment/persona field is captured anywhere in code** — not on `Analysis`, not on
  `Disagreement`, not in the wizard, not in localStorage. `docs/gtm-beta-outreach-plan.md`'s own
  plan for BR-8's segment-concentration metric is a **manual, out-of-band intake form**, not
  anything the app records. This matters: an aggregate dashboard cannot break disagreements down
  by segment today, full stop — that data doesn't exist in this table or anywhere adjacent to it.
- **No second frontend page/admin surface exists.** `index.html` and `landing.html` are the only
  two pages in the product. Building a dashboard page has zero precedent to extend.
- **Migration chain**: `b6376436f359` (root) → `bef404fe7abd` (adds `disagreements`, confirmed
  current head, nothing follows it).

## The real decision this spec exists to force: is this endpoint public?

A GET endpoint that lists every `Disagreement` row product-wide — including `current_pick`,
`proposed_alternative`, and free-text `reason` — is, functionally, a feed of what real
companies' actual architecture decisions and internal reasoning look like. Copying `share.py`'s
"public, unauthenticated, by design" precedent here would mean anyone who finds the URL can read
every beta tester's stated disagreements. That precedent exists for `share.py` because a share
link is *opt-in disclosure of one's own analysis* — this would be the opposite: exposing
everyone's data to whoever asks. **These are not the same access-control shape and this spec
does not copy that precedent.**

Two real options, not a false choice — pick one before writing any code:

1. **No new network endpoint at all (recommended for v1).** A local, read-only script
   (`backend/scripts/disagreements_report.py`) that connects to the DB directly — the same
   connection string used everywhere else in `backend/`, no new dependency — and prints/exports
   an aggregate summary. Zero new attack surface, zero auth to build or get wrong, and it's
   genuinely sufficient at beta scale (`docs/gtm-beta-outreach-plan.md`'s own Weeks 4-6 section
   already assumes "query the `disagreements` table... manually"). This is that query, made
   reusable instead of ad hoc.
2. **A real gated HTTP endpoint + a small static admin page**, if this needs to be checked from
   somewhere other than wherever the DB is reachable from (e.g. checking it from a phone, or
   sharing read access with someone who shouldn't get DB credentials). This requires designing
   actual auth — even a minimal single-shared-secret header (`X-Admin-Token` compared against an
   env var, no user accounts) is new infrastructure this codebase has never had, and is a real
   security surface to get right, not a small addition. Not scoped further here; only worth
   doing if option 1 turns out to be insufficient in practice.

**This spec proceeds on option 1.** If you want option 2 instead, say so before implementation —
it changes the shape of everything below.

## Scope for v1 (the script)

**`backend/scripts/disagreements_report.py`** — a standalone script (run via
`python -m scripts.disagreements_report` or similar from `backend/`), using the same
`SessionLocal`/`engine` as the app itself (`backend/app/db.py`), read-only (never writes).

Output (plain stdout text — no new dependency, no HTML, no charts):

1. **Total disagreement count**, and count of distinct `analysis_id`s represented (how many
   analyses had at least one disagreement) vs. total `Analysis` row count, giving a rough
   disagreement *rate* — the actual BRD Section 7 metric this whole feature exists to serve.
2. **Breakdown by `category`**, sorted by count descending — which stack decisions people
   disagree with most.
3. **Most common `proposed_alternative` per category** (top 3, with counts) — which alternatives
   people are actually reaching for instead of the pick.
4. **Full `reason` text listing**, grouped by category, most recent first — the qualitative
   signal a count can't capture; this is the part someone actually reads, not just skims.
5. **A `--since <ISO date>` flag** to scope the report to disagreements after a given date (e.g.
   "since I started this week's outreach batch") — optional, defaults to all-time.

**Explicitly not in v1**: no segment breakdown (data doesn't exist, per above — don't fabricate
one), no charts/visualization, no web page, no auth, no scheduled/automated run, no write path of
any kind (this never creates/edits/deletes a `Disagreement` row).

## Testing

- `backend/tests/test_disagreements_report.py`: seed a handful of `Disagreement`/`Analysis` rows
  directly via the test DB session (same in-memory SQLite `conftest.py` fixture every other test
  file uses — confirmed no Postgres dependency needed), call the script's report-building
  function (factor the query/aggregation logic into a plain function the script's `__main__`
  calls, so it's testable without shelling out), assert the counts/groupings/top-N-alternatives
  logic is correct against known seed data.
- Mutation-test each assertion (temporarily break the aggregation logic, confirm the test fails,
  restore) — per this session's established discipline.
- No frontend changes, so no `index.html`/Node-harness tests are needed for this spec.

## Explicitly deferred (out of scope for this spec)

- **A real gated HTTP endpoint + admin web page** (option 2 above) — only worth scoping once
  option 1 is proven insufficient at actual beta volume.
- **Segment-attributed breakdowns** — blocked on a real product decision (does the app ever
  capture segment itself, vs. staying a manual out-of-band intake form forever) that's bigger
  than this dashboard and shouldn't be smuggled in here.
- **Automating the disagreement-rate metric into a running dashboard/alert** — this spec produces
  a report you run on demand, not a live-monitoring system; premature at beta scale.
