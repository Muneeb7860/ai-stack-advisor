# Walkthrough — Hexagonal Architecture Refactor & Invariant Contracts

## Problem addressed

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

## Architecture

### 1. Hexagon core: `buildCanonicalArchitectureGraph(ctx)`

[`index.html`](../index.html) — domain core, pure function of `ctx`:

- Zero browser globals (`document`, `window`, `fetch`), zero file-format
  strings, zero pixel layout coordinates (`x`, `y`).
- Produces `{ nodes, edges }` where every node carries
  `{ id, cat, title, sub, conf, why, persona, detail }` across 6 semantic
  tiers (`client`, `edge`, `compute`, `data`, `ai`, `ops`).
- Dynamic topology: RAG (`rag`) and Vector DB (`vectordb`) nodes/edges appear
  only when the recommendation calls for them — 18–20 nodes depending on
  signals, not a fixed count.

### 2. Presentation adapter: `layoutFlowGraph(graph)`

Decorates the canonical graph with pixel positions (`x`, `y`) and theme
colors (`FLOW_CATS[cat].color`) exclusively for the Flow View canvas —
layout is a rendering concern, not a domain one. `buildFlowGraph(ctx)` is now
a one-line composition: `layoutFlowGraph(buildCanonicalArchitectureGraph(ctx))`.

### 3. Outbound adapters

`generateMermaidDiagram`, `generateDrawioXml`, `generateSvgDiagram` all build
off `buildCanonicalArchitectureGraph(rec)` and a shared `TIER_STYLE` /
`EDGE_LABELS` table, instead of each re-deriving their own subset:

- **Mermaid** — 6 tier subgraphs (`clientTier` … `opsTier`), full node set,
  labeled edges.
- **Draw.io** — multi-column `mxGraphModel` XML, one column per tier, real
  edges from `graph.edges` (previously a single linear chain).
- **SVG** — tier-labeled stacked cards for every node (previously 5 fixed
  categories).

## Verification — two layers

There's no JS test runner in this project (`AGENTS.md` forbids adding a
build step), so [`backend/tests/test_architecture_contracts.py`](../backend/tests/test_architecture_contracts.py)
covers this with two distinct layers. Keeping them named separately matters —
an earlier draft of this doc described the static layer's coverage in terms
that actually only applied once the runtime layer existed, and that gap is
worth remembering, not just fixing quietly.

### Layer A — static contract checks (8 tests, always run)

Read `index.html` as text; assert:

1. `buildCanonicalArchitectureGraph` exists.
2. Its body contains no `document.`/`window.`/`fetch(`/`localStorage`/`sessionStorage`, and no file-format strings (`mxGraphModel`, `graph TD`, `<svg`, `.drawio`, `.mmd`).
3. Its body embeds no `x`/`y`/`color` — layout stays out of the domain core.
4. `layoutFlowGraph` exists and its body assigns `x`/`y`.
5–7. Each of `generateMermaidDiagram` / `generateDrawioXml` / `generateSvgDiagram` calls `buildCanonicalArchitectureGraph(` in its body.
8. `buildFlowGraph` delegates to `layoutFlowGraph(buildCanonicalArchitectureGraph(ctx))`.

These are cheap regex/text checks. They catch drift (an adapter reverting to
its own ad-hoc extraction) but **cannot** catch a function that calls
`buildCanonicalArchitectureGraph(` and still produces broken output — they
never execute the JavaScript.

### Layer B — runtime execution checks (5 tests, skipped without Node)

Extract the main inline `<script>` block from `index.html`, evaluate it in
Node against a minimal `document`/`window`/`fetch` stub, run a real fintech
fraud-detection scenario through the actual pipeline, and check real output:

1. `buildCanonicalArchitectureGraph` produces 18–20 nodes, every node has the
   complete `{id, cat, title, sub, conf, why, persona, detail}` field set.
2. `layoutFlowGraph` attaches numeric `x`/`y` and a string `color` to every
   node.
3. `generateDrawioXml` output parses cleanly via `xml.etree.ElementTree`.
4. `generateSvgDiagram` output parses cleanly via `xml.etree.ElementTree`.
5. `generateMermaidDiagram` output contains all 6 tier subgraphs and at
   least one `-->` edge.

Guarded with `@pytest.mark.skipif(shutil.which("node") is None, ...)` so the
pure-Python baseline (`cd backend && pytest`) still passes on a machine
without Node — they skip cleanly rather than failing on `FileNotFoundError`.
Confirmed by running the suite with `PATH` stripped of `node`: 8 passed, 5
skipped, zero errors.

## Results

- `cd backend && pytest` (full suite): **112 passed, 1 xfailed by design**
  (was 99 + 1 xfailed before this refactor; +13 net new tests, zero
  regressions across either round of changes).
- `test_architecture_contracts.py` alone: 13/13 pass with Node present; 8/13
  pass + 5 skip with Node absent.
- JS syntax check across all inline `<script>` blocks: clean parse.
- In-browser end-to-end (fintech fraud-detection scenario): Flow View
  renders 20 nodes / 18 edges, visually identical to pre-refactor; Mermaid
  export now carries all 6 tier subgraphs (was 8 fixed nodes, no tiers);
  Draw.io and SVG exports both parse and carry the full topology (were 8 and
  5 fixed categories respectively).
