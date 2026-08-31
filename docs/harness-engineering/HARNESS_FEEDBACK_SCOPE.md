# Harness Readiness — feedback capture

Status: **scoped and implemented** (2026-08-31). Fourth piece of the harness-engineering
direction, after the audit, evidence upload, and score history.

## Why this, and why before promoting the mode

The product goal for the next six months is stated plainly: the tool is free, people try it,
solve a real problem, and tell us what they think. Harness Readiness currently supports the first
two and is structurally incapable of the third.

Checked against the code, not assumed:

- `attachRefineUI()` only targets `#stack .stack-card` and `#tradeoffs .tradeoff-card`. The
  harness results screen has **no feedback affordance of any kind**.
- Harness audits never call `ensureAnalysisId()`, so the existing "Challenge This Pick"
  disagreement endpoint could not fire from that screen even if it were wired up.
- Everything harness-related (audit answers, evidence, score history) is localStorage-only.
  Nothing has ever left a user's browser.

So the mode could be promoted perfectly and still return **zero** signal. Every trial would help
the user and teach us nothing. That makes feedback capture, not discoverability, the first thing
to build — discovery is worth doing next, but it is pointless first.

## Why a new table rather than reusing `Disagreement`

`Disagreement.analysis_id` is a `NOT NULL` foreign key to `analyses`. A harness audit has no
Analysis row, and should not create one: an `Analysis` is a *product requirement* (input text +
detected signals), which a harness self-audit is definitionally not. Forcing one into existence
purely to hang feedback off it would corrupt the meaning of that table and every metric derived
from it.

Precedent for a record that stands alone: `McpInvocation.analysis_id` is deliberately nullable
for the same class of reason (DDD 4.4 — the record exists before/without an Analysis).

`HarnessFeedback` is therefore standalone, with no FK. Append-only, same rationale as
`Disagreement` and `RefinementResult`: feedback is a fact about a moment; editing it later would
corrupt the record rather than update it. No update/delete route exists or should.

## What is captured

The comment alone is nearly useless without the score that produced it — "this wasn't useful"
from a team scoring 14/15 means something completely different than from a team scoring 2/15. So
each submission carries the audit result as context:

| Field | Why |
|---|---|
| `total`, `band` | The headline result the user is reacting to |
| `answers` (JSON) | Per-component scores — lets us see *which* profile of team found it useful |
| `helpful` (bool) | A one-click signal, deliberately separate from the comment: response rate on a binary is far higher than on free text, so this is the number that will actually have an n |
| `comment` (optional text) | The high-value, low-response-rate half |

`helpful` is submittable **without** a comment on purpose. Requiring prose is what collapses
response rates; a one-click answer from many users plus prose from a few is a better dataset than
prose from almost nobody.

## Privacy and the client-side invariant

This is the first thing in the harness feature area that leaves the user's machine, so it follows
the same posture the existing refine/ask/share features already established for exactly this:

- **Explicit user action only.** Nothing is transmitted until the user presses Submit. There is
  no automatic/background telemetry, and none should be added here later.
- **Disclosed in the UI**, in plain language, next to the button — the user is told what is sent
  (their score and comment) before they send it.
- **Best-effort, never blocking.** Same fire-and-forget posture as `onChallengeSubmit`'s optional
  POST: if the backend is unreachable, the UI thanks the user and moves on rather than surfacing
  an error about infrastructure they don't care about. The audit itself never depends on it.
- No identifiers are collected — no email, no user id, no requirement text. The audit answers are
  process facts about a team's tooling, not the product idea they came to the tool with.

## What this deliberately does not do

- **No promotion/discoverability changes.** Separate concern, separate PR, and it should follow
  this rather than precede it.
- **No admin/reporting UI.** Reading the collected feedback is a `psql` query for now; building a
  dashboard before there is any data to look at is premature.
- **No rating scale beyond the binary.** A 1–5 star adds interpretation burden at both ends for
  little gain at this sample size.
- **No change to the audit, scoring, evidence upload, or history.**

## Testing plan

- Backend: `TestClient(app)` against the in-memory SQLite fixture in `conftest.py` (no Postgres
  needed) — 201 and correct shape on a valid submission, comment genuinely optional, append-only
  (a second submission does not overwrite the first), and validation rejecting an out-of-range
  score.
- Frontend: the submit path is best-effort and must never throw or block when the backend is
  absent — asserted with `fetch` stubbed to reject, which is the realistic case for anyone
  running the file locally.
- Disclosure text must be present next to the button (a regression lock: silently removing the
  "what gets sent" line would turn an explicit exchange into undisclosed telemetry).
- Mutation-test every new assertion, per this session's established discipline.
