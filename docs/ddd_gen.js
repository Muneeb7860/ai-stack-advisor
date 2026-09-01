const fs = require('fs');
const path = require('path');
const {
  Packer, Paragraph, TextRun, AlignmentType, ImageRun,
  NAVY, ACCENT, LIGHT, MUTED, GOOD, WARN,
  h1, h2, h3, p, pRuns, bullet, bulletBold, numbered, reqTable,
  pageBreak, hr, coverTitle, baseDoc, standardPage,
} = require('./helpers');

const children = [];

// ---------- Cover ----------
children.push(...coverTitle(
  'Domain-Driven Design Document',
  'Bounded contexts, ubiquitous language, and aggregates for v2',
  [
    ['Document Version', '1.4'],
    ['Status', 'Implemented — all v2 contexts (Analysis, Refinement, Sharing, Integration) built and tested, including RAG grounding for the Refinement Context'],
    ['Prepared by', 'Muneeb, with Claude (Cowork)'],
    ['Date', new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })],
    ['Companion documents', 'BRD, PRD, v2 Design Doc, ERD, Architecture Diagram'],
  ]
));

// ---------- Scope note ----------
children.push(h1('1. Scope & Why This Document Exists Now'));
children.push(p('DDD is normally most valuable once you\'re committed to building service boundaries — defining bounded contexts for a system that doesn\'t exist yet risks being speculative. This document exists as a deliberate exception: v2\'s scope is already fully specified (LLM refinement, share-link persistence, MCP tool exposure — see the PRD\'s FR-27 through FR-29 and the v2 Design Document), so the domain boundaries below are derived from committed requirements, not from anticipated ones. Nothing here should be read as scope expansion; it is a way of organizing work that has already been scoped.'));
children.push(p('v1 (the client-side rule engine) is intentionally not modeled here as a "context" in the DDD sense — it has no persistence, no state, and no service boundary to speak of. It is the Analysis Context\'s core logic, reused rather than re-implemented, as shown in the Context Map below.', { italics: true, color: MUTED, size: 19 }));

// ---------- Ubiquitous language ----------
children.push(h1('2. Ubiquitous Language'));
children.push(p('Terms used consistently across code, documentation, and conversation about this system. Several of these already exist in the PRD/BRD; they are repeated here because a glossary is only useful where every context can see the same one.'));
children.push(reqTable(
  ['Term', 'Definition'],
  [2200, 6400],
  [
    ['Signal', 'A boolean or derived fact detected in a user\'s free-text requirement (e.g. "compliance", "onPrem", "highScale") — the atomic unit of input to the rule engine.'],
    ['Recommendation', 'A single category\'s output: a pick, a rationale ("why"), and a confidence rating. Fifteen-plus categories combine to form a full Analysis.'],
    ['Confidence', 'High / Medium / Low — how much detected signal supports a given recommendation, not a validated probability of correctness (see PRD Section 12).'],
    ['Trade-off', 'A head-to-head recommendation between two or more named alternatives, always paired with an explicit "switch when" condition.'],
    ['Analysis', 'The aggregate: one requirement text plus its full set of recommendations across all categories. The unit of persistence and sharing in v2.'],
    ['Refinement', 'An LLM-assisted second pass over an Analysis that may adjust specific picks, each adjustment carrying a cited reason back to the original text.'],
    ['Share link', 'A URL exposing one Analysis without requiring an account — the only access-control mechanism in this system by design (see ERD, "Deliberately Excluded").'],
    ['MCP invocation', 'A call to the recommend_stack() tool from an external MCP client (e.g. Claude Desktop), logged independently of whether a user ever views the resulting Analysis in the web app.'],
    ['Architect role / persona', 'One of six professional perspectives (Enterprise, Solution, Application, or AI Architect; TPM; SDE) tagged against each stack recommendation to indicate who would typically own that decision.'],
  ]
));

// ---------- Context map ----------
children.push(h1('3. Context Map'));
children.push(p('One core domain, two supporting subdomains, and one generic subdomain. The relationships below use standard DDD context-mapping patterns (Customer/Supplier, Conformist, Anti-Corruption Layer).'));

const imgBuf = fs.readFileSync(path.join(__dirname, 'img', 'context-map.png'));
children.push(new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 120, after: 200 },
  children: [new ImageRun({ type: 'png', data: imgBuf, transformation: { width: 620, height: 110 } })],
}));

