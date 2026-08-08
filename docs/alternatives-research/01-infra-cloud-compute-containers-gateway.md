# Alternatives Research — Group 1: Infrastructure
## Cloud · Compute/Serverless · Container Orchestration · API Gateway

**Status:** Draft for audit — standalone research document, not yet wired into `index.html`.
**Companion pattern:** follows the IAM/RBAC vendor-comparison format already shipped in `index.html`
(`IAM_VENDORS` → `pickIAM()`) — vendor/category/best-for/strength/drawback/pricing, plus a "best bet"
recommendation layer and categorization notes where products get confused with each other.
**Research method:** live web search + fetch, grounded in sources current as of Aug 2026 (see citations
per section). Knowledge-cutoff facts were NOT used for pricing/positioning claims — everything dollar-
denominated below was pulled from a 2026 source.
**Scope note:** this is Group 1 of 4 (per the user's step-by-step instruction). Data layer, AI/LLM layer,
and DevOps+Frontend follow as separate documents after this one is audited.

---

## 1. Cloud (IaaS) Alternatives

`index.html` currently frames "cloud" as a single-select among AWS / Azure / GCP / on-prem. This section
maps the second tier of the market: smaller/independent IaaS providers that are frequently the *actual*
right answer for cost-sensitive, non-enterprise, or infra-simplicity-first requirements — a gap the
current tool has no way to signal.

| Vendor | Category | Best for | Strength | Drawback | Pricing signal |
|---|---|---|---|---|---|
| **AWS** | Hyperscaler | Enterprise scale, broadest service catalog, compliance-heavy regulated industries | Deepest service breadth (ML, data, compute), largest talent pool, most third-party integrations | Most expensive at small-to-mid scale; steep learning curve; pricing complexity (hundreds of SKUs) | Baseline for comparison — usually the most expensive per-category |
| **Azure** | Hyperscaler | Microsoft-shop orgs (AD/Entra, .NET, Office 365 integration), enterprise procurement via existing MS contracts | Best-in-class enterprise identity/compliance tooling, hybrid on-prem story (Azure Arc/Stack) | Cheaper than AWS in most categories but still hyperscaler-tier pricing | Cheaper than AWS EC2 in ~64% of tracked categories (609/948) |
| **GCP** | Hyperscaler | Data/ML-heavy workloads, Kubernetes-native teams (GCP originated GKE/Borg lineage) | Strong data/analytics stack (BigQuery), competitive committed-use pricing, best free tier for serverless (Cloud Functions) | Smaller enterprise support org than AWS/Azure; product deprecation reputation | Cheaper than AWS EC2 in ~96% of tracked categories (47/49) |
| **DigitalOcean** | Simplified IaaS / PaaS-adjacent | Small teams, startups, side projects, predictable flat pricing | Radically simpler UX than hyperscalers, flat/predictable droplet pricing, good docs | Smaller service catalog (no deep ML/data stack), fewer regions, less enterprise compliance tooling | Cheaper than AWS EC2 in all 15 tracked categories |
| **Hetzner** | Budget IaaS (EU-centric) | Cost-sensitive workloads, EU-data-residency requirements, dev/staging environments | Lowest raw compute $/vCPU in the market by a wide margin | EU-only data centers (limited US/APAC presence), thinner enterprise support/SLA tier, smaller managed-service catalog | Cheaper than AWS EC2 in all 15 tracked categories — typically the cheapest of any provider tracked |
| **Oracle Cloud (OCI)** | Hyperscaler (enterprise/DB-focused) | Oracle DB workloads, enterprises with existing Oracle licensing, orgs wanting aggressive free tier | Strong "Always Free" tier, competitive high-memory/bare-metal pricing | Smaller ecosystem/community than the big 3; less mindshare among startups | Cheaper than AWS EC2 in all 24 tracked categories |
| **Linode (Akamai)** | Simplified IaaS | Developers wanting simple VPS + CDN (Akamai edge) combo | Simple pricing, Akamai's edge/CDN network now bundled | Smaller platform breadth post-acquisition still settling; fewer PaaS add-ons than DigitalOcean | Cheaper than AWS EC2 in ~83% of tracked categories (49/59) |
| **Vultr** | Budget IaaS | High-frequency compute/GPU rental, global points-of-presence | Wide global region footprint for a budget provider, GPU instance availability | Smaller managed-service ecosystem, support tier below hyperscalers | Competitive with Hetzner/DO on raw compute |
| **OVHcloud** | Budget IaaS (EU) | EU-sovereignty-conscious workloads | European sovereign-cloud positioning, competitive bare-metal pricing | Limited English-language support depth reported by some users; smaller US presence | Not in the 8-provider tracked set used here — flagged as a gap, see Audit section |

**Categorization note:** DigitalOcean, Hetzner, Linode, Vultr, and OVHcloud are NOT drop-in hyperscaler
replacements for workloads that need deep managed-service catalogs (managed Kafka, ML platforms, 50+
region compliance certs). They are best-bet for teams that don't need those services and are paying a
"hyperscaler tax" for infrastructure that's fundamentally just VMs + block storage + a load balancer.

**Best-bet logic (proposed, mirrors `pickIAM`'s primary/alternatives/complementary shape):**
- Regulated/enterprise + existing cloud commitment → keep current single-select (AWS/Azure/GCP), no change.
- Small team + cost-sensitive + no deep managed-service dependency signal → surface DigitalOcean/Hetzner
  as *alternatives*, not replace the primary recommendation.
- EU-data-residency signal (if ever added to `detectSignals()`) → Hetzner/OVHcloud become primary
  candidates, not just alternatives.

**Sources:** [CloudPriceCheck](https://cloudpricecheck.com/), [DigitalOcean: Hetzner Alternatives](https://www.digitalocean.com/resources/articles/hetzner-alternatives), [DigitalOcean: Linode Alternatives](https://www.digitalocean.com/resources/articles/linode-alternatives), [DigitalOcean: Vultr Alternatives](https://www.digitalocean.com/resources/articles/vultr-alternatives)

---

## 2. Compute / Serverless (PaaS + FaaS) Alternatives

This maps to `index.html`'s "compute" category (currently likely framed around containers/VMs/serverless
as a style choice). Two distinct sub-markets emerged from research and should NOT be collapsed into one
list: **frontend/full-stack PaaS** (Vercel/Netlify/Railway/Render/Fly.io) and **FaaS primitives**
(Lambda/Cloud Functions/Azure Functions/Cloudflare Workers).

### 2a. Frontend / Full-Stack PaaS

| Vendor | Free tier | Paid entry | Best for | Strength | Drawback |
|---|---|---|---|---|---|
| **Vercel** | 100GB transfer, 1M function calls, 4hr active CPU — **no commercial use on free tier** | $20/seat/mo (Pro) | Next.js apps | Built by the Next.js team; automatic ISR, edge middleware, image optimization | Hobby plan legally prohibits revenue-generating use; Pro's "Turbo" compute is ~9x the standard per-minute rate |
| **Netlify** | 300 credits/mo (~30GB bandwidth) — commercial use allowed | $19/seat/mo (Pro) | General frontend deployment, JAMstack | Commercial use allowed on free tier; mature build pipeline | Credit-based free tier is less predictable than flat limits; heavy builders exhaust credits fast |
| **Cloudflare Pages** | Unlimited bandwidth, 100 sites, 500 builds/mo | Enterprise (custom) | Static sites, JAMstack, edge-first apps | Unlimited bandwidth is unique in this list; no cold starts | Static/edge-function only — not a fit for traditional stateful backend compute |
| **Render** | 512MB/0.1 CPU web service + free Postgres (256MB, 30-day expiry) | $7/mo (Starter) | Backend APIs, full-stack apps needing a bundled DB | Free tier bundles a real Postgres + Redis, not just app hosting | Free services spin down after 15 min idle — 30-60s cold start on next request |
| **Railway** | $5 one-time trial credit only (not recurring) | $1/mo minimum (usage-based) | Startups, Docker-based apps, teams wanting no per-seat pricing | Usage-based (no per-seat tax), strong DX, instant deploys | Not a real free tier — trial credit runs out, then billing starts immediately |
| **Fly.io** | None for new accounts since Oct 2024 (2hr trial / 7-day demo only) | Pay-as-you-go | Container deployments needing always-on VMs (legacy accounts) | Always-on VMs, no cold starts, global anycast | New users should budget it as paid-from-day-one, not evaluate it as a free option |

**Categorization note:** these are PaaS products competing partly on developer experience and partly on
who absorbs infra-ops — they are not interchangeable with raw IaaS (Section 1) or with orchestrators
(Section 3). A requirement that says "small team, fast MVP, no dedicated infra person" should route here;
a requirement with real infra-ops capacity and cost sensitivity at scale should route to Section 1 or 3.

### 2b. FaaS Primitives

| Vendor | Free tier | Cold start | Billing model | Best for | Drawback |
|---|---|---|---|---|---|
| **AWS Lambda** | 1M invocations/mo, 400K GB-sec | 100–500ms | Wall-clock time (includes I/O wait) | AWS-native event-driven backends | API Gateway exposure is billed *separately* ($3.50/M requests) — headline free tier undercounts real HTTP cost |
| **Google Cloud Functions** | 2M invocations/mo (highest of the four), 400K GB-sec | 200–800ms | Wall-clock time | GCP/Firebase-integrated projects | — |
| **Azure Functions** | 1M invocations/mo, 400K GB-sec, 1.5GB max memory (Consumption tier) | 200–1000ms | Wall-clock time | Microsoft/.NET shops, enterprise Azure integration | Lowest per-function memory ceiling of the four on Consumption tier |
| **Cloudflare Workers** | 100K requests/day (~3M/mo), 10ms CPU/invocation | <5ms (V8 isolates) | **CPU time only**, not wall-clock | Edge computing, globally distributed APIs, I/O-heavy workloads | 10ms CPU cap per invocation on free tier (30s on paid) — not a fit for CPU-bound work |

**Key structural distinction worth encoding as a signal:** Workers' CPU-time billing (vs. Lambda/Cloud
Functions/Azure Functions' wall-clock billing) can make I/O-heavy workloads (the majority of typical CRUD/
API backends, which spend most of their time waiting on a database or another service) reportedly 10–50x
cheaper on Workers than on wall-clock-billed platforms. This is a genuinely different axis from "which
cloud" and could become its own signal (`ioHeavyWorkload` or similar) rather than being folded into the
existing compute pick.

**Sources:** [agentdeals.dev hosting comparison](https://agentdeals.dev/hosting-free-tier-comparison-2026), [agentdeals.dev serverless comparison](https://agentdeals.dev/serverless-free-tier-comparison-2026)

---

## 3. Container Orchestration Alternatives

(Researched earlier this session via spacelift.io — retained here for the consolidated document.)
`index.html` currently treats Kubernetes as effectively the default "containers" answer once a requirement
crosses a complexity threshold. That default is directionally right for most cases, but the market has
real, distinct alternatives worth surfacing rather than presenting Kubernetes as the only path.

| Vendor | Category | Best for | Strength | Drawback |
|---|---|---|---|---|
| **Kubernetes** | Orchestrator (baseline) | Teams at real multi-service scale needing the ecosystem | Largest ecosystem, cloud-portable, industry-standard | High operational complexity; overkill below a certain scale |
| **OpenShift (Red Hat)** | Enterprise K8s distribution | Regulated enterprises wanting a supported, opinionated K8s | Built-in CI/CD, security defaults, RH support contracts | Heavier, more opinionated, licensing cost |
| **Nomad (HashiCorp)** | Lightweight orchestrator | Teams wanting simpler scheduling without full K8s surface area, mixed workload types (containers + non-container) | Much simpler operational model than K8s; can schedule non-container workloads | Smaller ecosystem, fewer managed offerings, smaller talent pool |
| **Mesos/Marathon** | Orchestrator | — | — | **Retired Oct 17, 2025** (Apache committers voted to retire the project; moved to the Apache Attic, read-only) — should not be recommended for new projects |
| **Docker Swarm** | Lightweight orchestrator | Small teams wanting native Docker-tooling orchestration | Simplicity, native Docker CLI integration | Limited feature set vs K8s; declining ecosystem momentum |
| **AWS ECS** | Managed orchestrator (AWS-native) | AWS-committed teams wanting less operational overhead than self-managed K8s | Deep AWS integration, simpler mental model than K8s, Fargate serverless mode | AWS lock-in; smaller ecosystem than K8s |
| **VMware Tanzu** | Enterprise K8s platform | VMware-invested enterprises | Integrates with existing VMware infra investment | Heavy licensing cost, VMware ecosystem lock-in |
| **Google Cloud Run** | Serverless container platform | Stateless containerized services wanting zero infra management | True serverless container model — scales to zero, pay-per-request | Not a general orchestrator — no stateful workload story, GCP-only |
| **Incus/LXD** | System container manager | Teams wanting VM-like isolation with container-like density | Lower overhead than full VMs, strong isolation | Not a Kubernetes-workload-compatible model; niche adoption |
| **Cloud Foundry** | PaaS-orchestrator hybrid | Enterprises wanting a `git push`-style deploy model with governance | Strong "cf push" developer experience, mature buildpack model | Declining mindshare vs K8s-native tooling |
| **Docker (standalone)** | Container runtime | Single-host or small-scale deployments | Simplest possible entry point | Not an orchestrator — no multi-host scheduling |
| **Rancher (SUSE)** | K8s management layer | Multi-cluster K8s management across clouds | Strong multi-cluster/multi-cloud K8s UI and governance | Adds a management layer on top of K8s, not a K8s replacement |
| **Azure Container Instances** | Serverless containers | Simple, single-container workloads on Azure | Fast to spin up, no cluster to manage | Not an orchestrator — no multi-container scheduling model |

**Categorization note (important for `index.html` fidelity):** several of these are **not** Kubernetes
alternatives in the "pick one instead" sense — Cloud Run, ACI, and standalone Docker are single-container/
serverless primitives, not orchestrators, and Rancher is a management layer *for* Kubernetes rather than a
competitor to it. Presenting all 13 as equivalent "alternatives to Kubernetes" would be a categorization
error if wired into the tool later; the doc separates them here specifically to avoid that mistake.

**Sources:** [Spacelift: Kubernetes Alternatives](https://spacelift.io/blog/kubernetes-alternatives)

---

## 4. API Gateway Alternatives

`index.html`'s "gateway" category currently likely defaults to a cloud-native pick (API Gateway on AWS,
APIM on Azure) without surfacing the open-source/independent tier. This is the same pattern gap as IAM
before that section was built out.

| Vendor | Category | Best for | Strength | Drawback | Pricing signal |
|---|---|---|---|---|---|
| **Kong** | Open-source (Community) / Commercial (Konnect) | Microservices environments, teams wanting the largest plugin ecosystem | Established ecosystem, enterprise support tier available | PostgreSQL-based config storage adds overhead vs. etcd-based alternatives; enterprise pricing has many billing dimensions | OSS free; Konnect ~$105/mo/gateway service + ~$20–34/million requests (serverless vs. self-hosted/dedicated tiers price the per-million rate differently — verify current tier before quoting); Enterprise not publicly listed, requires sales consult |
| **Apache APISIX** | Open-source | High-performance/multi-cloud/hybrid deployments | Sub-millisecond proxy latency (NGINX + LuaJIT + etcd) | Requires operational management by the team (no managed-service default) | Free (OSS) |
| **Tyk** | Open-source / Commercial (Tyk Cloud) | Self-hosted or managed deployments needing full flexibility | Full deployment flexibility, consumption-based option | SSO/SAML restricted to higher paid tiers | OSS free; Professional ~$0–$3,800/mo; Enterprise custom |
| **Gravitee** | Open-source, event-native | Async/event-driven architectures (WebSockets, WebHooks, Kafka streams) | First-class async-API support — a genuinely different strength than REST-centric gateways | Smaller ecosystem than Kong/Tyk; self-hosting needs JVM + MongoDB + Elasticsearch | Community free (self-host infra ~$500–$2K/mo typical); Cloud per-gateway; Enterprise custom |
| **WSO2 API Manager** | Open-source, full-lifecycle | Enterprises wanting complete self-hostable governance without vendor lock-in | End-to-end platform: gateway + dev portal + analytics + monetization, 100% OSS | Self-hosting operational overhead; smaller market visibility than cloud-native competitors | Free (OSS) / Enterprise subscription |
| **AWS API Gateway** | Cloud-managed | AWS-native deployments wanting zero-ops | Auto-scaling, zero-ops convenience | Vendor lock-in; no built-in developer portal; costs compound with scale | HTTP APIs $1/M requests; REST APIs $3.50/M requests; 1M free/mo for 12 months |
| **Azure API Management** | Cloud-managed | Microsoft/Azure ecosystems | Native Azure integration | 8 pricing tiers total — genuinely complex to reason about; multi-region multiplies cost | Consumption ~$3.50/M calls; Developer ~$36/mo; Premium v2 ~$2,800/mo/unit |
| **Apigee (Google)** | Cloud-managed | GCP-integrated enterprise API programs | Deep GCP ecosystem integration, managed service | Vendor lock-in; no hybrid/multi-cloud support; hidden add-on costs (security, analytics) | $20/M standard calls; environment tiers $365–$3,431/mo; enterprise $8K–$25K/mo |
| **MuleSoft** | Commercial iPaaS (not a pure gateway) | Full integration-platform needs, not just API gateway | Broadest integration-platform scope of this list | Opaque pricing, lengthy procurement, most expensive option researched | ~$1,250/mo/vCore (Gold); reported $210K/yr for a typical Platinum 4-vCore/3-env contract |
| **Zuplo** | Cloud-managed, developer-first | AI-first API programs, teams wanting bundled pricing simplicity | Free tier includes dev portal; Enterprise bundles AI Gateway + SAML + audit logs into one contract | Newer/smaller vendor, less enterprise track record than Kong/Apigee | Free 100K req/mo; Builder $25/mo; Enterprise from $1K/mo |

**Categorization note:** MuleSoft is a full iPaaS (integration platform), not a pure API gateway — it's
included here because it appears in "API gateway alternative" searches, but a like-for-like swap against
Kong/Tyk would misrepresent its scope. Gravitee's event-native strength (async/streaming) is a genuinely
different axis from the REST-request/response gateways and should be a distinct signal, not just "another
gateway option," if this is ever wired into `index.html`'s decision logic.

**Sources:** [API7.ai gateway comparison](https://api7.ai/api-gateway-comparison), [Zuplo pricing comparison](https://zuplo.com/learning-center/api-gateway-pricing-comparison-2026), [DigitalAPI.ai: AWS API Gateway alternatives](https://www.digitalapi.ai/blogs/top-aws-api-gateway-alternatives)

---

## 5. Cross-Section Observations (pre-audit)

- **Pricing volatility is real and dated.** Several sources explicitly flag 2025–2026 pricing changes
  (Netlify's April 2026 credit-model shift, Vercel's Turbo-compute repricing, Fly.io's Oct 2024 free-tier
  removal, Railway's Oct 2025 trial-credit change). Any numbers wired into the product later should carry
  a "verify current pricing" disclaimer rather than being treated as static facts — this mirrors the IAM
  section's existing practice of citing sources rather than asserting numbers as permanent truth.
- **"Alternative" doesn't always mean "substitute."** Three of the four sections above surfaced products
  that get lumped into comparison lists but aren't actually interchangeable with the primary pick (Cloud
  Run/ACI/Docker aren't Kubernetes substitutes; MuleSoft isn't a pure gateway; Gravitee's event-native
  focus is a different job-to-be-done than REST gateways). This same pattern already had to be corrected
  once in the shipped IAM section (CyberArk/SailPoint aren't IdP replacements) — worth a deliberate check
  in the audit pass for each of these four subsections.
- **OVHcloud gap.** The cloud-pricing tracking source used (CloudPriceCheck) does not track OVHcloud, so
  its pricing-signal cell above is unverified against a live 2026 source — flagged for the audit pass
  rather than silently presented as equally well-sourced as the other seven providers.

---

## 6. Proposed Signal/Data Additions (not yet implemented)

If/when this is wired into `index.html`, mirroring the IAM section's `IAM_VENDORS` pattern would suggest:

- `CLOUD_IAAS_VENDORS` (Section 1) — gated behind existing cloud signals plus a possible new `costSensitive`/`smallTeam` combination.
- `COMPUTE_PAAS_VENDORS` and `FAAS_VENDORS` (Section 2, kept separate given they answered different questions in research) — gated behind existing compute-style signals.
- `ORCHESTRATOR_VENDORS` (Section 3) — gated behind existing container/Kubernetes signals, with the categorization note above enforced in the data (e.g., an `isOrchestrator: false` flag on Cloud Run/ACI/Docker/Rancher entries so a future `pickX()` doesn't present them as K8s-equivalent).
- `GATEWAY_VENDORS` (Section 4) — gated behind existing gateway signals.

This is a design note for later, not an action taken in this document — per the user's explicit choice of
"standalone research doc(s) first," no `index.html` changes have been made in this pass.

---

## 7. Audit Log (per user instruction: "do proper audit then take next")

Fact-check and consistency pass performed after first draft, before marking Group 1 complete.

**Claims independently re-verified against a second source:**

1. **Mesos/Marathon retirement.** First draft said "Retired Oct 2025" (from the Spacelift secondary
   source). Re-verified directly against the Apache Software Foundation's own retirement announcement
   (`announce@apache.org` mailing list) — confirmed exact date **October 17, 2025**, committer vote to
   retire, moved to the Apache Attic in read-only state. Upgraded from a paraphrased claim to a
   primary-source-confirmed one; doc updated with the precise date and mechanism.
2. **Kong Konnect pricing.** First draft (from Zuplo's pricing comparison) stated "~$105/month per gateway
   service; $200 per additional million requests." A second, independent source (API7.ai — a Kong
   competitor, so read with the usual competitor-source skepticism, but citing what reads as Kong's own
   published pricing page) gives the per-service base fee as the same **$105/month** (corroborated) but a
   **materially different per-million-request rate**: $20/M on the serverless tier vs. $34.25/M on
   self-hosted/dedicated — neither of which matches the $200/M figure in the first source. Resolution:
   the doc now presents the corroborated $105/mo base fee as-is, replaces the uncorroborated $200/M figure
   with the range actually found in the primary-adjacent source, and flags in the cell itself that the
   per-million rate is tier-dependent and should be re-verified before being quoted as fact anywhere
   downstream (e.g. if this ever gets wired into the product).

**Internal consistency checks:**

3. **Fly.io free-tier claim** appears in both Section 2a (PaaS) — "None for new accounts since Oct 2024"
   — consistently. No contradiction found between the table and prose.
4. **Cloud Run / ACI / Docker / Rancher mislabeled as Kubernetes alternatives** — checked against the
   Section 3 categorization note; confirmed the note explicitly calls out that these four are NOT
   apples-to-apples K8s substitutes, preventing the same category error the IAM section had to correct
   once already (CyberArk/SailPoint not being IdP replacements). No fix needed — the caveat was already
   present in the first draft, verified it holds.
5. **OVHcloud pricing gap** — confirmed CloudPriceCheck (the source used for the 8-provider cost-category
   comparison) does not track OVHcloud. Rather than fabricate a comparable "cheaper in N/M categories"
   statistic for it, the table leaves that cell honest ("not in tracked set") and Section 5 calls out the
   gap explicitly. This is a deliberate incompleteness disclosure, not an oversight.
6. **MuleSoft / Gravitee scope mismatch** — checked that both are flagged in the Section 4 categorization
   note as not being pure like-for-like gateway substitutes (MuleSoft = iPaaS, Gravitee = event-native).
   Confirmed present in first draft; no fix needed.

**Known limitations carried forward (not fixed, disclosed instead):**

- Pricing figures throughout are point-in-time (Aug 2026 sources) and several sources explicitly note
  recent repricing events (Netlify Apr 2026, Vercel Turbo-compute, Railway Oct 2025, Fly.io Oct 2024) —
  meaning this category moves fast enough that a "last verified" date matters more than usual. Recommend
  re-running this specific research doc's pricing cells on roughly a 2-quarter cadence if it's ever wired
  into a live product surface, rather than treating it as a one-time capture.
- Enterprise-tier pricing (Kong Enterprise, Apigee enterprise, MuleSoft) is largely "contact sales" /
  reported-anecdotally in the underlying sources rather than officially published — those figures are
  presented as directional signals, not quotable facts.

**Audit verdict:** Group 1 (Infra) is complete and internally consistent. One factual correction made
(Kong per-million pricing), one claim upgraded to primary-source confirmation (Mesos retirement date), no
contradictions found between sections, and known gaps/limitations are disclosed rather than papered over.
Ready to proceed to **Group 2: Data layer (databases/cache/messaging)**.
