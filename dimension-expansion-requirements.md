# New Decision Dimensions — Requirements Note

Captured from a product-direction conversation about sharpening the target audience: **orgs
that have already decided to build a new application** and need defensible reasoning across
every foundational decision (design, codebase, tools, cloud, security, deployment,
maintenance, redundancy, throughput, and more) before committing — not idea-stage validation.
See `market-analysis.md` for how this differs from the three direct competitors, none of whom
serve this "org reviewing a build proposal" audience directly.

Status: **All three implemented in `index.html`** (as Trade-off cards). See Section 4 for what
shipped and how the open question from Section 2a was resolved.

---

## 1. Already covered — no new work needed

Cross-checked against the current rule engine before writing new requirements, so this note
doesn't duplicate what already exists:

| Ask | Current state |
|---|---|
| Modular monolith over microservices for smaller orgs | `pickArchitecture()` already returns "Modular monolith (hexagonal internal structure), split into microservices later" for `startupMvp`/`smallTeam` signals, with microservices reserved for `enterprise`/`largeTeam`. |
| Istio as service mesh | `pickMesh()` already recommends Istio for `enterprise`/`largeTeam`, "not needed yet (revisit past ~10-15 services)" otherwise. |
| Hexagonal / "plug and play" architecture | Already embedded in the architecture recommendation text for all three `pickArchitecture()` branches (ports & adapters reasoning). |

## 2. New dimensions to build

### 2a. Delivery methodology — Waterfall vs. Agile vs. hybrid

**Not currently a dimension anywhere in the tool.**

Proposed signal set (open item — see note below on team-size framing):
- **Favors Waterfall:** fixed-price/fixed-scope contractual delivery, regulatory/compliance-bound
  delivery with mandated sign-off gates (some `compliance` + `enterprise` combinations), hardware-
  coupled builds where late-stage software change is expensive to absorb, low stakeholder
  availability for iterative review.
- **Favors Agile:** evolving/uncertain requirements (the common case for net-new product builds),
  small-to-mid teams that can't absorb heavyweight upfront specification overhead, frequent
  stakeholder feedback availability, `startupMvp` signal.
- **Favors hybrid (Agile delivery inside a Waterfall-gated governance shell):** `enterprise` +
  `largeTeam` without a hard regulatory driver — common in large orgs that need audit/budget
  gates but still want iterative engineering underneath.

**Open item to confirm before implementation:** the original ask framed this as "Waterfall due to
small size." Team size alone is not the standard driver — small teams are typically a stronger
argument *for* Agile, since they can't absorb Waterfall's upfront specification cost. The signal
set above treats scope certainty/contract type/compliance as primary and team size as a
secondary modifier. Flagging this explicitly so it can be confirmed or corrected before the
dimension is built, rather than silently encoding a small-team → Waterfall rule that would be
wrong for most users of this tool.

### 2b. BFF (Backend-for-Frontend)

**Not currently a dimension anywhere in the tool.**

Proposed signal set:
- Recommend a BFF layer when multiple distinct client types exist with materially different data
  shape/aggregation needs (e.g., `mobile` + `web` signals both present, or a public API +
  internal admin UI split) — the classic case BFF solves (per-client aggregation/shaping without
  polluting a shared general-purpose API).
- Skip BFF (plain API gateway + shared API is sufficient) for a single client type or early-stage
  builds where the aggregation-mismatch problem hasn't materialized yet (`startupMvp` with a
  single `web` or `mobile` signal, no signal of a second client type).
- Ties into the existing API Gateway/Edge and Frontend dimensions — needs to reference both
  rather than stand alone, since BFF is an API-shaping pattern sitting behind the gateway, in
  front of backend services.

### 2c. Enterprise/governance framework — TOGAF vs. SAFe vs. neither

**Not currently a dimension anywhere in the tool.** The existing Governance section (KRA/KPI/SLA/
Reliability targets) is operational targets, not framework/methodology selection — this is a
distinct, new dimension.

Proposed signal set:
- **TOGAF** fits when the ask is enterprise IT architecture governance — multiple systems/domains
  needing a shared architecture vocabulary, large `enterprise` orgs with an existing EA practice
  or the intent to build one, heavier documentation-and-review-gate culture.
- **SAFe** fits when the ask is scaling Agile delivery itself across multiple teams — `enterprise`
  + `largeTeam` orgs running (or wanting to run) coordinated Agile delivery across several squads,
  not just a single architecture governance question.
- **Neither** — the common case for small-to-mid orgs (`startupMvp`/`smallTeam`): both frameworks
  add coordination overhead that isn't justified below a certain org size/team count; lightweight
  architecture decision records (ADRs) plus the existing Governance section's KRA/KPI/SLA targets
  are enough.
- These two are not mutually exclusive in practice (an org can run TOGAF for architecture
  governance and SAFe for delivery coordination) — the dimension should be able to recommend both,
  either, or neither rather than forcing a single choice.

## 4. Closure note — what actually shipped

- **BFF (2b)** — folded into the existing "Single API gateway vs. multiple gateways" trade-off
  card (added separately, for the API-gateway-iteration question) rather than as its own card,
  since it's the same underlying decision (client-diversity-driven gateway splitting) — triggers
  when both `mobile` and `web` signals are present.
- **Delivery methodology (2a)** — implemented as its own trade-off card. The open question was
  resolved as flagged: team size is NOT the primary driver in the shipped logic. `fixedScope`
  (a new signal: fixed-price/fixed-scope/RFP/statement-of-work/government-contract language) is
  the primary Waterfall trigger; `enterprise && largeTeam` without `fixedScope` gets a hybrid
  (Agile delivery inside a lightweight gated shell); everything else defaults to Agile, with
  `startupMvp`/`smallTeam` alone actively raising confidence in the Agile pick rather than pulling
  toward Waterfall.
- **TOGAF vs. SAFe (2c)** — implemented as its own trade-off card. Recommends both, either, or
  neither depending on explicit mentions (new `togafMentioned`/`safeMentioned` signals) or, absent
  an explicit mention, `enterprise && largeTeam` (both worth evaluating) vs. everything else
  (neither — lightweight ADRs instead).

Verified against 5 scenarios (fixed-scope government contract, enterprise+large-team without a
contract, startup default, explicit TOGAF+SAFe mention, TOGAF-only mention) plus a full regression
pass across the 5 built-in examples — no errors.

## 3. Implementation notes for whoever builds this

Follow the same pattern as the existing alternatives-research wiring: add any new `detectSignals()`
keywords needed (methodology/framework language isn't currently detected at all), add a `pickX(s)`
function per dimension following the existing `{v, why, conf}` return shape, wire into `stackCards`
or a dedicated section per the established convention, and — per the project's audit discipline —
validate against a few crafted scenarios (not just the 5 built-in examples) before calling it done,
the way `validation-report.md` did for the original rule engine.