children.push(h3('3.1 Analysis Context — Core Domain'));
children.push(p('Owns the entire "requirement text in, recommendation out" logic — this is the reason the product exists, and it is exactly the v1 rule engine (detectSignals() plus the 45 pickX() functions, up from ~30 after a two-round dimension-expansion pass), unchanged, reused rather than reimplemented behind a service boundary. Upstream of both supporting subdomains. A new adjacent asset — docs/use-case-knowledge-base/, a 12-file corpus written as RAG grounding content, not application code — is not itself part of this bounded context\'s runtime, but /api/refine and /api/ask (in the Refinement subdomain below) retrieve from it via app/retrieval.py, so its retrieval contract (00-INDEX-AND-INGESTION-GUIDE.md) is effectively a dependency of that subdomain.'));
children.push(h3('3.2 Refinement Context — Supporting Subdomain'));
children.push(p('Owns the LLM-assisted second pass. Downstream of Analysis Context in a Customer/Supplier relationship — it consumes Analysis Context\'s output as its input and cannot override its structure, only annotate/adjust specific picks with cited reasons. Talks to the Anthropic API through an Anti-Corruption Layer, so a future change of LLM provider does not leak provider-specific concepts (message formats, tool-call schemas) into this context\'s own model.'));
children.push(h3('3.3 Sharing Context — Supporting Subdomain'));
children.push(p('Owns persistence and share-link issuance. Also downstream of Analysis Context (Customer/Supplier) — it stores Analysis snapshots but has no opinion on how a recommendation was derived. Deliberately excludes any notion of user accounts or ownership (see ERD "Deliberately Excluded"), keeping this context as thin as the actual v2 scope requires.'));
children.push(h3('3.4 Integration Context — Generic Subdomain'));
children.push(p('The MCP tool wrapper. A Conformist relationship to Analysis Context — it adapts an external protocol (MCP) onto Analysis Context\'s existing public model without asking Analysis Context to change anything for its benefit. This is intentionally the thinnest context in the system: a translation layer, not a source of business rules.'));

// ---------- Aggregates ----------
children.push(h1('4. Aggregates & Entities'));
children.push(p('One aggregate root per bounded context that has persistence (Analysis Context\'s logic is stateless in v1 and gains persistence only via the Sharing Context in v2). Full field-level detail is in the companion ERD; this section states the invariants and boundaries, which the ERD does not.'));

children.push(h2('4.1 Analysis (aggregate root — spans Analysis + Sharing contexts once persisted)'));
children.push(bulletBold('Invariant: ', 'an Analysis, once created, has an immutable requirement_text and signals snapshot — the rule engine\'s output at the moment of analysis is preserved even if the engine itself later changes. Re-running the same text after an engine update produces a new Analysis, never a mutation of the old one.'));
children.push(bulletBold('Invariant: ', 'share_slug is optional and one-directional — sharing can be turned on, but the ERD makes no provision for un-sharing (revoking a slug) because that was never a stated v2 requirement. If added later, this invariant needs revisiting.'));
children.push(bulletBold('Boundary: ', 'Analysis does not know about RefinementResult or ConversationMessage internally — those are separate aggregates that reference an Analysis by id, not children owned by it. This keeps the core Analysis Context\'s model uncontaminated by Refinement Context\'s concerns, consistent with the Customer/Supplier relationship in Section 3.2.'));

children.push(h2('4.2 RefinementResult (aggregate root — Refinement Context)'));
children.push(bulletBold('Invariant: ', 'append-only. A new refinement pass never overwrites a prior RefinementResult — this is what makes "disagreement rate" (BRD Section 7 success metric) measurable later: the history of what the LLM changed, and whether the user accepted it, is preserved rather than lost on the next click.'));
children.push(bulletBold('Boundary: ', 'RefinementResult references an analysis_id but does not reach back into Analysis to mutate its recommendations — the web app decides, at render time, whether to show the original or the refined view. This keeps "what the rule engine said" and "what the LLM suggested changing" as two honestly separate facts rather than merging them into one ambiguous record.'));

children.push(h2('4.3 ConversationMessage (aggregate root — Refinement Context)'));
children.push(bulletBold('Invariant: ', 'every message belongs to exactly one Analysis and is never shared across analyses — per the v2 Design Document, the /api/ask system prompt is deliberately restricted to reasoning about the existing recommendation, not re-deriving a new one, and the data model enforces that scoping structurally, not just via prompt instructions.'));

children.push(h2('4.4 McpInvocation (aggregate root — Integration Context)'));
children.push(bulletBold('Invariant: ', 'exists independently of whether the resulting Analysis is ever persisted or viewed in the web app — an MCP-originated call is a first-class usage path, not a side effect of the web app\'s existence. This is why analysis_id is nullable: the invocation is logged the instant the tool is called, before the Analysis Context has necessarily run to completion.'));

