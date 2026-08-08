const fs = require('fs');
const path = require('path');
const {
  Packer, Paragraph, TextRun, AlignmentType, TableOfContents,
  NAVY, ACCENT, LIGHT, MUTED, GOOD, WARN,
  h1, h2, h3, p, pRuns, bullet, bulletBold, numbered, reqTable,
  pageBreak, hr, coverTitle, baseDoc, standardPage,
} = require('./helpers');

const children = [];

// ---------- Cover ----------
children.push(...coverTitle(
  'Business Requirements Document',
  'Rule-based multi-role architecture advisor',
  [
    ['Document Version', '1.1'],
    ['Status', 'Draft — for internal review (v2 backend now shipped; see Section 8.2 and Section 12)'],
    ['Prepared by', 'Muneeb, with Claude (Cowork)'],
    ['Date', new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })],
    ['Classification', 'Internal'],
  ]
));

// ---------- Document control ----------
children.push(h1('1. Document Control'));
children.push(h2('1.1 Revision History'));
children.push(reqTable(
  ['Version', 'Date', 'Author', 'Summary of Changes'],
  [1400, 1800, 2400, 4400],
  [
    ['0.1', 'Session start', 'Muneeb / Claude', 'Initial concept: rule-based tool to recommend AI/tech stack from business requirements'],
    ['0.5', 'Same session', 'Muneeb / Claude', 'Expanded to full architecture advisor: cost, throughput, governance, AI serving layer, trade-off decisions'],
    ['1.0', 'Same session', 'Muneeb / Claude', 'This BRD formalizes the business case for the product built and validated to date'],
    ['1.1', 'Later session', 'Muneeb / Claude', 'v2 backend built and tested (share links, /api/refine, /api/ask, MCP tool wrapper). Updated BR-9 and the roadmap (Section 12) to reflect shipped status; BR-7/BR-8 remain not met — no functional requirement content changed otherwise.'],
  ]
));
children.push(h2('1.2 Related Documents'));
children.push(bullet('Product Requirements Document (PRD) — companion document, functional/technical detail'));
children.push(bullet('Market Analysis — competitive landscape and PMF assessment'));
children.push(bullet('v2 Design Document — backend architecture for the LLM-refinement layer, persistence, and MCP tool'));
children.push(bullet('Validation Report — bugs found and fixed during the pre-launch QA pass'));

// ---------- Executive summary ----------
children.push(h1('2. Executive Summary'));
children.push(p('AI Stack Advisor is a browser-based tool that takes a plain-language description of a business or product requirement and returns a complete, defensible technology and AI architecture recommendation — spanning cloud infrastructure, application architecture, AI/LLM strategy, and engineering governance. It is built to answer the question a founder, architect, or engineering lead asks at the start of nearly every new initiative: "what should we actually build this on?"'));
children.push(p('The current version (v1) runs entirely client-side as a transparent, auditable rule engine — every recommendation traces to a specific keyword or combination of signals detected in the user\'s input, each carries a confidence rating, and every "trade-off" decision (single-cloud vs. multi-cloud, Kafka vs. managed queue, Kubernetes vs. serverless, and others) states not just what to choose but why, and the specific condition under which the recommendation should change.'));
children.push(p('A competitive scan found three near-identical tools in market (StackAdvisor.ai, TechStacker, Stack Studio), none with a settled leader or finished pricing, inside a developer-tooling category growing at roughly 37% CAGR. This tool\'s differentiation is depth: none of the three competitors cover AI-native decisions — LLM provider/size selection, RAG architecture, model hosting topology, guardrail placement — that this tool treats as first-class categories, and none use a transparent, confidence-scored rule engine in place of an opaque LLM-generated answer.'));
children.push(pRuns([
  new TextRun({ text: 'Current status: ', bold: true, size: 21 }),
  new TextRun({ text: 'v1 is built, tested against 11 scenarios (5 built-in + 6 validation cases), and has had 3 real logic bugs found and fixed through a structured QA pass. It has not yet been used by anyone outside this project — product-market fit is not established, and the recommended next step is user validation before further scope expansion.', size: 21 }),
]));

