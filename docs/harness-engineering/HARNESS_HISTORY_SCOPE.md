# Harness Readiness — score history

Status: **scoped and implemented** (2026-08-31). Third and smallest piece of the harness-
engineering direction, after `HARNESS_READINESS_SCOPE.md` (the audit itself) and
`HARNESS_EVIDENCE_SCOPE.md` (optional evidence upload).

## The problem this solves

Harness Readiness is currently **amnesiac**. A completed audit exists only until the user
navigates away — `analysis_history` and `stack_challenges` both persist to localStorage, but a
harness score persists nowhere.

That's a real gap, not a missing nice-to-have, because the rubric this feature is built on is
explicitly a *repeat* practice: every band message tells the user what to fix next ("find the
lowest-scoring component and take it to a 2 before touching anything else"), which only means
something if they can come back and see whether it worked. A one-shot score is a curiosity; a
score you can retake and compare is the thing the source material is actually asking for.

This is also the cheapest way to learn whether anyone uses this mode at all — the open question
blocking the larger harness-engineering decisions (promote harder? build the repo-crawling CLI?).

## What it does

On finishing an audit, save the result to localStorage. On the results screen, when at least one
prior audit exists, show a **"Previous audits"** block: each past score with its date and band,
and — for the current result — the delta against the immediately-previous audit, both overall
and per component.

The per-component delta is the load-bearing part. "9/15, up from 6" is encouraging but not
actionable; "Verification 1 → 3, Guardrails still 0" tells the user their last round of work
landed and what's still outstanding.

## Storage

Follows the established `getAnalysisHistory()`/`saveAnalysisHistoryEntry()` pattern exactly
(`index.html`, near the other localStorage helpers): one flat top-level key holding a JSON array,
a reader wrapped in `try/catch` returning `[]` on any failure, a writer that read-modify-writes.
Key: `harness_history`. Entry shape:

```js
{ id, ts, total, band, answers: {system_of_record, tools, verification, guardrails, observability} }
```

Storing the raw `answers` (five integers), not just the total, is what makes per-component deltas
possible without re-running the audit.

### Two deliberate divergences from `analysis_history`

1. **No de-duplication.** `saveAnalysisHistoryEntry` de-dupes by identical text, so re-analyzing
   the same requirement moves the existing entry to the top rather than duplicating it. That's
   right there — the same text is the same analysis. It is *wrong* here: two identical 8/15
   scores three months apart are two genuinely different data points, and collapsing them would
   destroy exactly the signal this feature exists to show ("we've been stuck at 8 all quarter").
2. **A smaller cap** (`HARNESS_HISTORY_MAX = 10`, vs. 20 for analyses). Audits are meant to be
   spaced weeks or months apart, not run repeatedly in a session; ten is several years of a
   quarterly cadence and keeps the rendered list readable without paging.

## What this deliberately does not do

- **No sidebar entry.** The sidebar's history list is analysis-specific — clicking a row calls
  `openHistoryEntry` → `setAnalysis`, which reconstructs a *product analysis*. A harness score has
  no equivalent replay (there's nothing to re-derive; the score is the artifact), so wiring it in
  would mean either a fake replay or a second, differently-behaving list in the same UI. History
  renders on the harness results screen, where the comparison is actually meaningful.
- **No backend persistence.** Same client-side-only invariant (NFR-1) as every other v1 feature
  and both prior harness pieces. Nothing is transmitted.
- **No cross-device sync, no export.** Both are real asks if this gets traction; neither is worth
  building before there's evidence anyone retakes the audit at all.
- **No change to scoring, the questionnaire, or evidence upload.** This is purely additive around
  a completed result.

## Testing plan

Mirrors `test_analysis_history.py`'s approach (a **real in-memory localStorage stub**, not the
no-op one most Node-harness tests use, so round-trip read/write can actually be asserted):

- Round-trip: save an entry, read it back, same total and answers.
- The no-de-dup divergence: saving two identical scores leaves **two** entries (this is the one
  most likely to be "fixed" into a bug later by someone pattern-matching on `analysis_history`).
- Cap: saving 11 entries leaves 10, oldest dropped.
- Delta math: per-component improvement, regression, and unchanged all reported correctly.
- First-ever audit renders no history block and no delta (nothing to compare against).
- Corrupt/absent localStorage returns `[]` rather than throwing.
- Mutation-test every new assertion, per this session's established discipline.
