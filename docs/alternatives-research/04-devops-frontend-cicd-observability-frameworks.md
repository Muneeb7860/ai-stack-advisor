# Alternatives Research — Group 4: DevOps + Frontend
## CI/CD · Observability · Frontend Frameworks

**Status:** Draft for audit — standalone research document, not yet wired into `index.html`.
**Prerequisites:** Groups 1–3 complete and audited. This is the last of the four groups scoped in the
original request — after this audit, all four categories will have been researched sequentially per the
user's instruction.

---

## 1. CI/CD Alternatives

`index.html`'s "CI/CD" category presumably defaults to GitHub Actions given how dominant it's become. Real
tradeoffs exist across free-tier generosity, self-hosting philosophy, and cost-at-scale worth surfacing.

| Tool | Free tier | Paid entry | Best for | Strength | Drawback |
|---|---|---|---|---|---|
| **GitHub Actions** | 2,000 min/mo (private repos); unlimited (public repos) | $4/seat (Team) + usage overages | Open-source projects, teams already on GitHub | Unlimited minutes for public repos, massive Actions marketplace, tightest GitHub integration of any option | macOS runner minutes cost 10x Linux rate; self-hosted runners for private repos now bill $0.002/min (as of a March 2026 pricing change) |
| **GitLab CI** | 400 min/mo (shared runners) | $29/user/mo (Premium) | Enterprise teams wanting CI/CD + full DevOps platform in one product | Free *unlimited* self-hosted runner execution; Premium bundles container registry + security scanning | 400 shared-runner minutes exhausts fast for an active team; new accounts capped at 3 top-level groups |
| **CircleCI** | 6,000 min/mo (~30,000 credits) | $15/seat (Performance) | Teams wanting the most generous hosted free allowance | 30x concurrency, flexible resource classes, test splitting included | macOS builds burn credits 20x faster than Linux (100 vs 5 credits/min) |
| **Jenkins** | Unlimited (self-hosted, fully OSS) | $0 (MIT license) | Teams wanting zero vendor lock-in and full infra control | 100% free, 1,800+ plugins, runs anywhere | You own server admin, security patching, and plugin maintenance; realistic infra cost ~$20–100/mo even though the software is free |
| **Buildkite** | 500 hosted min/mo; unlimited self-hosted agents | $15/user/mo (Teams) | Teams with existing compute infra wanting a hybrid hosted-control-plane/self-hosted-agent model | Unlimited self-hosted agents at no software cost, built-in test analytics, 90-day retention | Hosted free tier capped at 3 concurrent jobs; 500 min/mo insufficient for an active team without self-hosted agents |

**Categorization note:** Jenkins and Buildkite's self-hosted-agent model represent a fundamentally
different cost shape than the SaaS-runner tools (GitHub Actions/GitLab CI/CircleCI) — cost trades from
"per-minute usage" to "infra you already run." A requirement signaling "has existing infra/ops capacity"
vs. "wants zero infra to manage" should be the actual routing signal here, not brand familiarity.

