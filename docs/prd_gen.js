const fs = require('fs');
const path = require('path');
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
    ['Document Version', '1.5'],
    ['Status', 'v1 and v2 shipped, frontend actually wired to the backend — see Section 7.7, Section 9.2, and Release Plan (Section 11). Hexagonal diagram-export architecture, AI Opportunity Layer, technology-catalog unification, Huawei Cloud vendor support, and Hybrid Connectivity added in a later session — see Section 7.2, 7.7, 9.4, and Release Plan.'],
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
    ['1.1', 'Updated after a two-pass rule-engine expansion (separate session, frontend-only): signal count grew from ~35 to 65+, pickX() functions from ~30 to 45, spanning 8 new use-case domains, a directional cost estimator, a semantic-routing/guardrail-service dimension, and governance/security dimensions. Also new: a 12-file RAG knowledge-base corpus (docs/use-case-knowledge-base/) and a 21-case retrieval evaluation set. Section counts (16) and the core client-side-only architecture (NFR-5) are unchanged.'],
    ['1.2', 'v2 backend built and tested in a later session (FastAPI + Postgres + Alembic; share links, /api/refine, /api/ask, and the MCP tool wrapper — FR-27/28/29 all shipped, /api/refine and /api/ask grounded in the 1.1 RAG corpus). Updated Section 7.7, 9.2, and the Release Plan (Section 11) to reflect that; no functional requirement content changed, only status.'],
    ['1.3', 'Found via a documentation-vs-code validation pass: FR-27–29 marked "Shipped" based on the backend alone, without ever stating whether index.html actually called those endpoints — for a real stretch of this project it didn\'t (confirmed by grep: zero fetch() calls). Rewrote Section 7.7 to state both layers explicitly, added FR-27a (independent ask), FR-30 (why-this-pick signal inspection), and FR-31 (real cost display) — all shipped but previously undocumented. Corrected the Release Plan\'s stale "44 passing tests" to the actual 93 (verified via a live pytest run, not the prior static count).'],
    ['1.4', 'Resolved Open Questions in Section 13 (target segment hypothesis, telemetry privacy policy, low-overhead feedback mechanism) and formalized Flow View as FR-31a with cross-reference to v1.5 Release Plan.'],
    ['1.5', 'Later session: refactored diagram export (Flow View, Mermaid, Draw.io, SVG) onto a single hexagonal-architecture domain core (Section 9.4) — fixed a real inconsistency where exporters showed 5-8 nodes against Flow View\'s 18-20. Added the AI Opportunity & Leverage Layer (FR-32), unified the technology catalog into one source of truth with a maintainer CLI and client-side custom overlay (FR-33), added Huawei Cloud vendor support (FR-34) and a new Hybrid Connectivity core category (FR-6a, 16th category). Corrected stale counts: signal dimensions 65+ -> 100+, pickX() functions 45 -> 47, KB technologies now 243. Two real bugs found and fixed during this work, not just features added — see Section 12.'],
  ]
));

// ---------- Overview ----------
children.push(h1('2. Product Overview'));
children.push(p('AI Stack Advisor is a single-page web application. A user pastes a free-text description of their product or business requirement; the application detects signals in that text across 100+ dimensions (industry, scale, compliance, latency, data type, team size, existing vendor commitments, and more) and renders a full architecture recommendation organized into 16 navigable sections, covering both traditional infrastructure decisions and AI-native decisions.'));
children.push(p('v1 runs entirely client-side: a JavaScript rule engine embedded in a single HTML file, with no server, no API calls, and no data leaving the browser. v2 adds an optional backend for LLM-assisted refinement of ambiguous cases (grounded in a RAG knowledge-base corpus), persistence via share links, and an MCP tool wrapper for use from Claude Desktop/Code — all shipped.'));

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
  ['FR-3', 'Detect 65+ signal dimensions from the input text (industry, scale, compliance, latency, data type, team size, cloud vendor mentions, language mentions, and more) via keyword and pattern matching.'],
  ['FR-4', 'Strip short negated clauses ("no compliance requirements", "don\'t need X") before signal matching, so stated non-requirements are not read as requirements.'],
  ['FR-5', 'Detect on-premises/air-gapped/no-public-cloud requirements from raw (non-negation-stripped) text, since these are phrased using negation words that are themselves the requirement.'],
]));

