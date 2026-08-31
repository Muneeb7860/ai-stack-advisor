# Harness Readiness — feature scope

Status: **implemented** (2026-08-31). One deliberate deviation from the scope as originally
written: results render into two dedicated screens (`#screenHarnessAudit` input,
`#screenHarnessResults` output) rather than the existing `#resultsShell`/`#results` container.
Reusing that container risked entangling this feature with machinery that assumes the
product-analysis shape everywhere (refine/ask/challenge buttons, sidebar history restore, share
links, export) — none of which conceptually applies to a harness score, and several of which
would have needed defensive guards added just to avoid breaking on this feature's different
data shape. A dedicated pair of screens keeps this feature's blast radius to itself, consistent
with the rest of this scope's own reasoning for why the feature is different everywhere else.

## What it is

A fourth entry mode alongside "Answer a few questions" / "Paste your own description" / "Upload
architecture diagram": **"Audit your harness"** — scores a team's *own agentic-development
practices* against the 5-component rubric from the Harness Engineering Build Guide, and outputs
a scorecard + fix-order, the same shape as `HARNESS_AUDIT.md`'s own "ranked by leverage" list.

This is Shape A from `CONCEPT_SKELETON.md`, made concrete.

## Why a new mode, not a section bolted onto existing analysis

The existing three modes all answer the same question — *what should this product's stack be* —
from a product/business requirement. Harness Readiness answers a structurally different
question — *how mature is this team's agent-development process* — and the inputs don't
overlap (nobody writing "we're a fintech startup with real-time fraud detection" is also
describing whether their CI runs a linter on every commit). Folding it into the existing
free-text flow would mean detecting an entirely new signal category from text that was never
written to contain it — much less reliable than the pattern below.

## Why a guided questionnaire, not free-text signal detection

Every other category in this product infers signals from natural-language requirement text
(`detect_signals` → `has([...])` keyword matching). That works because a requirement
description reliably *contains* the relevant facts ("real-time," "on-premises," "agentic").
A harness self-audit doesn't have that property — "do you have a Stop hook that blocks on a
failing test" is a yes/no fact about internal process a team won't spontaneously narrate in
prose, and false-negatives here (silently scoring 0 because the user didn't happen to mention
hooks) would be actively misleading, not just less-precise. Appendix B's own rubric is a
0/1/2/3 four-point scale per component with concrete, mutually-exclusive descriptions at each
level — that's a multiple-choice UI, not a text-mining problem. **Recommendation: 5 questions,
one per component, each a 4-option radio matching the Appendix B rows verbatim** (already
transcribed as `HARNESS_COMPONENTS` levels in `CONCEPT_SKELETON.md`'s skeleton data model, and
already built as a clickable mockup in the published scorecard artifact). This mirrors the
existing wizard's own UX (`startWizard()`, `.wiz-step`, chip/radio selection) rather than
inventing a new interaction pattern.

## Screens and flow

1. New `mode-card` on `#screenMode`: icon + "Audit your harness" + one-line description
   ("Score your team's own agent-development setup — five questions, two minutes").
2. New `#screenHarnessAudit` screen, structurally identical to `#screenWizard`'s step
   pattern (`.wiz-step`, progress bar, Continue button) but with exactly 5 steps, one per
   component, each rendering 4 radio options (the Appendix B level text) instead of the
   existing wizard's chip-grid.
3. On completion, render results into the **same `#resultsShell`/`#results` container** the
   other three modes already use, via a dedicated render function — not `renderRecommendations`
   (wrong shape entirely: no vendor picks, no stack cards), but a parallel function producing:
   - Total score `/15` + band (four bands, Appendix B's own labels: harness consumer / real
     harness exists / production grade / mature).
   - One card per component, styled like the existing stack cards, showing the score, the
     matching level description, and (see below) a fix suggestion when scored 0 or 1.
   - A "fix order" list — components sorted lowest-score-first, capped at 3, mirroring
     `HARNESS_AUDIT.md`'s own structure exactly (this document already proved the format works
     for a real reader).
4. `backToMode()` and the sidebar's existing "New Analysis"/"This Analysis"/history mechanisms
   all extend to this mode for free — they're generic screen-swap functions, not
   product-analysis-specific.

## Scoring logic

No `detect_signals`/`recommend_stack` involvement at all — this is a separate, much smaller
pure function:

