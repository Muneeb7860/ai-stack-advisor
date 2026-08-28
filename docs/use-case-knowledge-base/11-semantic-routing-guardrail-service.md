# Semantic-Routing / AI-Guardrail Service

**Status:** implemented — wired into `pickTradeoffs()` via the `routingGuardrailService` signal.

**Domain:** A dedicated service sitting in front of LLM calls to route requests to the right model
by cost/quality/task and/or enforce guardrails centrally — the architectural *pattern*, distinct
from the tool's existing Guardrails vendor comparison (which products to use inside it). Research
date: August 2026.

## Business context

Flagged as an open gap after the 8-domain use-case pass: the tool already compares guardrail
*products* (Guardrails AI, NeMo Guardrails, Llama Guard) and reasons about model orchestration
(which model per task, conceptually) and MCP-vs-direct-API integration, but had no reasoning about
whether routing/guardrail logic should run as its own dedicated service versus being duplicated
inline in every agent — a real and increasingly common architecture question once a product has
more than one model or more than one agent making LLM calls.

## Signals / triggers

Routing/cost: `route between models`, `multiple LLM providers`, `cost-optimize LLM calls`, `model
selection per task`, `different models per task`, `fall back to a stronger model`. Guardrail:
`prompt injection`, `jailbreak`, `PII redaction`, `content policy enforcement`, `centralized
guardrails`. Combined/infra: `LLM gateway`, `LLM proxy`, `AI gateway`, `semantic router`, `model
router`.

## Decision points

### A. The two problems this pattern solves

**Cost/latency misallocation** — sending every request to a frontier model wastes money and time
when most real-world queries are simple enough for a cheap model. RouteLLM's own benchmark is the
reference number: **~95% of GPT-4-level quality while routing only ~14% of queries to the strong
model** — the rest go to a cheap model, producing large blended cost savings without a
quality cliff.

**Guardrail duplication and inconsistency** — as agents/services multiply, each team
re-implements (or forgets) PII redaction, prompt-injection detection, jailbreak filtering, and
content-policy checks. Centralizing this in one service gives one enforcement point, one place to
tune thresholds, and one audit-log stream — instead of N independently-drifting copies.

Both are the same underlying shape: a decision every LLM call needs to make, cheaper and safer to
make once centrally than N times independently.

### B. Where it sits

Three placements recur in practice: **API gateway layer** (routing/guardrails piggyback on an
existing gateway once auth/rate-limiting/logging infra already exists there — common past ~100
engineers); **dedicated internal microservice** (a standalone "LLM control plane" — the sweet spot
for roughly 10–50 engineer orgs: enough surface area to justify a shared service, not yet large
enough that full gateway consolidation is mandatory); **embedded library per agent** (simplest,
lowest-latency-overhead, appropriate only for a single team/single model choice or still-stabilizing
requirements — explicitly fine early, a trap once scaled past a handful of services).

### C. Semantic routing approaches (increasing sophistication and cost)

1. **Rule-based** — keyword/regex/length conditions. Sub-millisecond, predictable, brittle. The
   recommended starting point.
2. **Embedding-similarity** — embed the query, route by cosine similarity to intent clusters.
   Handles paraphrasing without labeled data; needs threshold tuning.
3. **Trained classifier** ("predictive routing") — a lightweight model predicting which downstream
   model will produce acceptable quality for a query (what RouteLLM does). Highest payoff, highest
   setup cost — needs labeled preference data. A simple k-NN baseline is often competitive with a
   fully learned router, so add a classifier only after evaluating that it beats the simpler
   baseline, not by default.

Named tools: **Not Diamond** (hosted routing API), **OpenRouter's Auto Router**, **RouteLLM** (open
source, LMSYS reference implementation), **Martian**, **Portkey** (full AI gateway bundling
routing+caching+guardrails+observability), **Cloudflare AI Gateway** (edge-deployed, routing +
built-in Guardrails feature), **vLLM Semantic Router** (CNCF/vLLM open-source project combining
Mixture-of-Models routing with safety-signal detection).

### D. Guardrail placement — pre-call vs. post-call

