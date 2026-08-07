const fs = require('fs');
const {
  Packer, Paragraph, TextRun, AlignmentType,
  NAVY, ACCENT, LIGHT, MUTED, GOOD, WARN,
  h1, h2, h3, p, pRuns, bullet, bulletBold, numbered, reqTable,
  pageBreak, hr, coverTitle, baseDoc, standardPage,
} = require('./helpers');

const children = [];

// ---------- Cover ----------
children.push(...coverTitle(
  'Product Requirements Document',
  'Functional & technical specification',
  [
    ['Document Version', '1.0'],
    ['Status', 'Draft — describes v1 as-built + v2 as-designed'],
    ['Prepared by', 'Muneeb, with Claude (Cowork)'],
    ['Date', new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })],
    ['Companion document', 'Business Requirements Document (BRD)'],
  ]
));

// ---------- Doc control ----------
children.push(h1('1. Document Control'));
children.push(reqTable(
  ['Version', 'Summary'],
  [1600, 7400],
  [
    ['1.0', 'Initial PRD, written to document v1 (shipped) and v2 (designed, pending backend access) — this PRD was written after v1 was built and validated, not before, and reflects the actual implementation rather than a forward-looking spec alone.'],
  ]
));

// ---------- Overview ----------
children.push(h1('2. Product Overview'));
children.push(p('AI Stack Advisor is a single-page web application. A user pastes a free-text description of their product or business requirement; the application detects signals in that text across ~35 dimensions (industry, scale, compliance, latency, data type, team size, existing vendor commitments, and more) and renders a full architecture recommendation organized into 16 navigable sections, covering both traditional infrastructure decisions and AI-native decisions.'));
children.push(p('v1 runs entirely client-side: a JavaScript rule engine embedded in a single HTML file, with no server, no API calls, and no data leaving the browser. v2 (designed, not yet built) adds an optional backend for LLM-assisted refinement of ambiguous cases, persistence via share links, and an MCP tool wrapper for use from Claude Desktop/Code.'));

// ---------- Problem statement ----------
children.push(h1('3. Problem Statement'));
children.push(p('See BRD Section 3 for the full business framing. In product terms: a user with a business requirement in their head has no fast way to translate it into a concrete, defensible technology and AI architecture without either (a) already having architect-level expertise across infrastructure, application design, and AI systems simultaneously, or (b) spending days researching and cross-referencing trade-offs manually.'));

// ---------- Goals & non-goals ----------
children.push(h1('4. Goals & Non-Goals'));
children.push(h2('4.1 Goals'));
children.push(bullet('Zero-friction input: a single free-text field, no wizard, no required structured fields.'));
children.push(bullet('Complete-in-one-pass output: every major architecture decision category answered in a single analysis, not a multi-step flow.'));
children.push(bullet('Transparent reasoning: every recommendation states why, and every head-to-head trade-off states when to switch.'));
children.push(bullet('Honest uncertainty: confidence badges distinguish signal-driven recommendations from defaults.'));
children.push(bullet('AI-native depth: LLM sizing, RAG taxonomy, hosting, guardrails, and MCP are first-class sections, not an afterthought bolted onto a generic web-stack tool.'));
children.push(h2('4.2 Non-Goals'));
children.push(bullet('Not an infrastructure provisioning tool — never executes changes, only recommends.'));
children.push(bullet('Not a benchmarked "ground truth" tool — v1 has not been validated against expert architect judgment at scale, only against internally crafted test scenarios (see Section 12).'));
children.push(bullet('Not (yet) a multi-user collaborative product — no accounts, no shared workspaces in v1 or v2.'));

