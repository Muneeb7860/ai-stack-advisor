# Harness Readiness — evidence upload (Shape A/B hybrid)

Status: **shipped** in [PR #50](https://github.com/Muneeb7860/ai-stack-advisor/pull/50), with
report-under-claim handling and upload-path guards added in
[PR #66](https://github.com/Muneeb7860/ai-stack-advisor/pull/66); guarded by
`backend/tests/test_harness_evidence_upload.py` and
`backend/tests/test_harness_evidence_underclaim.py`. Follow-on to `HARNESS_READINESS_SCOPE.md`
(implemented, merged in [PR #49](https://github.com/Muneeb7860/ai-stack-advisor/pull/49)),
addressing the
one weakness pure self-report has: nothing stops a team from picking 3 on every question
regardless of what's actually true. This does not replace the guided questionnaire — it adds
one optional action per question.

## Why this is a hybrid, not "build Shape B instead"

Shape A (guided self-report, already shipped) is low-friction and always works — no files
required, two minutes, works for a team that hasn't touched their own repo in this browser
tab. Shape B (automated repo-scoring) is more credible but structurally can't live inside
this product as originally imagined: a browser tab cannot crawl a filesystem or git history
on its own, and this app's foundational invariant (NFR-1/NFR-5 — fully client-side, zero
network calls, works from `file://`) rules out a backend crawler. That's why
`HARNESS_READINESS_SCOPE.md` explicitly scoped automated repo-inspection out.

The hybrid doesn't relax that invariant. It uses the one filesystem interaction a browser
*does* have without a backend: the user explicitly picks a file, and `FileReader.readAsText()`
reads it client-side — the exact mechanism the diagram-upload mode already uses
(`handleDiagramFile` / `parseDiagramInput`, `index.html:8324-8341`). No crawling, no directory
listing, no access without an explicit per-file user action. What's added is one **optional**
"attach evidence" affordance per question, not a new mode.

## What it does

For each of the 5 questions in the existing harness-audit flow, add a small, dismissible
"Have a file that proves this?" control next to the radio options. If the user attaches a
file, run a client-side heuristic check against its text and compare the result to whatever
level they picked:

- **Match** — a small confirming badge next to their selection ("Evidence checks out").
- **Exceeds** — the file supports a *higher* level than the one picked. Reported, not corrected:
  it states what the file shows and leaves the score alone.
- **Mismatch** — a non-blocking warning ("You picked 3, but this file doesn't show a
  passing-test gate — reconsider?") with the reason. The user's own selection still wins;
  this never silently overrides their answer or blocks Continue.
- **Inconclusive** (file doesn't match any known pattern for this component) — no badge,
  no warning. Silence beats a false signal here.

> **Why "exceeds" is a separate verdict.** The first implementation treated `level <= ceiling` as
> a match, so claiming *less* than your file shows rendered "✓ Evidence checks out" — confirming a
> score the attached file actively contradicts. That isn't only imprecise wording. This audit's
> entire output is "find your lowest-scoring component and take it to a 2 before touching anything
> else", so a component scored 0 whose evidence shows 3 becomes the *recommended place to start* —
> the one thing the user demonstrably already has, while the tool holds the file proving it. Found
> by running a real audit with this repo's own files; every checker test until then had used
> `level == ceiling` or `level > ceiling`, so the under-claim path had no coverage at all.

Nothing is required. A user who skips every upload gets exactly today's flow, unchanged.

## Per-component check, and exactly what evidence it accepts

Grounded only in what's checkable from a single file's *text content* — no multi-file
correlation, no directory structure inference (that's a real Shape-B capability this
hybrid deliberately doesn't attempt):

| Component | Accepts | Heuristic (client-side regex/string check) |
|---|---|---|
| System of record | `AGENTS.md`, `CLAUDE.md`, any `.md` | Exists, is non-trivial length (not a stub), and — for the top score only — contains at least one line that reads like a "Do Not" / lesson-learned entry (a bullet whose text includes a past-tense verb near "don't"/"never"/"broke"), matching the existing `levels[3]` copy ("Lines trace to real failures"). |
| Tools | MCP config (`mcp.json`, `.mcp.json`, `claude_desktop_config.json`), or a `.claude/settings*.json` | Parses as JSON, has at least one entry under a recognizable tools/servers key. Cannot verify "you can justify each one" — caps the auto-confirmable level at 2, same ceiling `HARNESS_AUDIT.md` used by hand for an unreviewed-but-present set. |
| Verification | CI config (`.github/workflows/*.yml`, `.gitlab-ci.yml`), or a lifecycle-hook config (`.claude/settings*.json`'s `hooks` key) | String-matches step/command text against the same tool names already in this component's own `fix` copy (Ruff, pytest, ESLint, Vitest, Playwright) or a generic `test`/`lint` script invocation. A hook config additionally checked for a `Stop`/`PostToolUse` entry running a command — the strongest single signal, matching `levels[3]`'s "cannot finish on a failing check." |
| Guardrails | `.claude/settings*.json` | Counts `allow`/`ask`/`deny` array entries — mirrors exactly how `HARNESS_AUDIT.md` itself was scored by hand (298 allow / 0 ask / 0 deny, no hooks → 0/3). A deny rule matching a credential-path pattern (`.env`, `secrets/**`, `*.pem`) is the only thing that can confirm `levels[2]`+; deny rules alone with zero ask entries caps at 1, matching this component's own "chosen by convenience" `levels[1]` language. |
| Observability | `failures.md`, or any file whose name matches `CHANGELOG|failures|postmortem` | Exists, and — for the top score — has more than one dated entry (a naive count of lines matching a date-like pattern `\d{4}-\d{2}-\d{2}` or `## ` headings), matching `levels[3]`'s "a failure log drives your backlog." |

Every check is a **ceiling test, not a pass/fail grade**: it can confirm a selection is
plausible or flag that it isn't, but it never claims to verify the deeper qualitative claims
in `levels[3]` (e.g. "acted on," "removed on a schedule") — those stay something only the
person answering can actually know. This is a deliberate, stated limitation, not an oversight.

## What this explicitly does not do

- No directory listing, no `git log` inspection, no multi-file correlation (e.g. cross-checking
  that a CI step referenced in the workflow file actually exists as a script) — single-file
  text content only, exactly what `FileReader.readAsText()` on one user-picked file can see.
- No auto-filling or auto-selecting a radio option from the file — the user always picks;
  evidence only confirms or flags, never chooses for them.
- No upload is ever required — Continue stays enabled purely off the existing radio selection,
  unchanged from today's behavior.
- No file content is transmitted anywhere — parsed and discarded in-memory client-side, same
  no-network invariant as the diagram-upload mode.
- Still not the full Shape B (repo-wide automated crawl, test-coverage percentage, commit-history
  analysis) — that remains a separate, larger, likely-CLI-based effort, not attempted here.

## Screens and flow

Extends `haRenderStep()` (`index.html:6118`+), not a new screen:

1. Below each question's `.radio-list`, a collapsed `<button class="ha-evidence-toggle">` reading
   "Have a file that proves this? (optional)". Clicking reveals a file `<input type="file">`
   (reusing the diagram-upload input's styling, new element id per component: `haEvidence-${c.id}`).
2. On file select, `FileReader.readAsText()` → run that component's specific check function →
   render one of three states (match / mismatch / silent) into a new `<div class="ha-evidence-result">`
   directly under the toggle. No screen change, no re-render of the radio options themselves.
3. Nothing here changes `scoreHarnessAudit()` or the results screen — evidence only annotates the
   input step, it never feeds the score. (Whether a *confirmed* answer should count differently
   from an *unconfirmed* one is a real open question, deliberately deferred — see below.)

## New functions (all pure, all client-side, no backend)

- `checkEvidence(componentId, filename, fileText)` → `{ verdict: 'match'|'mismatch'|'silent', reason }`
  — a small dispatch table keyed by `componentId`, one checker function per component matching
  the table above.
- `haOnEvidenceFile(componentId, file)` — wires `FileReader`, calls `checkEvidence`, renders the result.
- Five checker functions (`checkSystemOfRecordEvidence`, `checkToolsEvidence`,
  `checkVerificationEvidence`, `checkGuardrailsEvidence`, `checkObservabilityEvidence`), each a pure
  `(selectedLevel, fileText, filename) => {verdict, reason}` function — testable via the same Node-harness
  pattern already used for `scoreHarnessAudit`, no DOM needed for the logic itself.

## Explicitly open questions (not resolved by this scope)

- **Should a confirmed answer visually outrank an unconfirmed one in the results screen** (e.g. a
  small checkmark next to a component score that had matching evidence)? Leaning yes — it's a
  natural, low-cost extension of "evidence checks out" — but not committing to it here; decide
  during implementation once the confirm/mismatch UI itself is live and can be judged by feel.
- **Should a mismatch be allowed to auto-suggest a lower level** (not force it, just pre-highlight)?
  Leaning no — the whole point of keeping this optional and non-blocking is that the user's own
  judgment stays authoritative; a suggested correction risks reading as the tool overriding them.

## Testing plan

Mirrors `HARNESS_READINESS_SCOPE.md`'s own testing discipline:

- Pure-function tests for all 5 checker functions via the Node harness (`test_harness_readiness_feature.py`'s
  existing `_js()` pattern) — one match case, one mismatch case, one silent/inconclusive case per
  checker, using small inline fixture strings (a realistic CI YAML snippet, a realistic
  `settings.local.json` snippet, etc.), not real files.
- DOM-wiring tests: the evidence toggle exists per component, the file input exists with the
  right id, no `fetch(`/`API_BASE` appears anywhere in the new code (same invariant check the
  existing `test_no_backend_or_llm_call_anywhere_in_the_harness_audit_code` already runs, extended
  to cover this addition).
- Mutation-test each new checker's regex/threshold (flip a boundary, confirm the matching test
  fails), per this session's unbroken discipline.
- Live-browser verification: attach a real small CI YAML fixture to the Verification question,
  confirm the match/mismatch badge renders correctly for both a passing and a non-matching file;
  confirm skipping every upload leaves the flow byte-identical to today's behavior.
