# Alternatives Research — Group 3: AI/LLM Layer
## Model Providers · Vector Databases · RAG Architectures · Guardrails

**Status:** Draft for audit — standalone research document, not yet wired into `index.html`.
**Prerequisites:** Group 1 (Infra) and Group 2 (Data layer) complete and audited. This document follows
the same step-by-step, sequential-audit instruction.
**Scope note:** this is the group most directly tied to the product's original core value proposition (LLM
sizing/provider pick, 14-type RAG selection, guardrails), so getting the categorization right here matters
more than in the other three groups — a wrong "which RAG type" recommendation is closer to the product's
main job than a wrong cloud pick.

---

## 1. LLM Model Provider Alternatives

`index.html`'s "LLM sizing/provider" section presumably already picks among major providers by workload
shape. This section adds the comparative strength/drawback/pricing-positioning layer, mirroring IAM.

| Provider | Category | Best for | Strength | Drawback |
|---|---|---|---|---|
| **OpenAI** | Frontier, broadest ecosystem | Teams wanting the deepest third-party tooling ecosystem and strongest general reasoning | Broadest library/integration support, mature fine-tuning + batch API, input caching cuts repeated-prompt costs | Often the highest sticker price; lower-tier rate limits; enterprise compliance requires routing through Azure OpenAI instead of the direct API |
| **Anthropic Claude** | Agentic workflows, code reasoning | Code assistants, multi-step agents, complex instruction-following | Strong multi-file code understanding, production-grade computer-use, effective long-context prompt caching | No public API fine-tuning; smaller third-party ecosystem than OpenAI; enterprise procurement often goes through AWS Bedrock rather than direct |
| **Google Gemini** | Multimodal, long-context | Video/audio/large-document workloads at scale | Native 1M+ token context with multimodal input, Flash variants optimize cost/token for high volume, built-in Vertex AI fine-tuning | Vertex AI adds operational overhead off-GCP; retrieval quality reported to degrade at extreme context lengths |
| **Azure OpenAI** | Enterprise compliance wrapper around OpenAI models | Enterprises needing private networking, compliance certs, auditability | SOC2/HIPAA/GDPR/data-residency certifications, Provisioned Throughput Units (PTU) for latency SLAs, native Azure AD/VNet isolation | Region-quota management overhead; throttling can occur earlier than raw OpenAI limits suggest |
| **AWS Bedrock** | Multi-model AWS-native platform | AWS-committed teams wanting one API across model families | Unified interface across Claude/Llama/Mistral/Titan, deep IAM/CloudWatch/VPC/S3 integration, provisioned capacity for SLAs | Model availability varies by region — region/model mismatches are a real operational gotcha |
| **Mistral AI** | Cost-efficient, EU-friendly, open-weight path | Teams wanting cost efficiency, multilingual strength, and an eventual self-hosting exit ramp | Competitive per-token pricing, open-weight models reduce lock-in, Codestral for code-specific tasks | Less mature reasoning/agentic feature set than the frontier labs; limited multimodal support |
| **DeepSeek** | Ultra-low-cost, high-volume | Price-sensitive, high-volume workloads where compliance certs matter less than unit cost | Reported 5–10x cheaper than frontier alternatives, strong coding performance for the price, OpenAI-API-compatible (easy swap-in) | Limited enterprise certifications; more variable reasoning consistency reported |
| **Self-hosted open-weight (Llama, Mistral open-weights)** | Self-hosted | Data-residency-strict requirements, or genuinely sustained high-volume usage with high GPU utilization | No per-token vendor cost at scale, full data control, no vendor lock-in, predictable latency (no shared-tenant queuing) | GPU rental runs $1,000+/mo even for a single high-end GPU; break-even is **far higher than intuition suggests** — see table below |

**Self-hosted economics, filled in (previously a flagged gap):** the break-even math is
`GPU VPS monthly cost ÷ blended API price per token`, and the actual monthly token thresholds are steep:

| API tier being displaced | Break-even volume (monthly tokens) | Realistic for most teams? |
|---|---|---|
| Frontier (GPT-5.x-class, Claude Opus-class) | 160M–256M tokens/mo | Reachable only with real sustained volume |
| Mid-tier (mini/Haiku-class) | 480M–768M tokens/mo | Rarely cost-effective to self-host |
| Budget open-weight API (DeepSeek, Together-class) | 2.5B–7B+ tokens/mo | Effectively unreachable for a single team |

