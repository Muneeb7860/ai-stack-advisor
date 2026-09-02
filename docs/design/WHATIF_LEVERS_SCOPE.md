# What-if levers — scope

**Status:** Phases 1-2 SHIPPED. Phase 1 (PR #77): four levers with named stops, the shared
boolean-override mechanism, and the changed-recommendation summary. Phase 2 (PR #81): a stated
concurrency figure's magnitude now changes the recommendation past a second, higher threshold
(1,000,000) — not just the boolean it already tripped. Landed as a new tradeoff-section entry
rather than a lever, since it is a fact the requirement states, not a knob to explore — the
levers remain the four from Phase 1. Phase 3 (a budget lever) remains, still blocked on the
product decision described below.

Written after investigating the engine rather than from the proposal that prompted it.

## The proposal, and what the engine can actually support

The request was four sliders above the results:

```
[ Team Size:  1 Solo Dev  <────●────>  50+ Enterprise Squads ]
[ Scale:      1,000 DAU   <────●────>  10,000,000 DAU        ]
[ Compliance: Standard    <────●────>  Strict HIPAA / PCI     ]
[ Budget:     $50         <────●────>  $50,000+/mo           ]
```

Moving one re-runs the engine and highlights what changed.

**146 of the engine's 152 signals are boolean.** The non-boolean ones are `excluded` (dict),
`known` (dict), `excludedLanguageTerms` (list), and three parsed numerics — `latencyTarget`,
`concurrencyTarget`, `timeline`.

So three of the four proposed sliders resolve to two or three discrete states, and the fourth
resolves to nothing at all:

| Proposed slider | What it actually drives | Real states |
| --- | --- | --- |
| Team size | `smallTeam`, `largeTeam` | 3 (small / unstated / large) |
| Scale | `highScale` (+ `concurrencyTarget`, see below) | 2 |
| Compliance | `compliance`, `hipaaMentioned`, `pciMentioned`, `soc2Mentioned`, `gdprMentioned` | discrete flags, not a scale |
| Budget | **no signal exists** | 0 |

A slider rendered over a boolean is a lie the interface tells: the reader drags from 1 to 40
engineers, nothing moves, then a single step flips the whole stack. That reads as a broken
control, and it is worse than the honest version because it invites the user to believe the
product models something it does not. **Ship segmented controls with named stops, not sliders.**
Where a lever has three states, show three.

`concurrencyTarget` and `timeline` are both parsed and then **never read by any pick function**
(verified: zero reads in either engine). A "scale" slider's most natural target is currently dead
weight. Wiring it up is real engine work in both implementations, not a UI change.

## What already exists, and is most of the mechanism

This is the part the proposal missed, and it makes the feature far smaller than it looks. The
override machinery built for the inference toggles is exactly the machinery levers need:

- **`applySignalOverrides(raw)`** — the single funnel where raw signals become effective signals.
  Called in 4 places, including inside `setAnalysis`. This is the injection point.
- **`toggleInference(kind, key)`** — already computes `before`, applies a change, computes
  `after`, diffs them, shows the user precisely what will change, and asks for confirmation.
- **`diffRecommendations(before, after)`** — already produces the changed-card list. This is the
  "flash the mutated nodes" requirement, already built.
- **`lastRawSignals`** — the untouched base to re-derive from, so levers compose rather than
  accumulate.

Performance is a non-issue: `detectSignals` + `computeRecommendations` measured **0.054 ms** in
the browser engine and **0.41 ms** in Python. Re-running on every interaction is ~18,000
recomputes/second; there is no need for debouncing, workers, or incremental evaluation.

## Phasing, by cost

The decisive fact for sequencing: **a lever that flips an existing boolean needs no engine change
at all**, and therefore carries no dual-engine parity risk. Only a lever that needs a *new* signal
touches both engines.

### Phase 1 — levers over existing signals (small, no parity surface)
Team size, scale, and compliance. Extend `signalOverrides` from its current
`{excluded, known}` shape to also carry boolean overrides, and have `applySignalOverrides` apply
them. No new signals, no `rule_engine.py` change, no parity risk. The existing before/after diff
supplies the changed-card highlighting.

The one real design question is **confirmation**. `toggleInference` currently opens a
`confirm()` dialog per change, which is right for "permanently withdraw an inference" and wrong
for a lever the user is sweeping to explore. Levers should apply immediately and show the diff as
a passive changed-summary, with the requirement text left untouched — exploration is not the same
act as revision, and conflating them is how a what-if tool becomes annoying enough to ignore.

### Phase 2 — the scale lever properly (medium, parity surface)
Wire `concurrencyTarget` into the picks that should read it, in both engines, with corpus cases
added to `test_engine_differential.py`. This is a genuine engine change and should be its own PR,
justified on its own merits rather than as a slider's backing store — the signal being dead is a
defect whether or not levers ever ship.

### Phase 3 — budget (largest, needs a product decision first)
No cost-sensitivity signal exists. Adding one means new detection, new branches across many
picks, and parity for all of it. It also runs into a standing decision: the engine deliberately
produces **per-category cost bands**, some of which read "Not applicable — capex, not opex", and
`test_hero_does_not_invent_a_single_cost_figure` exists to stop those being summed into one
number. A budget lever implies exactly that summation. **Do not start Phase 3 without deciding
first whether the product is willing to claim a single cost figure** — that is a product
question, not an implementation one, and it was already answered "no" once.

## Prerequisite, now fixed

Scoping this surfaced a live defect in the diff the feature depends on. `OVERRIDE_EFFECT_CARDS`
had 22 entries and was missing the six vendor categories added after it was written, so
`diffRecommendations` could not report changes to them. Measured: an enterprise/PII signal moves
the sandbox pick E2B → Vercel Sandbox, and the diff reported **13 changes with that one absent**;
after the fix, 17 — it had also been hiding GitOps and Inference Serving changes. Worse, when a
toggle moved *only* one of those six, the dialog printed "No recommendation changes — this
inference is not currently driving any pick", which was false.

Fixed, and `test_category_wiring.py` now asserts it structurally. This mattered before levers
existed and matters more with them, since the diff is how a lever tells the user what it did.

This was the **third** map of this shape to fall behind, after `test_engine_differential.py`'s
`KEYMAP` and `CATEGORY_VENDORS`. All three are now derived from the code rather than listed.

## Out of scope

- **Sliders.** Named segmented stops instead, for the reason in the first section.
- **A single cost figure.** See Phase 3.
- **Re-running the LLM refinement per lever move.** Levers drive the deterministic engine only;
  refine/ask stay explicit user actions with their own cost.
- **Persisting lever state.** Exploration is per-session; the analysis history stores the
  requirement text, and a lever position is not part of it.

## Testing

- Node-harness tests over `applySignalOverrides` with lever overrides applied — same pattern as
  `test_inference_overrides.py`.
- A test that each lever's stops produce genuinely different recommendations. A lever whose
  positions do not move any pick is a control that does nothing, which is the failure mode this
  feature invites most.
- The existing `test_review_findings.py::test_every_analysis_path_goes_through_one_funnel`
  constraints hold: `setAnalysis`'s signature line must not change, and there must remain exactly
  two top-level `lastRawSignals =` assignments.
- Mutation-test every assertion, per this repo's standing practice.