children.push(h2('4.5 Disagreement (aggregate root — Refinement Context)'));
children.push(p('Added later session for the "Challenge This Pick" widget (PRD FR-44) — the first real instrumentation for BRD Section 7\'s disagreement-rate metric. Placed in the Refinement Context, not a new context of its own: both RefinementResult and Disagreement are "a second opinion on a pick," one from an LLM and one from a human, so they share a bounded context rather than inventing a fourth.', { italics: true, color: MUTED, size: 19 }));
children.push(bulletBold('Invariant: ', 'append-only, same rationale as RefinementResult (Section 4.2) — a disagreement is a fact about a moment; editing it later would corrupt the rate calculation, not just the record. No update/delete route exists.'));
children.push(bulletBold('Boundary: ', 'references an analysis_id but is not a child Analysis owns internally, matching every other aggregate\'s relationship to Analysis in this document. Requires the referenced Analysis to already exist server-side — the client never creates an Analysis row purely to log a disagreement about it; a disagreement about an Analysis that was never persisted stays client-side-only (localStorage), consistent with NFR-1.'));

children.push(h2('4.6 HarnessFeedback (aggregate root — its own context)'));
children.push(p('Added for the Harness Readiness feedback capture (PRD FR-57). The only aggregate in this document with NO relationship to Analysis, deliberately: a harness self-audit scores a team\'s own development process, which is not a product requirement, so there is no Analysis for it to reference and none should be created to give it one. Forcing an Analysis row into existence purely to hang this off would corrupt the meaning of that table and every metric derived from it.', { italics: true, color: MUTED, size: 19 }));
children.push(bulletBold('Invariant: ', 'append-only, same rationale as RefinementResult (4.2) and Disagreement (4.5) — feedback is a fact about a moment. No update/delete route exists.'));
children.push(bulletBold('Invariant: ', 'carries the audit score and per-component answers alongside the comment. The comment is close to unreadable without them — the same words from a team scoring 14/15 and one scoring 2/15 mean different things — so they are part of the aggregate rather than a separate lookup.'));
children.push(bulletBold('Boundary: ', 'no foreign key at all, unlike every other aggregate here. The closest precedent is McpInvocation (4.4), whose analysis_id is nullable for a related reason — a record that is legitimately created before, or entirely without, an Analysis.'));
children.push(bulletBold('Note: ', 'written only on an explicit user action, never as background telemetry, and best-effort — an unreachable backend degrades to a thank-you rather than an error, consistent with NFR-5.'));

// ---------- Domain events ----------
children.push(h1('5. Domain Events'));
children.push(p('Named for a future event-driven implementation, though v2 as designed is a simple synchronous request/response system — these are documented now so that if the system later needs to react to its own state changes (e.g. triggering an eval run per BRD\'s open questions), the vocabulary already exists.'));
children.push(reqTable(
  ['Event', 'Raised by', 'Meaning'],
  [2600, 2200, 4200],
  [
    ['AnalysisCreated', 'Analysis Context', 'A requirement was analyzed and a full recommendation set produced (client-side in v1, or on first backend persistence in v2)'],
    ['AnalysisShared', 'Sharing Context', 'A share_slug was issued for an existing Analysis'],
    ['RefinementRequested', 'Refinement Context', 'A user clicked "Refine with AI" on an Analysis'],
    ['RefinementCompleted', 'Refinement Context', 'The LLM returned adjusted picks, a rationale, and any open questions'],
    ['FollowUpAsked', 'Refinement Context', 'A user submitted a question scoped to an existing Analysis'],
    ['McpToolInvoked', 'Integration Context', 'An external MCP client called recommend_stack()'],
    ['DisagreementLogged', 'Refinement Context', 'A user stated a preferred alternative to a specific pick and why, on an Analysis that already exists server-side'],
    ['HarnessFeedbackSubmitted', 'Harness Feedback Context', 'A user rated a completed harness self-audit, with the score and per-component answers that produced it'],
  ]
));

// ---------- What this doc deliberately does not do ----------
children.push(h1('6. What This Document Deliberately Does Not Do'));
children.push(bullet('Does not specify a message bus, event store, or async infrastructure — v2 as designed is synchronous request/response; Section 5\'s events are vocabulary, not an architecture commitment.'));
children.push(bullet('Does not model v1 as a bounded context — it has no persistence and is reused as a library, not re-implemented as a service (Section 1).'));
children.push(bullet('Does not introduce a Users/Accounts/Identity context — consistent with the ERD\'s "Deliberately Excluded" section and the PRD\'s non-goals; if accounts are ever added, that is a genuinely new bounded context, not an extension of Sharing Context.'));
children.push(bullet('Does not attempt to model the rule engine\'s internal categories (cloud, database, RAG, etc.) as domain concepts — those are Analysis Context\'s implementation detail, not something Refinement, Sharing, or Integration contexts need to understand structurally, only pass through as opaque JSON (see ERD, jsonb fields).'));

const doc = baseDoc({
  sections: [standardPage(children, 'Domain-Driven Design Document')],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(path.join(__dirname, 'AI-Stack-Advisor-DDD.docx'), buf);
  console.log('DDD written');
});