// ---------- Business problem ----------
children.push(h1('3. Business Problem / Opportunity'));
children.push(h2('3.1 Problem Statement'));
children.push(p('Choosing a technology and AI architecture for a new product is a high-stakes, low-frequency decision that most teams are not well equipped to make quickly. It requires synthesizing the perspectives of several specialist roles — Solution Architect, Enterprise Architect, Application Architect, AI Architect, TPM, and senior SDE — that a small team or an individual founder rarely has simultaneous access to. The cost of getting it wrong compounds: a poorly chosen database, an over-engineered microservices split for a 3-person team, or an unnecessary Kafka cluster all show up months later as expensive rework.'));
children.push(p('This problem has gotten more acute, not less, with the rise of AI-native products: teams now also have to decide LLM provider and size, RAG architecture (one of at least 14 named variants), model hosting location, guardrail placement, and MCP-vs-API integration strategy — decisions that didn\'t exist three years ago and that most general "pick your tech stack" advice doesn\'t cover at all.'));
children.push(h2('3.2 Market Opportunity'));
children.push(bulletBold('Category growth: ', 'the AI code generation and developer assistant market is valued at $16.13B in 2026, projected to reach $78.97B by 2031 (37.39% CAGR) — the architecture-advisor niche this product occupies is a small slice of that, but growing with it.'));
children.push(bulletBold('Low competitive intensity: ', 'three direct competitors identified (StackAdvisor.ai, TechStacker, Stack Studio); none has a finished pricing page, none has visible traction signals, and none covers AI-native stack decisions with the depth this product does.'));
children.push(bulletBold('Timing: ', 'better to establish a position now, while barriers to entry are still low and no category leader has emerged, than after the space consolidates.'));
children.push(h2('3.3 Differentiation'));
children.push(reqTable(
  ['Dimension', 'Competitors (StackAdvisor.ai / TechStacker / Stack Studio)', 'AI Stack Advisor'],
  [2200, 3600, 3200],
  [
    ['AI-native coverage', 'None — general web/cloud stack only', 'LLM provider/size, RAG type, hosting, guardrails, MCP'],
    ['Recommendation logic', 'Opaque LLM-generated output', 'Transparent rule engine with per-pick confidence rating'],
    ['Trade-off reasoning', 'Single recommendation, no rationale depth', 'Explicit "why" + "switch when" for every major decision'],
    ['Cost to run', 'LLM inference cost per analysis', 'Zero — fully client-side, no API calls'],
    ['Governance output', 'Not offered', 'KRA / KPI / SLA / reliability targets included'],
  ]
));

// ---------- Objectives ----------
children.push(h1('4. Business Objectives'));
children.push(p('These are the outcomes this product is intended to produce. They are intentionally framed as directional goals rather than committed targets, since v1 has not yet been exposed to real users — see Section 9 for the assumptions this depends on.'));
children.push(numbered('Give a technical founder or architect a defensible first-draft architecture in minutes instead of days, covering both traditional infrastructure and AI-native decisions in one pass.'));
children.push(numbered('Establish a credible position in the emerging "AI-native architecture advisor" niche before the space consolidates around 1–2 dominant players.'));
children.push(numbered('Validate, through real usage, whether the rule-based transparent-reasoning approach is preferred over the opaque LLM-generation approach competitors use.'));
children.push(numbered('Build a foundation (documented in the v2 design doc) that can extend to an LLM-refinement layer, persistence, and MCP-tool distribution without re-architecting the core recommendation engine.'));

// ---------- Target market ----------
children.push(h1('5. Target Users / Market Segments'));
children.push(p('Three segments were identified from competitor positioning; each competitor chose a different one, and this product has not yet committed to a single primary segment — that decision is called out as an open business requirement in Section 7.'));
children.push(reqTable(
  ['Segment', 'Profile', 'Primary need'],
  [2000, 4200, 2800],
  [
    ['Non-technical founder', 'Early-stage, no in-house architect, needs hand-holding', 'Confidence + cost estimation + plain-language rationale'],
    ['Developer / technical founder', 'Can evaluate trade-offs, wants depth over hand-holding', 'Comprehensive coverage, transparent reasoning, "why/when"'],
    ['Enterprise architect / TPM', 'Operating inside an existing org, needs governance artifacts', 'KRA/KPI/SLA output, ADR/C4/HLD/LLD documentation prompts'],
  ]
));

