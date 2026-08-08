# Simple Audit — Where This Tool Stands vs. Current Market

Quick check, not a full re-run of `market-analysis.md`: has anything in the competitive
landscape moved since that research, and does what's actually been built since then still hold
the edge it claimed? Verified by re-searching, not assumed.

## 1. Direct competitors — no change

Re-searched for new entrants in the "describe requirements → get a recommended stack" niche.
**No new direct competitor found.** Still the same three from the original analysis:
[StackAdvisor.ai](https://www.stackadvisor.ai/), [TechStacker](https://www.techstacker.app/),
[Stack Studio](https://stackstudio.io/). TechStacker's own public copy ("frontend, backend,
databases, and deployment") shows no evidence of AI-native depth — no LLM/RAG/guardrails/MCP,
no device-tier sizing, no runtime selection. Nothing suggests either of the other two have added
this depth either.

**One naming collision worth knowing about, not a competitor:** [Stack AI](https://www.stack-ai.com)
is a real, larger product — a no-code AI agent/workflow builder (think Zapier-for-AI-agents) —
that shares a very similar name. It doesn't do requirements-to-architecture recommendation, so it
isn't competing for the same query, but it may outrank this project in casual search due to name
similarity and size. Worth being aware of for future naming/positioning, not something to react
to now.

## 2. What's been built since the last market check — genuinely widens the gap

Everything below was added or substantially deepened after the original market analysis, and
none of it shows up in any of the three direct competitors' public descriptions:

- **Device-tier compute sizing** — Mobile/Tablet → Laptop → Workstation/Studio-class (Mac Studio,
  DGX Spark) → Server → Enterprise datacenter, each with real RAM/VRAM figures and 4-bit
  quantization guidance. The one adjacent tool doing anything similar — [NVIDIA's AI vWS Sizing
  Advisor](https://docs.nvidia.com/vgpu/toolkits/sizing-advisor/latest/intro.html) — only sizes
  NVIDIA vGPU profiles for a single workstation tier; it doesn't span the device range or sit
  inside a general architecture advisor. This validates the need is real (NVIDIA built a tool for
  a slice of it) without being a competing product.
- **Ollama vs. OpenRouter vs. direct-SDK runtime selection**, reasoned from data sensitivity,
  existing self-host infra, and traffic pattern — not offered by any of the three competitors.
- **Per-task agent mapping** (reasoning/code/summarization/classification agents, each with a
  model tier and a local-vs-cloud runtime hint) layered onto the existing single-vs-multiple-model
  orchestration reasoning.
- **Hybrid/distributed/mesh topology reasoning extended to the agent layer**, not just LLM serving
  and RAG — three-layer reasoning none of the competitors' public descriptions claim.
- **13 vendor-alternatives comparison categories** (cloud, compute, containers, gateway, database,
  cache, messaging, LLM providers, vector DB, guardrails, CI/CD, observability, frontend), each
  with named vendors, tradeoffs, and sourced pricing — folded inline into the relevant Stack cards.
- **IAM Options** — the one dedicated deep-dive comparison section (5 identity providers, full
  tradeoffs/pricing).

Net effect: the original analysis called AI-native stack coverage (LLM/RAG/guardrails/MCP) this
tool's strongest differentiator. Everything added since then is either deepening that exact edge
(agent/runtime/device-tier reasoning) or extending the same transparent, sourced-reasoning
treatment to the general infrastructure categories competitors already cover more shallowly. The
gap looks wider now than at the original analysis, not narrower.

## 3. What still hasn't moved — the real gaps are unchanged

Polish and depth don't fix these, and re-confirming them here rather than letting the recent
feature work create false confidence:

- **Still zero users, zero distribution.** Nothing built since the original analysis changes this.
  It remains the single biggest gap versus "market state" in the sense that matters most —
  competitors at least have live marketing sites and are getting found; this tool isn't in front
  of anyone yet.
- **No cost estimator** — StackAdvisor.ai's concrete differentiator, still unmatched here.
- **No codebase-aware mode** — Stack Studio's differentiator (analyzing an existing codebase, not
  just text), still unmatched here.
- **Design/UI-UX patterns, TOGAF/SAFe, BFF, Waterfall-vs-Agile** — flagged as gaps in
  `dimension-expansion-requirements.md`, still just requirements, not implemented.

## Bottom line

Nothing changed on the competitive side since the last check — same three players, none of them
visibly matching the AI-native/device-tier/runtime depth just added. The work this session widened
an already-identified edge rather than reacting to new competition. The gap that actually matters
for "market state" hasn't moved at all: this is still a private tool with no users, and that's a
distribution problem no amount of additional feature depth solves.

**Sources:** [StackAdvisor.ai](https://www.stackadvisor.ai/), [TechStacker](https://www.techstacker.app/),
[Stack Studio](https://stackstudio.io/), [Stack AI](https://www.stack-ai.com),
[NVIDIA AI vWS Sizing Advisor](https://docs.nvidia.com/vgpu/toolkits/sizing-advisor/latest/intro.html)