```python
# NOT real code — shape only.

def score_harness(answers: dict[str, int]) -> dict:
    """answers: {"system_of_record": 0-3, "tools": 0-3, "verification": 0-3,
    "guardrails": 0-3, "observability": 0-3} — one radio-selection per component, no inference."""
    total = sum(answers.values())
    band = next(b for b in SCORE_BANDS if total <= b["max"])
    fix_order = sorted(HARNESS_COMPONENTS, key=lambda c: answers[c["id"]])[:3]
    return {"total": total, "band": band, "per_component": answers, "fix_order": fix_order}
```

Deterministic, no LLM call, no keyword matching — matches this product's existing zero-cost,
fully-client-side invariant (BR-5 / NFR-1 from the BRD/PRD) exactly. This can genuinely ship
as pure JS in `index.html` with no backend involvement, same as the rest of v1.

## Fix suggestions — grounded only in what the market research actually verified

This is the part most likely to go wrong if built carelessly, so it's worth being explicit
about scope discipline up front, given what `CONCEPT_SKELETON.md` already found:

- **Verification (score 0-1):** recommend wiring a lifecycle hook to a `verify` command,
  naming Ruff/pytest, ESLint/Vitest, or Playwright by category — all three are named in the
  PDF's own reading list, still current, and are exactly the kind of thing this product's OWN
  test suite already exemplifies (dual-engine parity + mutation testing). This is the wedge the
  market research says is open — lead here, not on guardrails.
- **System of record / Tools (score 0-1):** recommend `AGENTS.md`, cite it as a Linux Foundation
  Agentic AI Foundation project (verified fact, not opinion) — same for MCP under Tools.
- **Guardrails (score 0-1):** describe the *mechanism* (allow/ask/deny rules, a deny list on
  credential paths) without recommending a *vendor* — the market survey found this exact
  vendor market (Lakera, Protect AI, Guardrails AI) got bought out or archived in 2026. Naming
  one of those companies as "the" guardrails product would be recommending something that may
  no longer exist as an independent product by the time someone reads it. This is a real,
  research-backed reason to deliberately NOT build a `GUARDRAILS_VENDORS`-style catalog here,
  unlike every other category this session added.
- **Observability (score 0-1):** recommend a failure log + progress file pattern (the PDF's own
  `failures.md` template) rather than an OTel-GenAI-conventions integration — the market survey
  found that spec is still "Development status," too early to build toward.

## What this explicitly does not do

- No new vendor catalog/comparison table for any of the 5 components (see Guardrails above —
  extends to all of them: this feature teaches a practice, it doesn't sell a tool).
- No repo-inspection/automated scoring (Shape B's other open question) — this scope is the
  guided-questionnaire version only. Automated grep-based scoring is a separate, larger effort
  (needs file-system access this client-side product doesn't have) and isn't part of this scope.
- No attempt to detect harness-maturity signals from the existing three modes' free text.
- No backend/API involvement — pure client-side, matching the rest of v1.

## Attribution

The Appendix B rubric and 5-component framing are Aishwarya Srinivasan / The Gen Academy's
(`HarnessEngineeringBuildGuide.pdf`, companion to a YouTube video). `CONCEPT_SKELETON.md`
flagged this as an open licensing question — resolving it (crediting the source in-product,
e.g. a footer note on the audit results page, similar to how vendor pricing sources are cited
elsewhere in this app) is part of this scope, not a follow-up.

## Testing plan (once approved)

Mirrors this session's established discipline, adapted to what's actually being tested — pure
scoring math and UI wiring, not text-signal detection, so no differential/parity harness is
needed (nothing here has a Python-side equivalent; this is v1-only, same as the wizard):

- Score-math tests: band boundaries (4/5/9/10/13/14 edges), fix-order sort correctness and its
  cap-at-3 behavior, all-zeros and all-threes edge cases.
- A live-browser click-through of all 5 steps, at least once per band (to see all four band
  labels render), plus the mobile-responsive check this session applies to every new screen.
- Mutation-testing the scoring function itself (flip a comparison operator, confirm the band
  test catches it) — same discipline as every rule-engine change this session.

## Attribution — resolved

A visible citation renders on the results screen ("Rubric and component descriptions: *Harness
Engineering Build Guide*, Appendix B (Aishwarya Srinivasan / The Gen Academy) — used as a
self-audit tool here, not reproduced as the source's own product."). This is a minimum, not a
final legal answer — worth a real look if this feature gets meaningfully more visible.