// ---------- Personas ----------
children.push(h1('5. Target Users & Personas'));
children.push(p('The product explicitly frames its output as synthesizing six professional perspectives; each stack recommendation is tagged with the role that would typically own that decision. These are not separate personas of the tool\'s users — they describe whose judgment the tool is trying to approximate for a user who may not have access to all six.'));
children.push(reqTable(
  ['Perspective', 'Typically owns'],
  [2600, 6400],
  [
    ['Enterprise Architect', 'Cloud provider, IAM, service mesh'],
    ['Solution Architect', 'API gateway/edge, architecture style, compute model, DNS'],
    ['Application Architect', 'Languages, messaging, database, frontend'],
    ['AI Architect', 'LLM selection, model orchestration, RAG, guardrails, MCP'],
    ['SDE', 'Caching, containers, CI/CD, concurrency/throughput'],
    ['TPM', 'Observability ownership (shared with SDE), governance (KRA/KPI/SLA/reliability)'],
  ]
));
children.push(p('The actual end-user segments (who opens the tool) are addressed in BRD Section 5 and remain an open commitment — non-technical founder, developer/technical founder, and enterprise architect/TPM are the three candidate segments, each requiring a different depth/hand-holding balance this PRD does not yet resolve.'));

// ---------- User stories ----------
children.push(h1('6. User Stories'));
const stories = [
  ['As a solo founder scoping an MVP', 'I want a stack recommendation from one paragraph of description', 'so that I don\'t need to hire an architect before writing my first line of code.'],
  ['As a developer evaluating Kafka vs. a managed queue', 'I want the tool to tell me not just what to pick but exactly when I\'d need to switch', 'so that I can defer the decision confidently instead of over-engineering on day one.'],
  ['As an AI product builder', 'I want guidance on LLM size, RAG pattern, and guardrail placement specific to my use case', 'so that I don\'t have to separately research 14 RAG variants and cross-reference them against my compliance needs.'],
  ['As an engineer in a regulated/air-gapped environment', 'I want the tool to recognize that constraint and never recommend a public-cloud service', 'so that I can trust the output enough to act on it without re-checking every line.'],
  ['As a TPM setting up a new service', 'I want starter KRA/KPI/SLA targets tailored to my project\'s risk profile', 'so that I have a first draft to negotiate with stakeholders instead of starting from a blank page.'],
];
children.push(reqTable(['As a...', 'I want...', 'So that...'], [2600, 3400, 3000], stories));

// ---------- Functional requirements ----------
children.push(h1('7. Functional Requirements'));
children.push(p('Grouped by module. Each row reflects what is actually implemented in v1 unless marked otherwise.'));

children.push(h2('7.1 Input & Signal Detection'));
children.push(reqTable(['ID', 'Requirement'], [1000, 7400], [
  ['FR-1', 'Accept free-text business/product requirement input via a single textarea; no required structured fields.'],
  ['FR-2', 'Provide five one-click example scenarios spanning fintech, healthcare, e-commerce, enterprise, and early-stage MVP profiles.'],
  ['FR-3', 'Detect ~35 signal dimensions from the input text (industry, scale, compliance, latency, data type, team size, cloud vendor mentions, language mentions, and more) via keyword and pattern matching.'],
  ['FR-4', 'Strip short negated clauses ("no compliance requirements", "don\'t need X") before signal matching, so stated non-requirements are not read as requirements.'],
  ['FR-5', 'Detect on-premises/air-gapped/no-public-cloud requirements from raw (non-negation-stripped) text, since these are phrased using negation words that are themselves the requirement.'],
]));