// ---------- Business requirements ----------
children.push(h1('6. Business Requirements'));
children.push(p('Numbered at the business level (not functional/technical — see the companion PRD for those). Each is traceable to what has been built and validated, or flagged as not yet met.'));
const brRows = [
  ['BR-1', 'The product must produce a complete architecture recommendation from a single free-text input, with no required form fields or wizard steps.', 'Met — v1'],
  ['BR-2', 'Every recommendation must state its rationale ("why") in plain language, not just the recommendation itself.', 'Met — v1'],
  ['BR-3', 'The product must differentiate from general-purpose stack advisors by treating AI-native decisions (LLM choice, RAG, hosting, guardrails, MCP) as first-class, not an afterthought.', 'Met — v1'],
  ['BR-4', 'The product must not misrepresent confidence — recommendations based on strong signal must be visually distinguishable from defaults applied in the absence of signal.', 'Met — v1 (confidence badges)'],
  ['BR-5', 'The product must run at zero marginal cost per use in its initial version, to support free/low-friction distribution while product-market fit is unproven.', 'Met — v1 is fully client-side'],
  ['BR-6', 'The product must not produce a recommendation that contradicts an explicitly stated hard constraint (e.g. recommending a public cloud when the user states no public cloud is permitted).', 'Met — fixed in validation pass; see BR-6 note below'],
  ['BR-7', 'The product must reach real external users to test demand and recommendation quality before further feature investment.', 'Not met — no external users to date'],
  ['BR-8', 'The product must define and commit to a primary target segment (see Section 5) to focus positioning and future feature investment.', 'Not met — open decision'],
  ['BR-9', 'Where a paid/backend tier is introduced (LLM refinement, persistence, MCP distribution), it must not degrade or paywall the free client-side experience that satisfies BR-5.', 'Met — v2 shipped; v1 remains fully functional with zero backend calls (PRD NFR-5)'],
];
children.push(reqTable(['ID', 'Requirement', 'Status'], [900, 6300, 1900], brRows));
children.push(p('Note on BR-6: this was not a design intention from the outset — it was a live bug discovered during validation testing (an air-gapped/no-public-cloud requirement was still returning a public-cloud recommendation). It is listed as a formal business requirement here specifically so it is regression-tested going forward, not just fixed once.', { italics: true, color: MUTED, size: 19 }));

// ---------- Success metrics ----------
children.push(h1('7. Success Metrics'));
children.push(p('No usage data exists yet (see Section 9). These are the metrics to instrument for once the product has real users, not retroactive claims about current performance.'));
children.push(reqTable(
  ['Metric', 'Definition', 'Why it matters'],
  [2400, 3600, 2600],
  [
    ['Completion rate', '% of visitors who submit a requirement and view a full result', 'Signals whether the value proposition lands before any friction'],
    ['Re-use rate', '% of users who return to run a second analysis within 30 days', 'Direct proxy for whether the tool earned a place in someone\'s workflow'],
    ['Disagreement rate', '% of sessions where a user edits/overrides a recommendation (once feedback capture exists)', 'The single most informative signal for whether the rule engine\'s judgment matches real practitioners\''],
    ['Segment concentration', 'Which of the 3 target segments (Section 5) actually uses the tool', 'Determines which segment to formally commit to (BR-8)'],
    ['Cost per active user', 'Backend LLM/infra spend ÷ active users, once v2 ships', 'Governs whether the free tier (BR-5/BR-9) remains sustainable'],
  ]
));

// ---------- Scope ----------
children.push(h1('8. Scope'));
children.push(h2('8.1 In Scope (v1 — Delivered)'));
children.push(bullet('Free-text requirement input with signal detection across 30+ business/technical dimensions'));
children.push(bullet('Full core technical stack recommendation (15 categories: cloud, gateway, IAM, languages, architecture style, compute, messaging, mesh, cache, database, containers, observability, frontend, CI/CD, DNS)'));
children.push(bullet('Explicit head-to-head trade-off decisions with "why" and "switch when" framing'));
children.push(bullet('AI/LLM strategy: model orchestration, local-vs-cloud hosting with VRAM sizing, interface topology, MCP-vs-API, RAG architecture (14-variant taxonomy), vector DB placement, guardrail pipeline placement'));
children.push(bullet('Cost/resource optimization and concurrency/throughput recommendations'));
children.push(bullet('Governance output: KRA, KPI, SLA, and reliability/continuous-improvement targets'));
children.push(bullet('Confidence scoring on every recommendation'));
children.push(bullet('Sticky navigation and collapsible sections for usability at full scope'));
children.push(h2('8.2 In Scope (v2 — Shipped)'));
children.push(bullet('LLM-powered refinement pass for ambiguous/conflicting requirements, using the user\'s own Anthropic API key — shipped as POST /api/refine'));
children.push(bullet('Share links (persistence) for completed analyses — shipped'));
children.push(bullet('MCP tool wrapper for use from inside Claude Desktop/Code — shipped, plus a grounded follow-up Q&A endpoint (POST /api/ask) added during the build'));
children.push(h2('8.3 Out of Scope'));
children.push(bullet('Provisioning or executing infrastructure changes — this is an advisory tool only, never a "terraform apply" tool'));
children.push(bullet('Multi-user accounts, team collaboration, or role-based access control'));
children.push(bullet('Formal integration with ticketing/PM tools (Jira, Linear) for tracking adoption of recommendations'));
children.push(bullet('Guaranteed accuracy against a benchmark of expert architect decisions — this has not been validated (see Section 10)'));

