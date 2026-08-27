# Cost Estimation Methodology

**Domain:** Directional monthly cost estimation for a proposed stack — compute, database, and LLM
API spend. Research date: August 2026. This document is the sourcing/methodology backing
`pickCostEstimate(s, ctx)` in `index.html`, which renders as the "Directional monthly cost
estimate" block at the top of the Cost & Resource Optimization section.

## Business context

Flagged repeatedly in this project's own market audit (`market-audit-2026-08.md`) as the single
concrete feature gap versus the closest direct competitor, StackAdvisor.ai, which ships a cloud
cost estimator. This document (and its corresponding code) closes that gap — with an explicit,
honest design choice: **a range, not a point estimate**, because a static client-side tool with no
backend and no live pricing API cannot know a user's actual traffic. A false-precision single
dollar figure would be a worse answer than an honestly-bounded range with its assumptions stated.

## Signals / triggers

Cost questions: `how much will this cost`, `monthly cost`, `cost estimate`, `budget`, `cloud bill`,
`what will we spend`, `pricing`, `cost per month`, `TCO`, `run rate`. Cost drivers: `LLM API cost`,
`token cost`, `cost per request`, `compute cost`, `database cost`, `egress cost`, `idle cost`.
Cost pressure: `cost-sensitive`, `budget conscious`, `reduce spend`, `too expensive`, `cheaper
alternative`, `self-host to save money`, `break-even`, `when does self-hosting pay off`.

## Design principle

Every competitor/reference tool researched (Helicone, YourGPT, DocsBot, AWS/GCP/Azure calculators)
presents a **point estimate for one exact configuration** — pick a model, enter token counts, get
one number. That's right for a tool where the user already knows their config. It's wrong for an
early-stage planning tool where the user is choosing between configs — a range framed around
low/medium/high scale (mirroring the tool's existing `startupMvp`/`highScale`/`enterprise` signal
tiers) is more honest and more useful at this stage, closer to how FinOps tools like Vantage/
CloudZero frame uncertainty than to a single-config calculator.

## Compute cost bands (monthly, order-of-magnitude, as of Aug 2026)

| Tier | Range | Basis |
|---|---|---|
| Low (startup/small team, no high-scale signal) | $0–$500/mo | Serverless/FaaS at low-to-moderate traffic — much of this lands inside cloud free tiers (Cloud Run: 2M free requests + 180K vCPU-sec + 360K GiB-sec/mo; Lambda: 1M free requests + 400K GB-sec/mo). |
| Medium (highScale / enterprise / realtime, not both enterprise+highScale) | $300–$1,500/mo | Serverless containers or a small-to-mid Kubernetes cluster (3–6 nodes) — control plane (EKS ~$72/mo, GKE/AKS often free for one cluster) + node cost + load balancer + storage. |
| High (enterprise AND highScale) | $10,000–$50,000+/mo | Enterprise Kubernetes footprint (100+ nodes, larger instance classes) — highly dependent on node count/instance class/multi-cluster setup. |
| On-prem | N/A — capex, not opex | Self-managed hardware is a one-time/amortized hardware+facilities cost, not a monthly cloud bill. |

