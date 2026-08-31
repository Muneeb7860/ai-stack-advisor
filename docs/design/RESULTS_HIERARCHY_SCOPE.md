# Results hierarchy — restructure scope

Status: **scoped, not implemented.** Follows the UI audit (31 Aug 2026), which rated the
interface 5.5/10 and traced every structural weakness to this one problem.

## The problem, stated precisely

Two facts from the code, not impressions:

1. **`index.html:4777` renders every section with a hardcoded `open`:**
   ```js
   `<details class="section-block" id="${x.id}" open>...`
   ```
   All 19 sections are expanded on every analysis. The disclosure mechanism exists and works —
   it's simply never used as disclosure.

2. **The lead space answers the wrong question.** `.results-hero` (the first thing rendered,
   `index.html:4537`) contains: a signal count ("12 signals detected"), the detected-signal
   chips, exclusions, token budget, and up to four banners. That is a restatement of *the user's
   own input*. The user knows what they typed. What they came for — the recommendation — starts
   below all of it, in section 1 of 19.

So the current shape is: *echo the input, then present everything at once, ranked by nothing.*

## Why this matters more than polish

From the audit's research:

- **The closest analogue has a documented failure mode.** AWS Well-Architected — structurally
  near-identical to this product — is most often criticised for exactly this outcome: *"teams
  open the console, click through a few questions, see a list of risk items, and close the tab,
  leaving the improvement plan unused."* The recommended fix is a design instruction: treat the
  output as a **triage exercise, not a to-do list**.
- **The real competitor is not another tool.** There is no established product category here; the
  alternative is reading a guide or asking an LLM directly, which returns skimmable prose in
  seconds with no interface to learn. Our advantages — determinism, citations, structure — only
  win if the structure reads as an asset rather than a wall. Nineteen expanded sections lose that
  comparison.

No amount of colour or spacing work fixes this, which is why the recent minimalist pass (PR #56),
while real, was shallow.

## The design: three tiers

Borrowed from Lighthouse, which this product already imitates correctly *in its own harness audit*
(score → band → ranked fix list) but not in its main report.

### Tier 1 — The answer

`.results-hero` stops describing the input and starts stating the recommendation: the spine of the
stack (cloud, primary database, compute model, LLM strategy) as a single scannable line-up, with
overall confidence. This is what the user came for and it should be legible in about three
seconds.

The signal chips, exclusions and token budget move **below** Tier 2, or behind a disclosure. They
are evidence for the answer, not the answer — and they're already duplicated per-card by the
existing "why this pick" inspection (FR-30).

### Tier 2 — What needs your attention

A short ranked list, capped (3–5 items), directly modelled on Lighthouse's *Opportunities*.

**The ranking signal already exists in the engine — no rule-engine work required.** Two fields are
already computed on every pick:

- `EXIT_COST_CATEGORIES` (`index.html:6727`) — the six categories genuinely expensive to reverse:
  cloud, iam, database, gateway, messaging, observability.
- `conf` — `high` / `medium` / `low`, present on every pick (195 occurrences).

Crossing them produces something more useful than either alone:

| Exit cost | Confidence | Meaning | Rank |
|---|---|---|---|
| High | Low | *Committing to something expensive to reverse, on weak signal* | **1 — surface first** |
| High | Medium | Expensive to reverse, moderate evidence | 2 |
| Low | Low | Weak signal, but cheap to change later | 3 |
| Any | High | Well-supported | not listed |

The top row is the single most valuable thing this product could tell someone, and **nothing
surfaces it today**. It's a derived insight, not a new computation.

### Tier 3 — Everything else

The remaining sections stay exactly as they are, but **collapsed by default**. One line changed at
`index.html:4777`: `open` becomes conditional.

Which sections default to open is a product decision, not a mechanical one. Proposed: the stack
grid (the answer's detail) and anything referenced by a Tier 2 item; everything else closed.

## Decisions worth stating

- **Collapsing alone is not the fix.** Nineteen *closed* accordions is a different wall — it
  converts a scrolling problem into a clicking problem, and buries the answer entirely. Tier 1 and
  Tier 2 are what make Tier 3's collapse safe. Doing only the easy line-change would make the
  product worse.
- **Nothing is removed.** Every section, pick and citation survives. This is a hierarchy change,
  not a scope cut — a user who wants all 19 sections is one interaction away, and export/share
  still carry everything.
- **Reuse the harness audit's shape rather than inventing one.** It already does score → band →
  ranked fixes, it's already tested, and users moving between the two modes should meet one idea
  of "how this product presents findings," not two.
- **No new rule-engine output.** Tier 2 derives entirely from existing `conf` and
  `EXIT_COST_CATEGORIES`. That keeps this a presentation-layer change and keeps the dual-engine
  parity surface untouched.

## Risks and constraints

- **`#sideNav` is generated from the section list** (`index.html:4772`). If sections collapse, the
  in-page nav must still jump correctly *and* open the target — otherwise clicking a nav item
  appears to do nothing. This is the most likely bug in the whole change and needs an explicit
  test.
- **`details.section-block` styling is test-locked** by
  `test_phase2_visual_reskin.py:75`. The template's structure must survive; only the `open`
  attribute becomes conditional.
- **`ALL_SECTION_IDS` membership is asserted** by `test_agent_framework_category.py` and
  `test_llm_observability_category.py`. Sections must remain registered — collapsing is not
  removal, so these should pass unmodified. Verify, don't assume.
- **Export/share must be unaffected.** They serialise the full recommendation object, not the DOM,
  so they should be untouched — but a shared read-only view rendering with everything collapsed
  would be a regression worth checking.
- **Flow View is a sibling of this, not part of it.** Untouched by this scope.

## What this scope deliberately excludes

- Keyboard navigation / command palette (audit item 2) — separate, self-contained.
- Empty and first-run states (audit item 3) — separate.
- The density pass: borders, nesting, whitespace (audit item 4) — deliberately **after** this, so
  spacing isn't tuned against a layout that's about to change.
- Any change to what the rule engine recommends. Presentation only.

## Testing plan

- **Tier 2 ranking is pure logic** — the exit-cost × confidence ordering is a testable function
  with no DOM: high-exit/low-conf ranks first, high-confidence never appears, cap respected,
  empty list when everything is high-confidence (and the block hides rather than rendering empty,
  matching the fix-order card's existing behaviour).
- **The nav-jump-opens-a-collapsed-section case** gets a dedicated test — the most likely bug.
- Assert Tier 1 no longer leads with the signal count, and that signals are still reachable.
- Confirm all existing section/visual locks pass unmodified; mutation-test each new assertion, per
  this repo's established discipline.
- Live-browser verification of the full flow at desktop and mobile widths, plus a shared
  read-only view.