// ---------- Assumptions & constraints ----------
children.push(h1('9. Assumptions & Constraints'));
children.push(h3('Assumptions'));
children.push(bullet('That practitioners value transparent, auditable reasoning over a more polished but opaque LLM-generated recommendation — untested against the three direct competitors, who all chose the opaque approach.'));
children.push(bullet('That the AI-native decision categories (LLM size/provider, RAG, hosting, guardrails) are under-served enough by competitors to be a meaningful wedge — supported by the competitive scan, not by user interviews.'));
children.push(bullet('That a rule-based engine can stay accurate as the underlying technology landscape shifts (new model releases, deprecated tools) without constant manual maintenance — not yet tested over time.'));
children.push(h3('Constraints'));
children.push(bullet('v2 backend work (LLM refinement, persistence, MCP tool) required desktop/local-environment access, which a browser-only session couldn\'t provide — resolved once that access became available; see Section 12.'));
children.push(bullet('No dedicated budget, team, or timeline has been assigned to this product — it has been built opportunistically within a single working session.'));
children.push(bullet('No user research has been conducted; all target-segment and positioning statements in this document are inferred from competitor behavior, not primary research.'));

// ---------- Risks ----------
children.push(h1('10. Risks'));
children.push(reqTable(
  ['Risk', 'Likelihood', 'Impact', 'Mitigation'],
  [2600, 1200, 1200, 3600],
  [
    ['No product-market fit — the core assumption in Section 9 is wrong and users prefer opaque LLM answers', 'Medium', 'High', 'Run BR-7 (real user exposure) before further feature investment; track disagreement rate once feedback capture exists'],
    ['Rule engine drifts out of date as models/tools change (e.g. a recommended LLM size tier becomes obsolete)', 'High over time', 'Medium', 'Establish a periodic review cadence once the product has real usage to justify the maintenance cost'],
    ['Competitive space consolidates around a funded competitor before this product reaches users', 'Medium', 'Medium', 'Prioritize BR-7/BR-8 (user exposure, segment commitment) over further feature breadth'],
    ['Heuristic/keyword-matching approach produces confidently wrong recommendations on inputs it wasn\'t designed for', 'Medium', 'High', 'Ongoing validation testing (see Validation Report); every recommendation carries a confidence rating and an explicit disclaimer that this is a directional starting point, not a substitute for architecture review'],
  ]
));

// ---------- Stakeholders ----------
children.push(h1('11. Stakeholders'));
children.push(reqTable(
  ['Role', 'Stake', 'RACI'],
  [2200, 4800, 1600],
  [
    ['Product owner (Muneeb)', 'Defines direction, priorities, and go/no-go on further investment', 'Accountable'],
    ['Engineering (Claude, current session)', 'Builds and maintains the rule engine and, later, the backend', 'Responsible'],
    ['Future end users', 'Determine whether the product has value — not yet engaged', 'Consulted (pending)'],
  ]
));

// ---------- Timeline ----------
children.push(h1('12. High-Level Roadmap'));
children.push(reqTable(
  ['Phase', 'Scope', 'Status'],
  [1800, 5400, 1600],
  [
    ['v1', 'Client-side rule engine, full stack + AI-serving + governance recommendation surface', 'Shipped'],
    ['v1.1', 'QA/validation pass — negation handling, on-prem support, data-warehouse detection', 'Shipped'],
    ['v2', 'LLM refinement layer, persistence (share links), grounded follow-up Q&A, MCP tool wrapper', 'Shipped'],
    ['v3', 'Informed by real user feedback per BR-7 — scope not yet defined', 'Not started'],
  ]
));

// ---------- Approval ----------
children.push(h1('13. Approval'));
children.push(p('This document is a draft prepared for internal reference and has not been formally reviewed or signed off. Recommended next action per BR-7: expose v1 to a small number of real users before committing further engineering time against Section 12.'));
children.push(reqTable(
  ['Name', 'Role', 'Signature', 'Date'],
  [2200, 2200, 2200, 2000],
  [['Muneeb', 'Product Owner', '', ''], ['', 'Reviewer', '', '']]
));

const doc = baseDoc({
  sections: [standardPage(children, 'Business Requirements Document')],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(path.join(__dirname, 'AI-Stack-Advisor-BRD.docx'), buf);
  console.log('BRD written');
});