Sources: [Cloud Run pricing](https://cloud.google.com/run/pricing), [AWS Lambda Cost Breakdown 2026 — Wiz](https://www.wiz.io/academy/cloud-cost/aws-lambda-cost-breakdown), [Kubernetes Pricing 2026: EKS vs AKS vs GKE — Sedai](https://sedai.io/blog/kubernetes-cost-eks-vs-aks-vs-gke).

## Database cost bands

| Tier | Range | Basis |
|---|---|---|
| Low | $25–$100/mo | Small managed Postgres (e.g. db.t4g.micro ≈ $11.52/mo compute-only, plus storage/backups) + small managed Redis (cache.t4g.micro ≈ $11.68/mo). |
| Medium | $150–$900/mo | Mid-tier Postgres (more vCPU/RAM, Multi-AZ roughly doubles cost) + Redis, plus a vector DB starter-to-production tier if RAG/knowledge-base signals are present. |
| High | $1,000–$5,000+/mo | HA multi-AZ Postgres, clustered/replicated Redis, production-tier vector DB at real scale. |
| Vector DB add-on (if `knowledgeBase`/`agentic`) | $0–$25/mo starter, $50–$700+/mo production | Pinecone free tier: ~2GB/350K vectors, $0/mo. Production: dedicated pods $70–$700+/mo depending on vector count/pod class; Qdrant Cloud reported ~32% cheaper than Pinecone at 50M+ vector scale per one vendor comparison. |

Sources: [Vantage RDS instance pricing](https://instances.vantage.sh/aws/rds/db.t4g.micro), [Economize ElastiCache pricing](https://www.economize.cloud/resources/aws/pricing/elasticache/cache.t4g.micro/), [Ranksquire Pinecone Pricing 2026](https://ranksquire.com/2026/04/02/pinecone-pricing-2026/), [LeanOps Qdrant vs Pinecone](https://leanopstech.com/blog/qdrant-cloud-pricing-2026/).

## LLM API cost — the highest-leverage number

Per-million-token pricing (input/output, official vendor pages as of Aug 2026):

| Provider/tier | Input $/MTok | Output $/MTok |
|---|---|---|
| Anthropic Haiku-class | $1 | $5 |
| Anthropic Sonnet-class | $2–$3 | $10–$15 |
| Anthropic Opus-class | $5 | $25 |
| OpenAI lightweight/fast tier | $0.20 | $1.20 |
| OpenAI flagship tier | $5.00 | $30.00 |
| Google Gemini Flash-Lite | $0.10 | $0.40 |
| Google Gemini Flash | $0.30–$1.50 | $2.50–$9.00 |
| Open-weight via OpenRouter (Llama/Qwen/Mistral-class) | $0.02–$0.36 | $0.03–$0.40 |

**The spread between frontier and budget-tier open-weight models is roughly two orders of
magnitude** — this is the single most important lever in the estimate, more impactful than
infrastructure tuning. Illustrative volume assumption used in the estimator (1,500 input + 500
output tokens/conversation):

| Volume tier | Conversations/day | Budget open-weight | Mid-tier hosted | Frontier |
|---|---|---|---|---|
| Low | ~1,000 | $3–$50/mo | $115–$160/mo | $1,050–$1,350/mo |
| Medium | ~3,000 | $9–$150/mo | $345–$480/mo | $3,150–$4,050/mo |
| High | ~30,000 | $90–$1,500/mo | $3,450–$4,800/mo | $31,500–$40,500/mo |

Prompt caching (reads at roughly 5–10% of input price on Anthropic/OpenAI) can cut repeat-context
cost 50–90% further for RAG/chatbot workloads with long, mostly-static system prompts — worth
modeling as a discount, not included in the base range above since it depends on prompt structure.

If the requirement's hosting recommendation is local/self-hosted (see `pickRuntime`/
`pickHostingLocation`), direct API spend is $0 — the cost instead shows up in the Compute band as
GPU infrastructure. This is the actual trade-off local hosting makes: capex/fixed infra cost
instead of variable per-token spend, not "free."

Sources: [Claude API Pricing](https://claude.com/pricing), [OpenAI API Pricing](https://developers.openai.com/api/docs/pricing), [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing), [OpenRouter Qwen pricing](https://openrouter.ai/qwen), [Live AI API Price Tracker](https://www.madebyagents.com/models/api-prices).

## Reference tools and how they present estimates

- **Infracost** — resource-level cost breakdown from IaC plan files, surfaced pre-deploy in
  PR comments/CLI.
- **Vantage.sh** — cloud + AI/LLM cost tracking via billing API integrations; dashboards over
  actual usage, not a priori estimation.
- **Helicone / YourGPT / DocsBot / llmpricecheck.com** — LLM-specific point-estimate calculators
  (model + token volume → one number).
- **AWS/GCP/Azure native calculators** — point estimates per exact resource configuration.

None of these present a range for early-stage planning the way this tool's estimator does — that's
the deliberate differentiation.

## Caveats and re-verification

- Vendor pricing moves — treat every figure above as a snapshot, not a permanent reference. Before
  using this for a real budget commitment, re-check the official pricing pages linked above.
- Compute/database bands are order-of-magnitude planning ranges, not itemized quotes — actual
  spend depends heavily on region, instance class, reserved/committed-use discounts, and existing
  free-tier headroom not modeled here.
- This methodology does not yet model storage/egress bandwidth, CDN costs, or third-party SaaS
  tooling (observability, CI/CD) — those remain qualitative recommendations elsewhere in the tool,
  not part of the dollar estimate.