children.push(h2('7.2 Core Technical Stack (15 categories)'));
children.push(p('Cloud provider, API gateway/edge, IAM, backend language(s), architecture style, compute model, messaging/streaming, service mesh, caching, primary database(s), containers/orchestration, observability, frontend, CI/CD & deployment, DNS.'));
children.push(reqTable(['ID', 'Requirement'], [1000, 7400], [
  ['FR-6', 'Each of the 15 stack categories must return a recommendation, a plain-language rationale, a confidence rating (High/Medium/Low), and the architect role that typically owns that decision.'],
  ['FR-7', 'On-premises/air-gapped detection (FR-5) must override the default recommendation in every category where a public-cloud service would otherwise be suggested (cloud, gateway, compute, containers, observability, CI/CD, DNS).'],
  ['FR-8', 'Analytics/ETL-heavy workloads without a transactional, chat, or RAG signal must be routed to a data-warehouse recommendation (BigQuery/Snowflake/Redshift) rather than a general-purpose OLTP database.'],
  ['FR-9', 'Conflicting signals (e.g. a small team combined with high-scale/enterprise requirements) must resolve to a stated middle-ground recommendation with the conflict acknowledged in the rationale, not a recommendation whose own justification contradicts part of the input.'],
]));

children.push(h2('7.3 Key Trade-off Decisions'));
children.push(reqTable(['ID', 'Requirement'], [1000, 7400], [
  ['FR-10', 'Provide explicit head-to-head recommendations for: single-cloud vs. multi-cloud, Terraform vs. Pulumi/CDK/native IaC, Kafka vs. Pub/Sub vs. managed queue, and Kubernetes vs. serverless.'],
  ['FR-11', 'Each trade-off must state the recommendation, why, and an explicit "switch when" condition describing the trigger for reconsidering.'],
  ['FR-12', 'On-premises detection must override the cloud-strategy trade-off entirely, replacing the single-vs-multi-cloud question with a public-cloud-vs-on-premises framing.'],
]));

children.push(h2('7.4 AI / LLM Strategy'));
children.push(reqTable(['ID', 'Requirement'], [1000, 7400], [
  ['FR-13', 'Recommend single-model vs. multi-model orchestration strategy, with a standing task-to-model mapping table (reasoning/design, code generation, classification/routing, RAG synthesis, agent orchestration).'],
  ['FR-14', 'Recommend local vs. cloud model hosting based on budget and security/compliance signals, including a stated cost-crossover heuristic.'],
  ['FR-15', 'Provide a VRAM sizing reference table (4B/12B/30B/70B+ tiers, fp16 and int4-quantized footprints, typical GPU, notes) with the tier suited to the user\'s inputs highlighted.'],
  ['FR-16', 'Recommend interface topology (hybrid / distributed / mesh, each defined in-product) separately for the LLM serving layer and the RAG/retrieval layer.'],
  ['FR-17', 'Recommend MCP vs. direct API integration, with the reuse/multi-client condition that should trigger adopting MCP.'],
  ['FR-18', 'Recommend a RAG architecture from a 14-variant taxonomy, or explicitly state that RAG is not required, including the specific case where retrieval should target structured/SQL data instead of a vector store.'],
  ['FR-19', 'State explicitly where the vector database sits in the pipeline (or that none is required), and recommend a specific vector store choice based on existing database investment and scale.'],
  ['FR-20', 'Recommend guardrails as a 5-stage pipeline (input, retrieval/tool-call, in-flight generation, output, post-hoc evals/monitoring) — never input/output only.'],
]));

children.push(h2('7.5 Cost, Throughput & Governance'));
children.push(reqTable(['ID', 'Requirement'], [1000, 7400], [
  ['FR-21', 'Provide cost/resource optimization recommendations (compute right-sizing, reserved vs. spot capacity, storage tiering, LLM cost routing, caching, FinOps tagging).'],
  ['FR-22', 'Provide concurrency/throughput recommendations (async I/O, connection pooling, autoscaling strategy, read replicas, CDN, backpressure, response streaming, circuit breakers).'],
  ['FR-23', 'Provide governance targets across four categories — KRA, KPI, SLA, and reliability/continuous-improvement (MTTD/MTTR, postmortem cadence, error-budget policy) — tuned by the same input signals as the rest of the output, with an explicit disclaimer that these are starting-point defaults, not commitments.'],
]));