GPU **utilization**, not just volume, drives the real cost: a rented GPU costs the same whether idle or
saturated, so cost-per-token effectively multiplies as utilization drops — roughly 1.7x at 60% utilization,
4x at 25%, 10x at 10%. On top of the raw GPU rental, realistic total deployment cost runs **1.3–5x the raw
GPU price** once you factor in engineer time for maintenance, model-update churn, and KV-cache/memory
tuning. Model-to-GPU fit: 8B models fit an RTX 4090 (24GB); 32B needs an RTX 4090-class card or better;
70B needs an A100 80GB or RTX 6000 Ada (48GB).

**Bottom line worth stating plainly:** for most teams, self-hosting only pays off financially at volume
most single products never reach. The non-cost reasons (data sovereignty, predictable latency, full
fine-tuning control) are usually the real justification, not per-token savings — switching to a cheaper
*API* tier (e.g. DeepSeek-class) typically beats self-hosting on pure cost while keeping zero ops burden.

**Sources:** [Cloudzy: Self-Hosting an LLM vs. API — Real Cost Math (2026)](https://cloudzy.com/blog/self-hosting-open-weight-llm-gpu-vps-cost/)

**Categorization note:** Azure OpenAI and AWS Bedrock are not independent model providers — they're
compliance/procurement wrappers around the same underlying models (OpenAI's and Claude/Llama/Mistral's,
respectively). A requirement signaling "needs SOC2/HIPAA" should route to the wrapper, not present it as a
different model choice from the underlying provider — this is the same "hosting model vs. core product"
distinction Group 2 drew between Supabase/Neon and the Postgres engine itself.

**Sources:** [Syncfusion: Top LLM API Comparison 2026](https://www.syncfusion.com/blogs/post/top-llm-api-comparison-2026)

---

## 2. Vector Database Alternatives

`index.html`'s RAG section needs a vector store choice as a sub-decision. This is a genuinely crowded,
fast-moving market with real cost/scale tradeoffs.

| Vector DB | Category | Best for | Strength | Drawback | Pricing signal |
|---|---|---|---|---|---|
| **Pinecone** | Fully managed SaaS | Startups/enterprises prioritizing speed-to-market over cost control | Zero-ops serverless, billions-of-vectors scale, strong multi-tenant isolation, built-in inference/reranking | Cost predictability issues at scale — pricing climbs steeply on Standard/Enterprise tiers | Free / $20+/mo (Builder) / $50+/mo (Standard) / $500+/mo (Enterprise) |
| **Milvus / Zilliz Cloud** | Open-source + managed | Billion-scale datasets | Cardinal engine reports up to 10x query throughput improvement, GPU acceleration, distributed querying | Self-hosted mode needs its own metadata store, object storage, and messaging system — real infra, not a single binary | OSS free; Zilliz managed pricing available |
| **Qdrant** | Open-source + managed | Budget-conscious teams still wanting production-grade performance | Composable search (dense + sparse + filters), Rust-native, excellent filtering, low self-hosting cost | Practical ceiling around ~50M vectors — not the pick for extreme scale | Free tier (1GB RAM/4GB disk); self-hosted ~$30–50/mo |
| **Weaviate** | Open-source + managed | Apps needing hybrid search (keyword + vector) in one query | Native BM25 + vector + metadata filtering combined, built-in vectorization, multi-modal support | GraphQL API has a real learning curve; JVM runtime is resource-heavy; external embedding calls add latency/cost | $45/mo minimum (Flex) up to $400+/mo (Premium) |
| **pgvector** | PostgreSQL extension | Teams already on Postgres with <10M vectors | Zero additional infrastructure, full ACID compliance, vectors + relational data in one transaction | Limited to Postgres ecosystem; HNSW index build time/memory pressure grows at scale | Free (OSS) — cost is just your existing Postgres |
| **MongoDB Atlas Vector Search** | Fully managed SaaS | Full-stack apps that already have operational data in MongoDB | Eliminates data-sprawl/sync-lag between app DB and vector store, Automated Embedding, native LLM-framework integration | Only pays off if you're already on MongoDB; capped at 4,096-dim embeddings | M0 free (512MB); Flex $0–30/mo; Dedicated ~$57+/mo |
| **Chroma** | Open-source (embedded/client-server) | Prototyping and early-stage LLM app development | Fastest path from zero to working vector search, intuitive API, accessible to non-experts | Not optimized for production scale; limited filtering vs. Qdrant/Weaviate | OSS free; Cloud Starter usage-based; Cloud Team $250+/mo |
| **LanceDB** | Open-source + cloud | Serverless functions, multimodal retrieval pipelines | File-based storage on S3/GCS (no always-on server needed), strong multimodal support, efficient on-disk filtering | Managed cloud tier less mature than Pinecone/Weaviate | OSS free; cloud/enterprise pricing available |
| **Faiss** | Open-source library (not a database) | Research, custom GPU-accelerated similarity search | High-performance similarity search, GPU support, flexible indexing (IVF/HNSW/PQ) | Library only — no persistence, query API, or ops tooling; you build the database around it | Free (OSS) |

**Categorization note:** pgvector and MongoDB Atlas Vector Search are "already have this database, add
vectors to it" choices, not general-purpose vector-database picks — a requirement should route to these
specifically when the existing-database signal is already Postgres/MongoDB, not as a first-class option
alongside Pinecone/Weaviate for a from-scratch build. Faiss is a library, not a deployable database — it
would need its own signal (something like "team has ML infra capacity to build around a library") rather
than sitting in the same list as fully managed options.

**Sources:** [MarkTechPost: Best Vector Databases in 2026](https://www.marktechpost.com/2026/05/10/best-vector-databases-in-2026-pricing-scale-limits-and-architecture-tradeoffs-across-nine-leading-systems/)

---

## 3. RAG Architecture Types

This is the section most directly relevant to the product's existing "14 RAG types" feature — this
research surfaced 9 well-documented, named patterns with clear best-for/complexity data; the remaining 5
of the product's 14 either weren't separately covered by this source or are compositions/variants of the
ones below (flagged as a gap in the audit rather than papered over with invented detail).

| RAG type | Best for | Strength | Complexity / drawback |
|---|---|---|---|
| **Naive RAG** | FAQs, internal docs assistants, HR bots, customer knowledge portals | Fast to deploy (days), reduces hallucination via grounding, minimal infra | Semantic similarity ≠ true relevance; no multi-hop reasoning; no self-correction on bad retrieval |
| **Hybrid RAG** | Enterprise search, regulatory reporting, IT ops knowledge systems, technical doc copilots | Combines vector + lexical (BM25/TF-IDF) search — consistently outperforms either alone, catches exact-term matches vector search misses | Needs vector DB + search engine + ranking logic together — moderate ops overhead |
| **Graph RAG** | Legal research, pharma R&D, compliance audits, M&A due diligence | Multi-hop reasoning across entity relationships, surfaces patterns flat vector search can't, better explainability via traceable chains | High graph-construction/indexing cost; ongoing entity-extraction maintenance; high architectural complexity |
| **Agentic RAG** | Multi-source financial analysis, incident investigation, enterprise copilots with workflow automation | Cross-system intelligence (CRM/SQL/APIs/storage), autonomous multi-step research, higher accuracy via iterative reasoning | Very high complexity; real governance exposure from autonomous tool use; variable latency, hard to observe/debug; realistic 3–9 month build |
| **Self-RAG** | Medical copilots, legal research, investment advisory, other risk-sensitive regulated domains | Reflection mechanism evaluates its own retrieval/generation quality, confidence scoring aids explainability, selective retrieval optimizes cost | Needs specialized training; more compute overhead; higher latency; harder monitoring |
| **Adaptive RAG** | Cost-sensitive deployments with mixed query complexity | Classifies query complexity and routes simple → fast path, complex → multi-step path | Medium-high complexity; needs a working query-classification mechanism; medium governance risk |
| **Contextual RAG** | Regulated-sector long-form docs (healthcare/finance/gov) | Preserves document-level context (headers, position) across chunk boundaries — fixes pronoun/reference ambiguity | Needs document-structure analysis + a metadata-enrichment pipeline |
| **Modular RAG** | Multi-domain enterprise deployments, orgs wanting to experiment at scale | Retrieval/indexing/generation/orchestration as swappable components — upgrade one without re-architecting the rest, supports in-production A/B testing | Higher engineering investment; interface-management and cross-module governance complexity |
| **Agentic Graph RAG** | Fraud detection across ownership chains, supply-chain risk, national-security intel, complex litigation | Combines autonomous agents with knowledge graphs — dynamic entity exploration, strategic path prioritization, multi-hop synthesis | Highest computational cost of this list; sophisticated orchestration required; hardest to observe/debug |

**Categorization note:** several of these compose rather than compete — Agentic Graph RAG is literally
Agentic RAG + Graph RAG combined, and Adaptive RAG is really a routing layer that could sit in front of any
of the others (naive for simple queries, agentic for complex ones) rather than being a fully separate
architecture. If the product's existing 14-type list treats all of them as mutually-exclusive single-select
options, that may itself be a categorization simplification worth a second look — flagged for audit, not
fixed here since verifying against the actual 14-type list wasn't in scope for this research pass (see
Audit Log).

**Sources:** [Techment: 10 RAG Architectures 2026](https://www.techment.com/blogs/rag-architectures-enterprise-use-cases-2026/)

---

## 4. Guardrails Alternatives

`index.html`'s guardrails section presumably picks a single default. This is a category with a real
open-source-vs-commercial split worth surfacing distinctly.

| Guardrail tool | Category | Best for | Strength | Drawback | Pricing |
|---|---|---|---|---|---|
| **NVIDIA NeMo Guardrails** | Open-source, programmable middleware | Engineering teams wanting deep customization, vendor-neutral across LLM providers | Apache 2.0 (no vendor lock-in), GPU-accelerated sub-100ms latency, Colang DSL for complex business logic | Colang DSL has a real learning curve; needs your own operational infra | Free (OSS) |
| **Guardrails AI** | Open-source Python framework | Python teams needing strict, structured output validation | 50+ pre-built composable validators, Pydantic integration, self-hosted | Chained-validator configs get complex; streaming support has real limitations | Free (OSS) |
| **Lakera Guard** | Commercial, API-based security firewall | Security teams in regulated industries focused on prompt-injection and data-leakage prevention | Single API integration, no code changes needed, horizontally scalable, continuously updated threat models | Limited built-in observability; the gateway itself becomes a potential single point of failure for LLM traffic | Not publicly listed |
| **Azure AI Content Safety** | Cloud-managed content moderation | Azure-native teams running conversational AI / RAG in Azure | Native Azure OpenAI integration, multi-layer coverage (input/adversarial/output), container deploy for edge cases | Microsoft's own docs acknowledge accuracy limitations on context-sensitive cases | Not publicly listed |
| **Galileo** | Commercial, enterprise observability + runtime protection | Enterprise teams running production agents needing full eval + observability + runtime protection together | Luna-2 small models reportedly hit 0.95 F1 vs. GPT-4o's 0.94 F1 at 98% lower cost; multi-agent debugging; SaaS/VPC/on-prem deploy flexibility | Likely overkill/over-budget for a single-LLM-app use case; Luna-2 setup adds configuration complexity | Not publicly listed |
| **Llama Guard (3, 8B)** | Open-weight safety classifier (Meta) | Teams wanting a dedicated input/output safety classifier model rather than a rules framework | Fine-tuned Llama with a defined safety taxonomy; became the de facto open-source content classifier for LLM safety; reports competitive F1 on standard benchmarks (ToxiGen, LMSYS, OpenAI, Meta-internal datasets) | Not itself a full guardrails framework — needs orchestration around it; **uneven recall across harm categories** (weaker specifically on hate speech and obfuscated/adversarial requests); **high false-positive rate on legitimate benign-but-sensitive content** (educational, medical, fiction) — a real production-usability concern, not just a benchmark footnote; real latency cost to run (see below) | Free (open weights) — but not free to run, see below |
| **AWS Bedrock Guardrails** | Cloud-managed, AWS-native | AWS/Bedrock-committed teams wanting guardrails as a platform feature rather than a separate integration | Native integration with Bedrock-hosted models, no separate service to stand up; per-check granular pricing (pay only for the checks you enable); word filters and PII regex filters are free | AWS-only | Content filters (text) $0.15/1,000 text units · Denied topics $0.15/1,000 · Sensitive-info filters $0.10/1,000 · Contextual grounding checks $0.10/1,000 · Word filters free · Image content filters $0.00075/image · Automated Reasoning checks $0.17/1,000 per policy (a "text unit" = up to 1,000 characters, rounded up) |

**Llama Guard latency, filled in (previously a flagged gap):** running Llama Guard yourself has a real
compute cost even though the weights are free — p99 latency runs ~50ms on an A100, ~120ms on an A10G, and
500ms+ on CPU (CPU-only is flagged by the source as unsuitable for production use). For comparison, OpenAI's
Moderation API runs closer to ~20ms but trades that for API dependency and a different false-positive
profile; Perspective API is built for community toxicity/hate-speech moderation specifically and is weak
for instruction-following-safety use cases (jailbreaks, prompt injection) that Llama Guard targets. No
source found compared Llama Guard head-to-head against Guardrails AI or Lakera specifically — that
narrower gap remains open (see Audit Log).

**Categorization note:** the open-source-framework tier (NeMo Guardrails, Guardrails AI, Llama Guard) and
the commercial-platform tier (Lakera, Galileo, Azure Content Safety, Bedrock Guardrails) answer different
build-vs-buy questions — a "small team, no dedicated security engineer" requirement should route toward
the commercial tier's zero-integration-effort products, while a "needs deep customization, has ML
engineering capacity" requirement should route toward the OSS tier. This mirrors the IAM section's
existing primary/alternatives/complementary structure and could reuse that same data shape if wired in.

**Sources:** [Galileo: Best AI Guardrails Platforms 2026](https://galileo.ai/blog/best-ai-guardrails-platforms), [AI Moderation Tools: Llama Guard Benchmark Review](https://aimoderationtools.com/posts/llama-guard-benchmark-review/), [AWS: Amazon Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)

---

## 5. Cross-Section Observations (pre-audit)

- **Update (follow-up pass, closed):** the three gaps originally flagged here — self-hosted open-weight
  model pricing/performance, Llama Guard's comparative benchmarks, and AWS Bedrock Guardrails' feature
  breakdown — have been filled in (Sections 1 and 4 above) with sourced data rather than left open. One
  narrower gap remains: no source directly compared Llama Guard head-to-head against Guardrails AI or
  Lakera specifically (see Section 4 and Audit Log). This group is now on equal footing with Groups 1–2.
- **Also resolved since the original draft:** the two concrete product findings this research surfaced —
  `pickMessaging()`'s Kafka-first fallback (Group 2) and `pickRAG()`'s agentic-vs-compliance waterfall gap
  (this group, Section 6 below) — have both been fixed directly in `index.html`, not just documented. The
  RAG fix specifically now returns "Agentic RAG + Corrective RAG (CRAG) validation layer" when a
  requirement is both agentic and compliance/healthcare-sensitive, instead of silently dropping the
  validation step.
- **RAG-type composability is a structural question, not just a vendor-comparison one.** Unlike Groups 1–2
  where "is X actually a substitute for Y" was mostly a labeling nuance, here it borders on the product's
  actual mental model (does the tool present 14 mutually exclusive RAG choices, or does it already
  understand that some compose?). This is worth a dedicated look at the shipped `index.html` RAG-picking
  logic before treating this document's categorization note as merely academic.
- **Wrapper-vs-provider pattern repeats a third time.** Azure OpenAI/Bedrock-as-wrapper (Section 1) and
  pgvector/Atlas-as-extension (Section 2) are the same shape of distinction seen in Group 2's
  Supabase/Neon-vs-Postgres-engine finding — this is starting to look like a recurring modeling principle
  worth a named pattern ("hosting/compliance wrapper vs. underlying engine") rather than a one-off note
  per group, if this research is synthesized into a final cross-group document later.

---

## 6. Audit Log

**Claims spot-checked:**

1. **Galileo Luna-2 benchmark (0.95 F1 vs GPT-4o's 0.94 F1, 98% lower cost)** — this is a vendor's own
   claim about their own product, surfaced via a source that appears to be covering/citing Galileo's
   marketing directly rather than an independent benchmark. Treated in the document as a reported claim
   ("reportedly") rather than an independently verified fact — this is the right level of skepticism given
   the source, and no second source was found to corroborate or refute it in this pass.
2. **DeepSeek "5–10x cheaper than frontier alternatives"** — consistent with DeepSeek's known public
   positioning and pricing structure; treated as a reasonable directional claim, not re-verified against a
   primary DeepSeek pricing page in this pass (lower stakes than Group 1's Kong pricing fix since no
   specific dollar figure is being asserted here, just a multiplier).

**Internal consistency checks:**

3. **Wrapper-vs-engine pattern applied consistently** — checked that Section 1 (Azure OpenAI/Bedrock) and
   Section 2 (pgvector/Atlas) both correctly flag themselves as wrappers/extensions rather than
   independent alternatives, consistent with the same distinction already established in Group 2. Holds.
4. **RAG-type overlap (Agentic Graph RAG = Agentic + Graph)** — checked this isn't presented as a
   contradiction but as an explicit composability note; confirmed the table doesn't double-count strengths
   between the two component types in a way that would mislead a reader.
5. **No vendor appears with conflicting claims across sections** — Claude/Anthropic, Bedrock, and
   Azure all appear in Section 1 only; no cross-section duplication found.

**Known limitations carried forward:**

- ~~Self-hosted open-weight model economics~~ — **closed in this follow-up pass**, see Section 1.
- ~~Llama Guard's comparative performance/pricing~~ — **closed in this follow-up pass**, see Section 4
  (latency and benchmark-characterization data added; pricing is N/A since the weights are free, but the
  real compute cost to run it is now quantified).
- ~~AWS Bedrock Guardrails' feature/pricing breakdown~~ — **closed in this follow-up pass**, see Section 4
  (full per-check pricing table added from AWS's own pricing page).
- **Still open:** no source directly benchmarked Llama Guard against Guardrails AI or Lakera specifically
  (only against OpenAI Moderation, Perspective API, and NeMo Guardrails) — narrower than the original three
  gaps, and lower priority since Guardrails AI/Lakera solve a different layer of the problem (validation
  framework / commercial firewall) than Llama Guard's classifier role, so a direct benchmark comparison is
  less apples-to-apples than it might first sound.
- ~~Whether `index.html`'s actual RAG-type-picking logic already treats types as composable~~ — **checked
  during audit, and the resulting bug has since been fixed directly in `index.html`** (see note above in
  Section 5). `pickRAG()` (line 579) is confirmed as a flat single-select over a 14-entry `RAG_TYPES`
  array, chosen by an if/else waterfall (structured→SQL RAG, agentic→Agentic RAG, enterprise+KB→Graph RAG,
  compliance/healthcare→Corrective RAG, dataHeavy→Hybrid RAG, else→Retrieve-and-Rerank as the default).
  This confirms the composability gap this document raised is real, not hypothetical: the waterfall can
  only return one type, so a requirement that's simultaneously agentic AND compliance-sensitive (a
  realistic combination — an autonomous compliance-auditing agent, per Section 3's own Agentic RAG
  best-for row) will get Agentic RAG and silently lose the Corrective-RAG validation layer, purely because
  `agentic` is checked before `compliance` in the waterfall. This is a genuine, evidence-backed finding
  (not just a research-document observation) — worth flagging to the user as a concrete follow-up, same
  tier of finding as Group 2's Kafka-fallback gap, but with more real-world consequence given RAG
  selection is closer to this product's core purpose.

**Audit verdict (updated after follow-up pass):** Group 3 (AI/LLM layer) is complete, and the three
research gaps originally disclosed here — self-hosted model economics, Llama Guard's benchmark/latency
profile, and Bedrock Guardrails' pricing — have since been closed with sourced data (Sections 1 and 4), not
filled with invented numbers. One narrower gap remains open by design (Llama Guard vs. Guardrails AI/Lakera
head-to-head) since no source covered it and it's lower-priority given the products solve different layers
of the problem. The genuine, code-verified product finding from this pass — `pickRAG()`'s single-select
waterfall silently dropping Corrective-RAG validation on agentic+compliance requirements — has already been
fixed directly in `index.html`, not just left as a documented recommendation. Groups 1–4 are all now
complete and audited; this document has no further open action items.
