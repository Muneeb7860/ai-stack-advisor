# Walkthrough — Hexagonal Architecture Refactor & Invariant Contracts

## Problem Addressed

`buildFlowGraph()` rendered a rich 18–20 node graph for Flow View, while
`generateMermaidDiagram`, `generateDrawioXml`, and `generateSvgDiagram` each
independently re-derived a reduced 5–8 node subset from `rec.*` fields via
`getPickVal`. There was no single domain model of the architecture — four
serializers, four different (and inconsistent) views of "the stack."

Precedent: this follows the same Ports & Adapters shape already enforced in
[`Swish_App`](file:///Users/muneeb/Documents/GitHub/Swish_App)'s
`ch.swissqcommerce.backend.domain.<context>.{core,port,adapter}` package
structure and its `HexagonalArchitectureTest.java`. The literal package tree
doesn't transplant here — `ai-stack-advisor`'s invariant per `AGENTS.md` is a
single-file, frameworkless `index.html` (no build step, no TypeScript) — so
the same core/port/adapter separation is expressed as plain functions in one
file instead of a Java package tree.

---

## Architecture Components

### 1. Hexagon Core: `buildCanonicalArchitectureGraph(ctx, signals = {})`

[`index.html`](../index.html) — domain core, pure function of `ctx` and `signals`:

- Zero browser globals (`document`, `window`, `fetch`), zero file-format
  strings, zero pixel layout coordinates (`x`, `y`).
- Produces `{ nodes, edges }` where every node carries
  `{ id, cat, title, sub, conf, why, persona, detail, opportunities }` across 6 semantic
  tiers (`client`, `edge`, `compute`, `data`, `ai`, `ops`).
- Dynamic topology: RAG (`rag`) and Vector DB (`vectordb`) nodes/edges appear
  only when the recommendation calls for them — 18–20 nodes depending on
  signals, not a fixed count.

### 2. AI Opportunity & Leverage Points Layer

- Pure 12-pattern opportunity catalog (`CATALOG_AI_OPPORTUNITIES`) across 6 tiers.
- Compliance guardrails: suppresses direct text-to-SQL on raw databases when regulated/compliance flags are active unless strict read-only/PII isolation prerequisites are met.

### 3. Presentation & Outbound Adapters

- **`layoutFlowGraph(graph)`**: Decorates canonical graph with pixel positions (`x`, `y`) and theme colors.
- **`generateMermaidDiagram`**: 6 tier subgraphs (`clientTier` … `opsTier`), full node set, labeled edges.
- **`generateDrawioXml`**: Multi-column `mxGraphModel` XML, one column per tier, real edges from `graph.edges`.
- **`generateSvgDiagram`**: Tier-labeled stacked cards for every node.

### 4. Knowledge Base & Technology Catalog Single Source of Truth

- `#stackKbData.technologies` inside [`index.html`](../index.html) is the single canonical source of truth for all 225 technologies, with `signal_keywords: string[]` on every entry.
- Missing observability/quality tools (`dynatrace`, `datadog`, `splunk`, `newrelic`, `elasticsearch`/`elk`, `grafana`, `sonarqube`, `jprofiler`, `visualvm`) added with complete schemas.
- Maintainer authoring tool [`scripts/add_tech.py`](../scripts/add_tech.py) validates required schema fields, enums, rings, and duplicates.
- Client-side `localStorage` overlay (`getCustomKbTechs()`, `saveCustomKbTech()`) with GitHub Issue suggestion generator.

---

## Verification & Test Results

### 1. Dedicated Contract & Invariant Suites
- **`backend/tests/test_kb_schema.py`**: **7/7 passed** (schema completeness, duplicates check, alternatives reference integrity, Node.js runtime signal detection, localStorage custom overlay, Python signal parity).
- **`backend/tests/test_add_tech_script.py`**: **12/12 passed** (schema validation rules, ring checks, duplicate prevention).
- **`backend/tests/test_architecture_contracts.py`**: **16/16 passed** (static AST invariants, Node.js runtime execution, opportunity attachment, compliance guardrails).

### 2. Full Backend Pytest Breakdown (`backend/`)
- Running `pytest` on the entire backend test suite yields **112 passed, 1 xpassed, 22 failed**.
- The 22 failures are in `test_retrieval_eval.py` and `test_ask.py`/`test_refine.py` grounding tests, caused by the local Ollama / `nomic-embed-text` daemon being stopped.
- Running pure unit & architecture contract tests (`pytest --ignore=tests/test_retrieval_eval.py -k "not test_build_grounding_context"`): **107 passed, 4 deselected, 0 failed**.