children.push(h2('7.6 Navigation & Presentation'));
children.push(reqTable(['ID', 'Requirement'], [1000, 7400], [
  ['FR-24', 'Provide a sticky navigation bar with jump-links to all 16 result sections.'],
  ['FR-25', 'Render each result section as an independently collapsible element, defaulting to open, with a single Collapse All / Expand All control.'],
  ['FR-26', 'Display all detected input signals as a visible chip list before the recommendation sections, so the user can see what drove the output.'],
]));

children.push(h2('7.7 Planned — v2 (Not Yet Built)'));
children.push(reqTable(['ID', 'Requirement', 'Dependency'], [1000, 5600, 1800], [
  ['FR-27', 'An optional "Refine with AI" pass that sends the free-text input and the v1 rule-engine output to an LLM (user\'s own Anthropic API key) for cases where the rules are uncertain or the user wants to ask a follow-up question about a recommendation.', 'Backend / desktop access'],
  ['FR-28', 'Share links: persist a completed analysis to a shareable URL.', 'Backend / desktop access'],
  ['FR-29', 'MCP tool wrapper (recommend_stack(...)) callable from Claude Desktop/Code directly.', 'Backend / desktop access'],
]));

// ---------- Non-functional ----------
children.push(h1('8. Non-Functional Requirements'));
children.push(reqTable(['ID', 'Requirement'], [1000, 7400], [
  ['NFR-1', 'v1 must run entirely client-side with zero external network calls, so no user input ever leaves the browser.'],
  ['NFR-2', 'Analysis must render synchronously with no perceptible delay (rule engine, not an LLM call) — this is a deliberate differentiator from LLM-generation-based competitors.'],
  ['NFR-3', 'The page must remain usable at 16+ result sections via the navigation/collapse features in FR-24/FR-25 rather than requiring a redesign as scope grows.'],
  ['NFR-4', 'The tool must never claim higher certainty than its signal detection supports — every recommendation carries a confidence rating (NFR extension of FR-6), and defaults are visually distinct (Low confidence) from signal-driven picks (High/Medium).'],
  ['NFR-5', 'v2\'s optional backend features must degrade gracefully — the client-side experience (v1) must remain fully functional if the backend is unavailable or the user has no API key.'],
]));

// ---------- Architecture ----------
children.push(h1('9. System Architecture'));
children.push(h2('9.1 v1 — As Built'));
children.push(p('A single self-contained HTML file. A JavaScript rule engine (detectSignals() plus ~30 pickX() functions, one per recommendation category) runs synchronously in the browser on form submit. No build step, no framework, no dependencies — chosen deliberately for a tool at this stage of validation, where operational simplicity matters more than the marginal benefit a framework would add (see BRD Section 3.3 differentiation on "zero cost to run").'));
children.push(h2('9.2 v2 — Designed, Pending Backend Access'));
children.push(p('Documented in full in the companion v2 Design Document. Summary: a FastAPI backend adds two endpoints — POST /api/refine (LLM-assisted reconciliation of ambiguous rule-engine output, only overriding a v1 pick when it can cite a specific reason from the input text) and POST /api/ask (grounded follow-up Q&A scoped to the current recommendation). Postgres stores shared analyses. An MCP server wraps the same logic as a callable recommend_stack(...) tool. All three require the user\'s own Anthropic API key and a live hosting environment neither available in a browser-only session.'));
children.push(h2('9.3 Data Flow (v1)'));
children.push(numbered('User enters free text and clicks Analyze.'));
children.push(numbered('detectSignals(text) returns a signals object (~35 boolean/derived fields).'));
children.push(numbered('Each pickX(signals) function returns a recommendation, rationale, and confidence rating for its category.'));
children.push(numbered('The results are assembled into 16 sections, rendered into the DOM inside a sticky-nav/collapsible-section shell.'));
children.push(numbered('Nothing is persisted; a page refresh clears all state (until v2\'s share-link feature ships).'));