children.push(h2('7.2 Core Technical Stack (16 categories)'));
children.push(p('Cloud provider, API gateway/edge, IAM, backend language(s), architecture style, compute model, messaging/streaming, service mesh, caching, primary database(s), containers/orchestration, observability, frontend, CI/CD & deployment, DNS, hybrid connectivity.'));
children.push(reqTable(['ID', 'Requirement'], [1000, 7400], [
  ['FR-6', 'Each of the 16 stack categories must return a recommendation, a plain-language rationale, a confidence rating (High/Medium/Low), and the architect role that typically owns that decision.'],
  ['FR-6a', 'Hybrid Connectivity category (added later session): recommend a dedicated-link + transit-hub pairing matched to the chosen cloud vendor (AWS Direct Connect+Transit Gateway, Azure ExpressRoute+Virtual WAN, GCP Cloud Interconnect+Network Connectivity Center, Huawei Direct Connect+Enterprise Router) plus VPN-failover and MACsec guidance, when a dedicated on-prem-to-cloud link is detected. Always rendered as the 16th card; content states "not required" or "not applicable" (air-gapped) rather than the card being hidden, matching every other always-shown category.'],
  ['FR-7', 'On-premises/air-gapped detection (FR-5) must override the default recommendation in every category where a public-cloud service would otherwise be suggested (cloud, gateway, compute, containers, observability, CI/CD, DNS, hybrid connectivity).'],
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

children.push(h2('7.7 v2 — Shipped'));
children.push(p('"Shipped" below means both layers: the backend endpoint is built and tested, AND index.html has a real, clickable UI element wired to call it. Earlier revisions of this table only asserted the first layer — for a stretch of this project\'s history the backend was fully shipped while index.html had zero fetch() calls to it at all. That gap is closed as of the guided-mode + backend-wiring milestone; both are true now.', { italics: true, color: MUTED, size: 19 }));
children.push(reqTable(['ID', 'Requirement', 'Status'], [1000, 5600, 1800], [
  ['FR-27', 'An optional "Refine with AI" pass that sends the free-text input and the v1 rule-engine output to an LLM (user\'s own Anthropic API key) for cases where the rules are uncertain. Adjustments are only made when the model can cite a specific reason; every pass is kept, not overwritten, so the reasoning history is comparable across repeated passes.', 'Shipped — POST /api/refine, per-card "✨ Refine with AI" button in index.html, refinement history retained client-side'],
  ['FR-27a', 'Follow-up Q&A scoped to a recommendation, independent of whether refine has been used on that card first.', 'Shipped — POST /api/ask, independent "💬 Ask a question" button in index.html'],
  ['FR-28', 'Share links: persist a completed analysis to a shareable URL, rendered read-only with the input form and AI buttons removed.', 'Shipped — POST /api/analyses/{id}/share, "📎 Share this analysis" button, ?shared=SLUG read-only view'],
  ['FR-29', 'MCP tool wrapper (recommend_stack(...)) callable from Claude Desktop/Code directly.', 'Shipped'],
  ['FR-30', 'Show which specific detected signals drove each stack card\'s recommendation, not just a confidence badge, so the "why" is inspectable per pick rather than only stated as prose.', 'Shipped — client-side only, no backend dependency'],
  ['FR-31', 'Show real LLM token cost (from the Anthropic response) alongside the existing directional cost estimate once a refine/ask call has been made.', 'Shipped — backend returns real usage from message.usage; not persisted to any table'],
  ['FR-31a', 'Flow View: interactive node-canvas visualization of the architecture recommendation (pan/zoom canvas, minimap, tier-colored nodes) as an alternate to the 16-section card view. Cross-references Release Plan v1.5.', 'Shipped — client-side only, no backend dependency'],
  ['FR-32', 'AI Opportunity & Leverage Layer: a 12-pattern catalog across all 6 architecture tiers (client/edge/compute/data/ai/ops), attached to Flow View nodes as "New AI Leverage Point" (gap — no AI touchpoint yet) or "AI Optimization Point" (an existing AI touchpoint could be upgraded). Text-to-SQL specifically enforces High complexity and mandatory read-only-replica/PII-tokenization/audit-trail prerequisites when finance/healthcare/compliance/onPrem signals are present, so regulated environments are never advised to expose transactional tables to unconstrained LLMs.', 'Shipped — client-side only, no backend dependency'],
  ['FR-33', 'Technology catalog unified into a single source of truth (#stackKbData.technologies, 243 entries) powering citations/ADR export, with a maintainer CLI (scripts/add_tech.py) that validates schema/domain/maturity-ring/duplicates before any entry is added, and a client-side localStorage overlay letting a user add a custom technology without editing the shipped catalog.', 'Shipped — client-side + a Python authoring script, no backend dependency for the app itself'],
  ['FR-34', 'Huawei Cloud vendor support: signal detection plus vendor-specific recommendations across cloud provider, API gateway (APIG + ROMA Connect), containers (CCE), DNS, observability (Cloud Eye + LTS), and CI/CD (CodeArts) — the same 6 categories AWS/Azure/GCP already branch on.', 'Shipped — client-side (index.html); backend rule_engine.py has the detection signal only, not the pick-logic branches — see Section 12 for why'],
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
children.push(p('A single self-contained HTML file. A JavaScript rule engine (detectSignals() plus 45 pickX() functions, one per recommendation category) runs synchronously in the browser on form submit. No build step, no framework, no dependencies — chosen deliberately for a tool at this stage of validation, where operational simplicity matters more than the marginal benefit a framework would add (see BRD Section 3.3 differentiation on "zero cost to run").'));
children.push(h2('9.2 v2 — Shipped'));
children.push(p('Documented in full in the companion v2 Design Document. A FastAPI backend adds two endpoints — POST /api/refine (LLM-assisted reconciliation of ambiguous rule-engine output, only overriding a v1 pick when it can cite a specific reason from the input text) and POST /api/ask (grounded follow-up Q&A scoped to the current recommendation). Postgres stores shared analyses. An MCP server wraps the same logic as a callable recommend_stack(...) tool. All three require the user\'s own Anthropic API key, passed per-request and never stored server-side. All four pieces (share links, /api/refine, /api/ask, MCP tool) are built and tested — see backend/README.md for the running system\'s test suite and quickstart.'));
children.push(h2('9.3 Data Flow (v1)'));
children.push(numbered('User enters free text and clicks Analyze.'));
children.push(numbered('detectSignals(text) returns a signals object (65+ boolean/derived fields).'));
children.push(numbered('Each pickX(signals) function returns a recommendation, rationale, and confidence rating for its category.'));
children.push(numbered('The results are assembled into 16 sections, rendered into the DOM inside a sticky-nav/collapsible-section shell.'));
children.push(numbered('Nothing is persisted unless the user explicitly saves/shares it via v2\'s share-link feature; a page refresh otherwise clears all state.'));
children.push(h2('9.4 Diagram Export Architecture (Hexagonal / Ports & Adapters)'));
children.push(p('Added in a later session, documented in full in docs/walkthrough-hexagonal-refactor.md. Prior to this, buildFlowGraph() (Flow View) and the three exporters (Mermaid, Draw.io, SVG) each independently re-derived their own view of the architecture from the raw recommendation object — Flow View showed 18-20 nodes, the exporters showed a hardcoded 5-8. buildCanonicalArchitectureGraph(ctx, signals) is now the single pure domain core (no browser globals, no file-format strings, no pixel coordinates) that every consumer builds from: layoutFlowGraph(graph) is the presentation adapter that adds x/y/color for Flow View only, and the three exporters serialize the same canonical {nodes, edges} instead of a reduced subset. Mirrors the ports-and-adapters separation already enforced in a sibling project\'s (Swish_App) HexagonalArchitectureTest.java, adapted to this repo\'s single-file frameworkless constraint (no Java package tree, no build step) as a static-analysis contract test (backend/tests/test_architecture_contracts.py) plus Node-executed runtime checks instead.'));

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
  ['v2.0', 'Share links, LLM refinement endpoint (/api/refine), grounded follow-up Q&A (/api/ask), MCP tool wrapper (recommend_stack) — FastAPI + Postgres + Alembic backend, 93 passing/xfailed tests', 'Shipped'],
  ['v2.1', 'Frontend wiring: guided-input wizard, per-card Refine/Ask buttons actually calling the v2.0 backend, share button, ?shared=SLUG read-only view, why-this-pick signal inspection, refinement-pass history, real LLM cost display', 'Shipped'],
  ['v2.2', 'Hexagonal diagram-export refactor (Section 9.4) — fixed Flow View/exporter node-count inconsistency; AI Opportunity & Leverage Layer (FR-32) — fixed a phantom-signal-key bug that had silently disabled the compliance guardrail it shipped with; technology catalog unified to one source of truth with maintainer CLI + custom overlay (FR-33); Huawei Cloud vendor support (FR-34); Hybrid Connectivity category (FR-6a) — fixed a pre-existing onPrem false-positive this work surfaced (see Section 12)', 'Shipped'],
]));

// ---------- Known limitations ----------
children.push(h1('12. Known Limitations'));
children.push(p('From the Validation Report and general assessment — listed explicitly so they are tracked, not discovered later:'));
children.push(bullet('Keyword/pattern matching is inherently approximate; the negation-stripping fix (FR-4) reduces but does not eliminate false-positive signal detection on unusual phrasing.'));
children.push(bullet('No benchmark exists against real expert-architect judgment — validation to date is internal scenario testing (35+ crafted scenarios across the original validation pass and the two-round expansion pass), not comparison against how senior architects would actually decide the same inputs, and not real end users.'));
children.push(bullet('The rule engine encodes a snapshot of current technology/model landscape knowledge and will drift out of date as new models, tools, and best practices emerge, with no automated update mechanism.'));
children.push(bullet('Confidence ratings reflect how much matching signal was detected, not an externally validated probability of correctness — a "High confidence" pick is high-confidence in the sense that strong signal supports it, not that it has been checked against ground truth.'));
children.push(bullet('The docs/use-case-knowledge-base/ corpus is written for RAG retrieval but has only been tested against a local TF-IDF prototype (lexical similarity), not the real embedding-based retrieval /api/refine/ask now use in production — 18/21 eval cases passed against that prototype, with one concrete finding (keyword-dense "Signals/triggers" chunks out-ranking substantive content chunks) already fed back into the ingestion guide. See docs/use-case-knowledge-base/RETRIEVAL-EVAL-SET.md.'));
children.push(bullet('RESOLVED (later session): backend/app/rule_engine.py (Python) previously carried the detection *signals* for Huawei Cloud and Hybrid Connectivity without replicating the vendor-specific pick-logic branches those signals feed into on the frontend — logged here as a deliberate scope boundary on the premise that nothing exercised rule_engine.py\'s picks from a live request path. That premise did not hold: recommend_stack() is the live path behind /api/refine, /api/ask and the recommend_stack MCP tool, so those three surfaces were returning two fewer categories (hybrid_connectivity, integration_guidance) than the browser did for identical input. Both pick functions are now ported, wired into recommend_stack(), and verified against the JS byte-for-byte across 24 fixtures. backend/tests/test_engine_parity.py is the standing gate: it diffs the pickX() set in index.html against rule_engine.py in both directions, so this class of gap fails CI instead of relying on being remembered and logged here.'));
children.push(bullet('Python\'s strong_on_prem keyword list (rule_engine.py) is missing "own server(s)"/"in-house server(s)", which index.html\'s detectSignals() already has (added there after a documented live-test finding). Found while building Hybrid Connectivity, not fixed — out of scope for that change, flagged here so it is not lost.'));

// ---------- Open questions ----------
children.push(h1('13. Open Questions'));
children.push(numbered('RESOLVED (v1.4): Target segment commitment — committed direction is Segment 2 (Tech Leads & Staff Architects at scaling startups/SMBs) as the primary ICP, with Segment 1 (solo founders) as the frictionless on-ramp. This is a committed direction, not yet confirmed by usage — the existing Segment Concentration metric in Section 10 / BRD Section 7 is specifically what will validate or overturn this hypothesis.', 0, 'numbered-list-2'));
children.push(numbered('RESOLVED (v1.1): a directional monthly cost estimator was added — compute/database/LLM-API bands by scale tier, with LLM cost broken out by model tier specifically. Deliberately a range, not a point estimate, and explicitly caveated as a planning figure, not a quote, since a client-side tool has no live pricing API. See docs/use-case-knowledge-base/09-cost-estimation-methodology.md for full sourcing.', 0, 'numbered-list-2'));
children.push(numbered('RESOLVED (v1.4): Telemetry & privacy policy (NFR-1) — never transmit free-text inputs, diagram payloads, or entity names. If telemetry is ever built, it must be strictly opt-in and restricted to anonymous categorical event counts (e.g. export format clicked, diagram format uploaded). No receiving backend endpoint or telemetry infrastructure exists today, and this policy decision does not constitute a commitment to build one.', 0, 'numbered-list-2'));
children.push(numbered('RESOLVED (v1.4): Rule-engine feedback mechanism — adopt a low-overhead "Disagree with pick → Open GitHub Issue / Copy Markdown" workflow that formats the active signal, rule ID, and pick rationale. Known limitation: requiring a GitHub issue is real friction for a mid-review staff engineer, so conversion is expected to be low — a clean zero-backend starting point, not a claim of high adoption.', 0, 'numbered-list-2'));
children.push(numbered('RESOLVED (v1.4): Flow View formalization — formalized as FR-31a in Section 7.7, cross-referenced against the existing v1.5 Release Plan entry rather than treated as newly discovered.', 0, 'numbered-list-2'));

const doc = baseDoc({
  sections: [standardPage(children, 'Product Requirements Document')],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(path.join(__dirname, 'AI-Stack-Advisor-PRD.docx'), buf);
  console.log('PRD written');
});
