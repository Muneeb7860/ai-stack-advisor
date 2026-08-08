# Audit — Wiring the Alternatives Research into index.html

**Status:** Complete, including a subsequent information-architecture revision (see addendum at the
bottom). Documents a proper audit pass performed on the vendor-comparison wiring work, following the same
audit discipline used throughout `docs/alternatives-research/01-04*.md`.
**Why this exists:** the user explicitly asked for a proper audit of this chunk of work before handing
findings to a fresh Claude Code session — this is that audit, plus the fixes it produced.
**IMPORTANT — read the addendum before touching this code.** The findings below (1–7) were written
against an earlier version of the wiring that added 13 separate top-level nav sections. That version
shipped, then the user flagged low confidence in the resulting design (page/nav bloat — see addendum).
The comparisons were subsequently folded into inline "See alternatives" toggles on the existing Stack/AI
cards instead. All 7 findings and fixes below are still factually accurate and still apply to the current
code (same vendor-pick functions, same bugs, same fixes) — only the *placement* in the DOM changed. Don't
re-introduce 13 top-level sections while acting on this doc.

---

## Method

Rather than just re-reading the new code, every claim below was checked by actually running `index.html`'s
JS in a headless Node harness (`new Function()` over the extracted `<script>` blocks, with a minimal DOM
stub) against realistic requirement text, and comparing what two related cards say about the *same*
underlying signals. This is the same "don't just reason about it, run it" standard applied when the earlier
`pickMessaging()`/`pickRAG()` bugs were verified. Playwright screenshots were also used to visually confirm
fixes rendered correctly, not just that the JS returned the right string.

## Findings

### 1. (Fixed) Google Pub/Sub was mismapped to Apache Pulsar

`pickMessagingVendor()`'s original logic matched the substring `'Pub/Sub'` in the messaging pick and
highlighted the `pulsar` vendor card as the "best bet" — but Google Pub/Sub and Apache Pulsar are entirely
unrelated products that happen to share part of a name. A GCP-only requirement (no high-scale/realtime
signal) triggered this: `pickMessaging()` correctly returns "Google Pub/Sub (if GCP-native)," but the new
comparison card was starring **Apache Pulsar** as the best bet instead — a real, user-visible factual
error, not just a style nit.

**Fix:** added a real `pubsub` entry to `MESSAGING_VENDORS` and made the mapping check `'Pub/Sub'`
explicitly before falling through to the Pulsar/SQS checks. Verified via direct test: GCP-only input now
correctly stars Google Pub/Sub.

### 2 & 3. (Fixed) Splunk and Dynatrace picks were both mismapped to "New Relic"

`pickObservability()` can genuinely recommend Splunk (enterprise + compliance) or Dynatrace (enterprise +
highScale) — but neither vendor existed in `OBSERVABILITY_VENDORS`, so the mapping fell through to
`'newrelic'` in both cases. The result: a compliance-heavy enterprise requirement would show "Best bet:
Splunk (+ Datadog or Dynatrace for APM)" as the headline text, while the comparison card below it starred
**New Relic** — a vendor the underlying recommendation never even mentioned. Same root cause as finding 1
(a vendor pick with no corresponding comparison-table entry, silently absorbed by the wrong fallback
branch) and the more consequential of the two, since it could visibly contradict the plain-English pick
directly above it.

**Fix:** added real `splunk` and `dynatrace` entries to `OBSERVABILITY_VENDORS` (pricing intentionally left
qualitative/unsourced rather than inventing numbers — neither vendor was in the Group 4 research scope,
which covered Datadog/Grafana Stack/New Relic/Honeycomb/SigNoz specifically) and fixed the mapping to check
both explicitly. Verified via direct test against both trigger conditions.

### 4. (Fixed) Compute Options card could contradict the Compute Model stack card

`pickComputePlatform()` was written independently of `pickCompute()` and picked a FaaS/PaaS vendor purely
from cloud-shop/realtime/highScale signals, without checking what `pickCompute()` itself had already
concluded. For a small team building a real-time, high-scale product, `pickCompute()` correctly recommends
"Serverless containers (Cloud Run / Fargate)" — a container/orchestrator-tier answer — but
`pickComputePlatform()` independently landed on "Cloudflare Workers," a completely different tier of
product (edge FaaS vs. managed container platform). Two cards on the same page, for the same requirement,
recommending different *kinds* of infrastructure.