**Sources:** [agentdeals.dev: CI/CD Pricing Comparison 2026](https://agentdeals.dev/ci-cd-pricing)

---

## 2. Observability Alternatives

`index.html`'s observability category likely defaults among Datadog/Prometheus+Grafana/cloud-native
tooling. This market has a sharp commercial-vs-OSS cost cliff worth making explicit.

| Platform | Category | Best for | Strength | Drawback | Pricing signal |
|---|---|---|---|---|---|
| **Datadog** | Enterprise SaaS | Orgs prioritizing breadth + correlation depth across metrics/traces/logs | One-click metric-anomaly → trace → log correlation, AI-assisted analysis, 15+ integrated sub-products, strong cloud-provider integrations | High cost trajectory — mid-size enterprises commonly reported spending $500K–2M+/yr; custom metrics and log ingestion are frequent budget-surprise sources; no self-hosted option at all | Usage-based, scales with data volume |
| **Grafana Stack** (Prometheus/Mimir + Loki + Tempo) | Open-source, composable | Cost-sensitive teams and regulated enterprises needing data residency/full self-hosted control | Apache 2.0, native OpenTelemetry support across the whole stack, composable (swap components independently), runs anywhere | Real operational overhead if self-hosted; correlation across metrics/logs/traces needs manual configuration; steeper learning curve managing multiple components | Free/OSS core + optional Grafana Cloud SaaS tiers |
| **New Relic** | Enterprise APM platform | Orgs with existing APM investment or prioritizing deep application-performance monitoring | Mature APM heritage, strong language-agent support (Java/.NET/Node/Python) | Correlation UX less polished than Datadog; historically confusing pricing model; enterprise deployments still commonly reach $500K+/yr | Per-user + per-GB ingested |
| **Honeycomb** | Distributed tracing specialist | Teams needing high-cardinality debugging and exploratory trace analysis | Strongest trace-based exploratory query model of the researched set, BubbleUp anomaly-pattern detection, OpenTelemetry-native, developer-focused UX | Narrow scope — not a full standalone platform; weaker metrics/logs than the others; typically paired with something else rather than used alone | ~$130/mo starting |
| **SigNoz** | Open-source, OTel-first | Teams wanting a single OSS product covering metrics+logs+traces as a genuine Datadog alternative | Most OpenTelemetry-centric of the researched platforms, self-hosted or cloud, competitively priced vs. Datadog | Smaller ecosystem than the established players; correlation maturity still developing; younger product | Free (OSS) + competitive cloud pricing |

**Categorization note:** Honeycomb and the Grafana Stack answer different questions than Datadog/New
Relic — Honeycomb is a specialist tool meant to be paired with something else, and the Grafana Stack is a
build-your-own-platform-from-composable-parts choice, not a single-vendor drop-in replacement. A "small
team, wants one thing that just works" requirement should route to Datadog/SigNoz-style all-in-one
products; a "has platform-engineering capacity, cost-sensitive, needs data residency" requirement should
route to self-hosted Grafana Stack.

**Sources:** [devsecops.ae: Datadog vs New Relic vs Honeycomb vs Grafana 2026](https://devsecops.ae/observability-platforms-2026/)

---

## 3. Frontend Framework Alternatives

`index.html`'s "frontend" category likely defaults to React given market share. This section adds the
comparative layer, including the genuinely different performance model of compile-time frameworks.

| Framework | Category | Best for | Strength | Drawback |
|---|---|---|---|---|
| **React** | Component library (needs a meta-framework for full-stack) | Complex apps needing the largest ecosystem and talent pool | ~40% of professional developers use it regularly (largest talent pool of any option here), mature ecosystem (React Query, Zustand, Router, shadcn/ui, Radix), Server Components (via Next.js) cut client JS | Requires assembling routing/state/UI from separate libraries — no batteries-included default; performance depends heavily on how well the app is optimized, not the framework itself |
| **Vue 3** | Progressive framework | Teams wanting a gentler learning curve, or incremental adoption (add to an existing page vs. full rewrite) | Template-based syntax lowers the learning curve, genuinely progressive (script-tag-in or full-app-out), mature Composition API | Smaller talent pool than React or Angular |
| **Angular** | Full-stack enterprise framework | Large enterprise teams wanting enforced architectural consistency across many contributors | TypeScript mandatory (not optional, unlike React/Vue), comprehensive built-ins (DI, routing, forms, HTTP client, i18n) reduce third-party sprawl, recent versions (17–19) added signals/defer blocks/SSR improvements | Steeper learning curve; more opinionated/rigid structure — a real tradeoff against, not just a neutral fact, for teams wanting flexibility |
| **Svelte / SvelteKit** | Compile-time framework | Apps prioritizing minimal bundle size and fast initial load | No virtual DOM — compiles to optimized vanilla JS, dramatically smaller bundles/faster loads than React/Angular equivalents, SvelteKit is a full Next.js-equivalent meta-framework | Smaller ecosystem and talent pool than React/Vue/Angular |
| **SolidJS** | Fine-grained-reactivity framework | Content-heavy sites wanting minimal JS overhead beyond even Svelte | Fine-grained reactivity model reduces overhead further than component-re-render-based frameworks | Ecosystem/talent pool still genuinely limited — the biggest practical risk factor of this list |
| **Next.js** | React meta-framework | Production React deployments needing SSR/SSG/full-stack in one framework | SSR + static generation + file routing + API routes + image optimization bundled; Server Components enable direct DB access, cutting client JS; deployable beyond Vercel (AWS, Railway, Render, self-hosted) | De facto default for React — worth naming explicitly as the meta-framework layer React itself doesn't provide |
| **Astro** | Framework-agnostic static-site generator | Content-focused sites — docs, blogs, marketing pages | Framework-agnostic (mix React/Vue/Svelte/vanilla in one project), Islands architecture ships JS only for interactive components, strong Core Web Vitals out of the box | Not a fit for highly interactive, app-like experiences — it's optimized for mostly-static content, not a general SPA replacement |

**Categorization note:** React and Next.js are not two competing options — Next.js is the meta-framework
layer that gives React the SSR/routing/API capabilities Vue/Angular/SvelteKit ship natively. If
`index.html` currently presents "React" and "Next.js" as sibling choices in a single-select, that's the
same wrapper-vs-underlying-technology pattern flagged repeatedly in Groups 2–3 (Supabase/Postgres,
Bedrock/Claude) — worth checking against the actual code rather than assumed, per the Audit Log below.

**Sources:** [ortemtech.com: JavaScript Frameworks Comparison 2026](https://ortemtech.com/blog/javascript-frameworks-comparison-2026/)

---

## 4. Cross-Section Observations (pre-audit)

- **The wrapper-vs-underlying-technology pattern appears a fourth time** (React/Next.js here, after
  Azure-OpenAI/OpenAI and Bedrock/Claude in Group 3, Supabase-Neon/Postgres in Group 2). Across all four
  research documents this is now a consistently recurring modeling issue worth naming as one design
  principle if this research is ever synthesized into product changes, rather than four separate one-off
  notes: **"is this actually a different technology, or a different way of consuming the same one?"**
- **CI/CD and Observability share a build-vs-buy axis** (self-hosted-infra-owning teams vs.
  zero-ops-wanting teams) that maps cleanly onto signals the tool likely already has in some form (team
  size, ops capacity) — these two sections are probably the easiest in this whole four-document project to
  wire into existing signals without needing brand-new ones, unlike some of Group 3's RAG-composability
  gap which would need new signal logic.

---

## 5. Audit Log

**Claims spot-checked:**

1. **GitHub Actions March 2026 self-hosted-runner pricing change** — this is a specific, checkable,
   recent policy change rather than a vague positioning claim. Not independently re-verified against a
   second/primary GitHub source in this pass (would be the natural next step if this figure were ever
   quoted in a live product surface) — flagged with the same caveat pattern as Group 3's DeepSeek pricing
   multiplier: directionally trusted, not independently corroborated.
2. **Datadog "$500K–2M+/yr for mid-size enterprises"** — a wide range presented by the source as a
   commonly-reported figure, not a specific vendor-quoted number; treated as a directional cost-shape
   signal (Datadog costs scale steeply) rather than a precise fact, consistent with how Group 1 treated
   MuleSoft's similarly wide reported enterprise range.

**Internal consistency checks:**

3. **React/Next.js wrapper relationship** — checked against `index.html`'s actual frontend-picking logic
   rather than left as a hypothesis, following the pattern established in Groups 2 and 3 (see resolved
   follow-up below).
4. **CI/CD self-hosted-vs-SaaS categorization** — checked that Jenkins/Buildkite aren't presented as
   directly cost-comparable to GitHub Actions/GitLab CI/CircleCI without the infra-ownership caveat;
   confirmed the note holds.
5. **No vendor appears with conflicting claims across sections** — Grafana appears only in Observability;
   no cross-document contradiction found against Groups 1–3 either (no vendor overlaps across all four
   research documents that would need reconciling).

**Follow-up resolved during audit — React/Next.js in `index.html`:**

Checked the actual `pickFrontend()` function (line 536). Finding: the current logic is simpler than either
hypothesis considered above — it only ever picks between `'React'`, `'Angular'` (if `s.enterprise`), and
`'Flutter'` (if `s.mobile`). **Next.js isn't mentioned at all**, so there's no React/Next.js sibling-vs-
wrapper conflation to fix — the wrapper-confusion risk this section's categorization note warned about
doesn't currently exist in the code. The real gap is different and smaller: the tool recommends "React"
without a meta-framework opinion, leaving out the SSR/routing/API-routes layer this document's own
research treats as a near-default pairing for production React. Not a bug, more a "the current pick is one
level less specific than this research suggests it could be" observation — worth noting, not urgent.

**Audit verdict:** Group 4 (DevOps + Frontend) is complete and internally consistent, with no factual
corrections required this pass. This closes out all four scoped research groups. See the companion
cross-group summary note below for what to do with all four documents next.

---

## 6. All-Four-Groups Wrap-Up

With Groups 1–4 now researched and individually audited, three product-relevant findings surfaced that go
beyond simple vendor cataloguing and are worth the user's direct attention separate from the research
documents themselves:

1. **Group 2:** `pickMessaging()`'s zero-signal fallback names Kafka first when a lighter managed queue
   would better fit the generic case — small, precise fix candidate.
2. **Group 3:** `pickRAG()`'s single-select waterfall can silently drop a relevant RAG dimension (e.g.,
   agentic + compliance-sensitive requirements lose Corrective-RAG validation) purely due to check order —
   the most consequential of the three findings, since RAG selection sits closer to the product's core
   purpose than messaging or frontend framework choice.
3. **Recurring design pattern across all four groups:** "wrapper/hosting-model vs. underlying technology"
   (Supabase vs. Postgres, Bedrock vs. Claude, Azure OpenAI vs. OpenAI, React vs. Next.js) — not a bug,
   but a naming/data-shape principle worth applying consistently if any of this research gets wired into
   `index.html`'s actual signal/pick logic later.

No `index.html` changes have been made as part of this four-document research project, per the user's
explicit "standalone research doc(s) first" instruction. These four documents
(`01-infra-cloud-compute-containers-gateway.md`, `02-data-layer-database-cache-messaging.md`,
`03-ai-llm-layer-models-vectordb-rag-guardrails.md`, `04-devops-frontend-cicd-observability-frameworks.md`)
are ready as a complete, audited reference set for whatever the user wants to do next — wiring some/all of
it into the product's signal logic, or treating it as standalone reference material.