// ---------- Success metrics ----------
children.push(h1('10. Success Metrics'));
children.push(p('See BRD Section 7 for the full metric definitions (completion rate, re-use rate, disagreement rate, segment concentration, cost per active user). No instrumentation exists yet in v1 — this is listed as an open item in Section 13.'));

// ---------- Release plan ----------
children.push(h1('11. Release Plan'));
children.push(reqTable(['Release', 'Contents', 'Status'], [1600, 6000, 1800], [
  ['v1.0', 'Core stack (15 categories) + AI/LLM recommendation + RAG + guardrails + MCP servers needed', 'Shipped'],
  ['v1.1', 'Trade-off decisions, cost/throughput, governance sections; persona tagging', 'Shipped'],
  ['v1.2', 'AI serving/integration layer: orchestration, hosting/VRAM, topology, MCP-vs-API, guardrail pipeline, vector DB placement', 'Shipped'],
  ['v1.3', 'Sticky nav + collapsible sections', 'Shipped'],
  ['v1.4', 'Validation/QA pass — negation handling, on-prem support, warehouse detection, conflict-resolution fixes', 'Shipped'],
  ['v1.5', 'Flow View: node-canvas visualization of the recommendation (n8n/Voiceflow/VectorShift-style pan/zoom/drag graph, alternate to the card view); recursive logic audit — fixed several false-positive signal matches and a same-report contradiction between the Compute Model card and the Kubernetes-vs-Serverless trade-off card', 'Shipped'],
  ['v2.0', 'LLM refinement endpoint, share links, MCP tool wrapper', 'Designed — blocked on backend/desktop access'],
]));

// ---------- Known limitations ----------
children.push(h1('12. Known Limitations'));
children.push(p('From the Validation Report and general assessment — listed explicitly so they are tracked, not discovered later:'));
children.push(bullet('Keyword/pattern matching is inherently approximate; the negation-stripping fix (FR-4) reduces but does not eliminate false-positive signal detection on unusual phrasing.'));
children.push(bullet('No benchmark exists against real expert-architect judgment — validation to date is internal scenario testing (11 cases), not comparison against how senior architects would actually decide the same inputs.'));
children.push(bullet('The rule engine encodes a snapshot of current technology/model landscape knowledge and will drift out of date as new models, tools, and best practices emerge, with no automated update mechanism.'));
children.push(bullet('Confidence ratings reflect how much matching signal was detected, not an externally validated probability of correctness — a "High confidence" pick is high-confidence in the sense that strong signal supports it, not that it has been checked against ground truth.'));

// ---------- Open questions ----------
children.push(h1('13. Open Questions'));
children.push(numbered('Which of the three target segments (Section 5 / BRD Section 5) should the product formally commit to, and how much should the depth/hand-holding balance change per segment?', 0, 'numbered-list-2'));
children.push(numbered('Should v1 add a cost-estimation feature to match StackAdvisor.ai\'s strongest concrete differentiator, or is that out of scope given the "not a provisioning tool" non-goal?', 0, 'numbered-list-2'));
children.push(numbered('What instrumentation is needed to capture the success metrics in Section 10 without violating NFR-1 (no data leaves the browser) — this is a real tension between measurement and the current privacy posture that needs an explicit decision.', 0, 'numbered-list-2'));
children.push(numbered('Once real users are exposed to the tool (BRD BR-7), what is the process for feeding disagreement/feedback back into rule-engine updates?', 0, 'numbered-list-2'));
children.push(numbered('Should the new Flow View (node-canvas visualization of the recommendation, added after this PRD was first drafted) be formalized as its own FR item in the next revision?', 0, 'numbered-list-2'));

const doc = baseDoc({
  sections: [standardPage(children, 'Product Requirements Document')],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync('/home/claude/ai-stack-advisor/docs/AI-Stack-Advisor-PRD.docx', buf);
  console.log('PRD written');
});