**Fix:** `pickComputePlatform()` now takes the already-computed `compute` result as an argument and checks
it first — when the Compute Model answer is container/orchestrator-tier (`startsWith('Kubernetes')` or
`startsWith('Serverless containers')`), the Compute Options card explicitly defers to the Orchestrator
Options section below instead of picking a conflicting FaaS/PaaS vendor. This is the same fix pattern
already used in `pickTradeoffs()` for its Kubernetes-vs-Serverless card (see that function's own comment
about mirroring `pickCompute()`'s branch order) — now applied consistently to the new card too.

### 5. (Fixed) Orchestrator Options card could contradict the Containers/Orchestration stack card

`pickOrchestrator()` had a special branch for `enterprise && compliance` that recommended OpenShift, a
condition `pickContainers()` (the original stack card) doesn't check at all — it just says plain Kubernetes
for `enterprise || highScale`. For a regulated enterprise requirement, the two cards disagreed: "Docker +
Kubernetes (EKS/GKE/AKS)" above, "OpenShift" in the comparison card below.

**Fix:** `pickOrchestrator()`'s branch conditions now mirror `pickContainers()` exactly (onPrem /
startupMvp / enterprise-or-highScale / default). OpenShift is still surfaced, but as a same-answer
refinement mentioned inside the `enterprise && compliance` case's explanatory text ("if you want a more
opinionated, supported distribution... OpenShift wraps Kubernetes with..."), not as a competing `primaryId`
that disagrees with the stack card above it.

### 6. (Fixed, documentation-only) LLM Provider Options note overclaimed unimplemented routing

`pickLLMProvider()`'s `primaryId` logic already correctly mirrors `pickLLM()`'s own compliance/enterprise/
security → Claude-vs-OpenAI split exactly (checked directly — no contradiction bug here, unlike findings
4–5). But the accompanying note claimed the section "routes to the wrapper" (Azure OpenAI/Bedrock) when a
compliance+cloud-shop signal is present — that routing was never actually implemented; the function only
ever returns `anthropic` or `openai` as the best bet, never `azureopenai`, `bedrock`, `mistral`, `deepseek`,
or `selfhosted`, even though all of those exist as full comparison rows.

**Fix:** rewrote the note to disclose this plainly as a known scope gap rather than asserting behavior that
isn't there — consistent with the "disclose gaps, don't paper over them" standard from the original
research docs' audit logs. Deliberately did **not** add the richer cloud-wrapper/cost-tier routing in this
pass, because doing so without also updating `pickLLM()` (the stack card above it) would risk creating a
*new* version of findings 4–5 — a good next refinement, but one that should touch both cards together, not
just this one in isolation.

### 7. (Minor cleanup, not a behavior bug) Redundant condition in `pickDatabaseVendor()`

`db.v.includes('warehouse') || db.v.toLowerCase().includes('warehouse')` — the first half is fully
redundant with the second (the warehouse pick text is already lowercase at that word), and the trailing
`: 'postgres'` fallback in the original ternary was duplicated at both the true and false ends of the same
final check. Cleaned up to a single `.toLowerCase().includes('warehouse')` check with one fallback. No
functional change — this never produced a wrong answer, just did redundant work to get the right one.

### Checked and found NOT to be a problem

