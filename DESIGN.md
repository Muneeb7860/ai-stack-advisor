# Design decisions — AI Stack Advisor

Filled in per `ui-craft`, before Phase 2 code changes. `check-ui.mjs` reads this file and
suppresses Tier 2 findings declared here.

## Accent

- **Accent:** `#5b8def` (blue) → `#7c5bef` (violet) gradient, dark theme; `#3b6fd6` →
  `#6d4fd1` on light. Already load-bearing across the whole app (buttons, badges, links,
  the hero headline's partial-color treatment) — not changing it now, formalizing it.
- **Why:** technical trust, not alarm. The product's whole pitch this session has been
  "auditable, not a black box — cited, not guessed"; blue reads as calm/precise rather than
  playful or urgent, which fits an architecture-recommendation tool aimed at engineers and
  reviewers, not a consumer product.
- **Neutrals:** cool grey ramp (`--muted`/`--muted2`/`--border`), matches the blue accent's
  temperature rather than a warm grey that would fight it.
- **Status colours:** `--good` (green), `--warn` (amber) are reserved for problem/warning
  states only — the on-prem hosting-constraint errors, exit-cost badges, innovation-token
  overage. Phase 4's confidence-basis badges must NOT reuse these; see Type/basis note below.

## Type

- **Text:** Inter — unchanged, already integrated, well-hinted at UI sizes. Not replacing it;
  replacing a working, legible UI font for its own sake is exactly the kind of unforced
  visual churn this pass should avoid.
- **Display/data:** adding a real second family — `ui-monospace, SFMono-Regular, Menlo,
  Consolas, monospace` (system stack, zero load cost) — for technical/literal tokens:
  technology names in comparison tables, cost figures, confidence-basis codes, ADR excerpts.
  This is a genuine different-job pairing (prose vs. literal-value), not decoration — it's
  the same signal monospace always carries ("this is an exact value, not phrasing"), and it
  fits a tool whose entire premise is citing specific things rather than paraphrasing.
- **Scale ratio:** existing fluid `clamp()` scale (`--fs-xs` through `--fs-xl`) kept as-is —
  already a real, considered scale, not the unexamined default the skill warns about.
- **Measure:** body copy and card `.why` text capped implicitly by card width (~340–420px in
  the grid) — well under the 90ch upper bound, no change needed.

## Geometry

- **Radius base:** `6px` — was `10px` (== `0.625rem` exactly, confirmed the literal shadcn
  default before writing this). Moving off it costs nothing per the skill's own numbers.md,
  and a tighter radius fits a "precision instrument" register better than the softer default.
- **Derived:** `--radius-sm: 4px` (~65%), `--radius-lg: 8px` (~130%) — recomputed from the
  new base, same proportional relationship the current tokens already use.
- **Nesting:** cards inside the results grid already nest chip/badge elements at a smaller
  radius than their parent card — this rule already holds, just re-verify after the base
  value changes.
- **Elevation:** two levels, not more. **Resting** — border only, no shadow (stack cards,
  chips, badges — the vast majority of the UI). **Raised** — border + soft shadow + glass
  blur, reserved for genuinely overlaid/floating surfaces (the glide panel, the results hero,
  the mode-picker preview card). Two levels because the UI has exactly two real states of
  "how urgently should your eye land here" — everything else is the same weight on purpose.

## Motion

- **Durations:** `150ms` for micro-interactions (hover, chip toggle — matches the existing
  `.15s` already used throughout), `250ms` for panel-scale motion (glide panel slide-in).
- **Easing:** `cubic-bezier(.2,.7,.3,1)` — already defined as `--ease` and used consistently.
  Naming it here formally: **"advisor-ease"** — a fast-start, gentle-settle curve (steep
  initial acceleration, soft landing, no overshoot) chosen to feel decisive rather than bouncy,
  matching a tool that's supposed to read as confident, not playful.
- **Reduced motion:** `prefers-reduced-motion: reduce` should collapse the glide-panel slide
  and wizard step fade to opacity-only crossfades — not yet implemented, flagging as a real
  gap to fix in Phase 2 (falls under the checker's general accessibility intent even though
  it's not one of the 7 rule ids that fired).

## The signature

**Dot-grid body texture** — `radial-gradient(circle at 1px 1px, rgba(var(--dot-rgb),
var(--dot-alpha)) 1px, transparent 0) 0 0/24px 24px` layered under `--bg`, theme-aware
(`--dot-rgb`/`--dot-alpha` swap for light/dark). Already shipped (added earlier this project),
not new — declaring it formally as the signature token per the skill's own definition: a
grain/texture the default system does not ship, that no component-library default would
produce. Reads as blueprint/schematic paper, which fits a tool that produces architecture
diagrams and decision records.

## Deliberate deviations

- `glassmorphism` — intentional, not a default-tool artifact. Restrained to the two Elevation
  "raised" surfaces above, not blanket-applied to every panel (the skill's own concern is
  backdrop-blur "on translucent panels" used as an unexamined default everywhere; here it's
  selective and was a specific, discussed product request — iOS-style frosted glass — earlier
  in this project, not an accepted default).
- `page-skeleton` (hero → feature → pricing → faq → cta detected) — reviewed, and this reads
  as a likely checker false-positive on this specific page rather than a real generic-funnel
  structure: the page has no pricing section, no testimonials, no FAQ, and no separate bottom
  CTA — it's a single-screen tool (hero → mode-picker → wizard/results), not a marketing site
  with those sections. Flagging this back per the brief's own instruction (§"Report back" —
  checker misses not on the Known-false-positives list should come back as a skill bug) rather
  than silently suppressing it as if it were a real, examined trade-off.

## Out of scope

- No user accounts or login in v1 — the tool works anonymously, no-signup, by design; a share
  link is the only persistence/access-control primitive, matching the tool's low-stakes,
  advisory (not provisioning) nature.
- No native mobile app — responsive web only, one codebase.
- No localization/i18n — English only, not on the roadmap.
- Dark theme is the default and the primary design target; light theme is a supported opt-in,
  not a from-scratch parallel design — new components are designed dark-first, then checked
  against the light token overrides.