**Pre-call (input)** — prompt-injection/jailbreak detection, PII detection/redaction. Cheapest to
make synchronous, and doubles as a routing short-circuit (reject obviously-unsafe requests before
they reach an expensive model). **Post-call (output)** — content policy, hallucination/groundedness
checks, structured-output validation. Often more expensive (may itself require an LLM-as-judge
call) — usually pushed to async/sampled execution rather than blocking every response, unless the
domain (healthcare, finance, regulated content) requires synchronous enforcement regardless of
latency. The common production pattern: synchronous fast checks in the request path, async/sampled
expensive checks feeding dashboards/alerts.

## Anti-patterns

- **Duplicating guardrail logic per agent/service** — copy-pasted safety code drifts, thresholds
  get loosened locally under deadline pressure, no single place to audit coverage gaps.
- **Routing purely on cost with no quality/safety fallback** — a router optimizing only for $/token
  without a fallback path for low-confidence or safety-sensitive classifications silently degrades
  quality or lets unsafe content through a cheap model.
- **Adding a routing layer before there's more than one model in play** — premature infrastructure;
  a single hardcoded model choice is simpler and correct until that changes.
- **Jumping to a trained classifier router without a simpler baseline** — a k-NN or rules approach
  often performs comparably with far less operational overhead.
- **Synchronous guardrail checks that add unacceptable latency to every request** — expensive
  post-call checks (LLM-as-judge) run inline on 100% of traffic instead of sampled/async.

## Reference implementations

**Not Diamond**, **OpenRouter Auto Router**, **RouteLLM** (open source), **Martian**, **Portkey**,
**Cloudflare AI Gateway**, **vLLM Semantic Router** (CNCF).

## Revisit triggers

- **§B (placement):** an embedded per-agent library is fine for a single team/model, but becomes a
  trap once scaled past a handful of services — move to a dedicated internal "LLM control plane"
  microservice in the **roughly 10-50 engineer** range, and reconsider folding routing/guardrails
  into the existing API gateway once past **~100 engineers** where that gateway infra already
  exists.
- **§C (routing sophistication):** start rule-based; add embedding-similarity once paraphrasing
  causes real misroutes; add a trained classifier only after evaluating that it beats a simple k-NN
  baseline — each step up in sophistication should be earned by a measured gap the simpler tier
  actually has, not adopted by default.
- **§D (guardrail placement):** post-call checks are usually async/sampled — revisit that to
  synchronous, blocking enforcement specifically once the domain (healthcare, finance, regulated
  content) requires it regardless of the added latency.

## As implemented in `index.html`

Wired into `pickTradeoffs(s)` via the `routingGuardrailService` signal (or implicitly when
`agentic && (compliance || security)`) — recommends a dedicated AI gateway (Portkey/Cloudflare AI
Gateway for bundled routing+guardrails+observability, or Not Diamond/OpenRouter/RouteLLM for
routing specifically), with explicit guidance to start with rule-based routing and skip the whole
layer entirely below 2+ models in production use.

## Sources

- [LLM Router Architecture: Best Practices for 2026 — Redis](https://redis.io/blog/llm-router-architecture-best-practices/)
- [Architecture Patterns for Scaling AI Guardrails — Galileo](https://galileo.ai/blog/scaling-ai-guardrails-architecture-patterns)
- [LLM Model Routing in 2026: Cost-Quality Optimization — DigitalApplied](https://www.digitalapplied.com/blog/llm-model-routing-2026-cost-quality-optimization-engineering-guide)
- [GitHub - vllm-project/semantic-router](https://github.com/vllm-project/semantic-router)
- [State of LLM Routers in 2026 — Pratik Bhavsar](https://pakodas.substack.com/p/llm-routers)
- [LLM Gateway Comparison 2026 — Flotorch](https://www.flotorch.ai/blogs/llm-gateway-comparison-2026)
- [AI Agent Guardrails: Pre-LLM & Post-LLM Best Practices — Arthur](https://www.arthur.ai/blog/best-practices-for-building-agents-guardrails)
- [Guardrails · Cloudflare AI Gateway docs](https://developers.cloudflare.com/ai-gateway/features/guardrails/)
- [AI Agent Anti-Patterns (Part 1): Architectural Pitfalls — Allen Chan](https://achan2013.medium.com/ai-agent-anti-patterns-part-1-architectural-pitfalls-that-break-enterprise-agents-before-they-32d211dded43)