- **`pickGatewayVendor()`** deliberately diverges from the "API Gateway / Edge" stack card (which also
  covers WAF/DDoS/edge concerns Kong/Tyk/etc. don't address) — this divergence is explicitly disclosed in
  `GATEWAY_NOTE`, not accidental, so it was left as-is.
- **`pickCICDVendor()`** reuses the original `cicd.v`/`cicd.why` text directly and only derives `primaryId`
  independently — checked every branch (onPrem/enterprise/startupMvp/default) and confirmed the highlighted
  vendor is always actually named in the corresponding `cicd.v` text. No contradiction found.
- **`pickGuardrailsVendor()`** — checked every branch's `primaryId` against its own `v` text; consistent
  throughout, no cross-vendor mismapping like findings 1–3.
- **`pickFrontendVendor()`** — intentionally scoped to web frameworks only; Flutter (mobile) isn't in
  `FRONTEND_VENDORS` and isn't claimed to be. Disclosed scope boundary, not a gap.

## Regression testing performed after fixes

- Full syntax check (`new Function()` over every `<script>` block) — passes.
- 8 end-to-end `analyze()` runs via a headless Node DOM stub, covering on-prem/air-gapped, GCP-only,
  enterprise+compliance, enterprise+highScale, startup+realtime+highScale, generic/no-signal, and
  structured+dataHeavy+enterprise scenarios — all 13 new comparison sections render in every scenario, no
  exceptions thrown.
- Playwright screenshots of the live page confirming the Pub/Sub fix renders correctly (distinct card,
  correct star) and that Flow View and the rest of the existing UI are unaffected.

## What Claude Code is inheriting

- All 5 real fixes above are already applied to `index.html` — nothing further to do on them.
- One disclosed, intentionally-deferred scope gap: `pickLLMProvider()` doesn't yet route to Bedrock/Azure
  OpenAI/DeepSeek/self-hosted even though those are fully documented comparison rows — see finding 6 for
  why this was deliberately left alone rather than half-fixed in isolation. If picked up, do it together
  with `pickLLM()` (the AI/LLM Recommendation stack card) so the two don't diverge, the same lesson
  findings 4–5 already paid for once.
- The general pattern worth carrying forward: **any new comparison card whose "best bet" is derived
  independently of an existing stack card's own pick logic needs to either (a) directly reuse/derive from
  that card's already-computed result, or (b) explicitly check it can't contradict that result for the same
  signals before shipping.** This bit twice in this pass (compute platform, orchestrator) despite being a
  known failure mode already documented in `pickTradeoffs()`'s own comments — worth a lint-style mental
  checklist item for future comparison sections, not just a one-time fix.

---

## Addendum — information-architecture revision (post-audit)

After this audit shipped, the user reviewed the result and said they weren't confident in the design. On
discussion, the actual problem wasn't any of the 7 findings above — it was structural: 13 new top-level nav
sections roughly doubled the page's section count (from ~15 to ~28 nav tabs) and made every category say
almost the same thing twice — once in its Stack card ("AWS, high confidence, here's why"), again a few
sections later in a near-duplicate "Best bet: AWS" card plus a vendor table. That diluted the one thing
that made the original IAM Options section work: it was the *one* place the tool deliberately went deeper,
which only reads as intentional when it's the exception, not the rule.

**Fix applied:** removed all 13 top-level `sec('...compare', ...)` calls. In their place, each vendor
comparison now renders as a collapsed-by-default `<details class="alt-toggle">` ("See N alternatives")
directly inside the matching existing card — the 10 applicable Stack cards (Cloud Provider, API Gateway/
Edge, Compute Model, Messaging/Streaming, Caching, Primary Database(s), Containers/Orchestration,
Observability, Frontend, CI/CD & Deployment), plus the AI/LLM Recommendation card (LLM Provider), Vector DB
card, and Guardrails card. `renderVendorCompare()` (which rendered a full standalone card with its own
"Best bet" header) was replaced by `renderAltToggle()`, which renders just the comparison list + note
inline — no duplicate header, since the parent card already shows the pick and its "why." IAM Options
remains the one dedicated top-level deep-dive section, unchanged, which was the right call rather than
also folding it in — it's the original, proven case for going deeper, and stays the exception that proves
the rule instead of becoming section 14 of 14 identical-looking ones.

**Data/logic-layer impact: none.** Every `pickXVendor()` function, every `*_VENDORS` array, every fix from
findings 1–7 above is untouched — this was purely a presentation-layer change (where the same HTML renders
in the DOM), verified by re-running the full regression suite (8 scenarios end-to-end, old section IDs
confirmed absent, `alt-toggle` elements confirmed present in the expected count per scenario) plus fresh
Playwright screenshots of both the collapsed and expanded states and Flow View (unaffected, since it never
referenced the removed sections).

**What this means for Claude Code:** if you're looking for "Cloud Options," "Database Options," etc. as
separate sections, they don't exist anymore — look for a "See N alternatives" toggle inside the relevant
Stack/LLM/Vector DB/Guardrails card instead. `renderAltToggle(vendors, primaryId, note)` is the current
shared renderer (in the same spot in the file `renderVendorCompare` used to be) — `renderVendorCompare` no
longer exists in the codebase.
