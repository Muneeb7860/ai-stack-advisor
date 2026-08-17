# PRD — Diagram Import/Understanding & External Design-Tool Integration

**Status:** Draft, for review — not yet scoped into a release
**Owner:** TBD
**Relates to:** `docs/AI-Stack-Advisor-PRD.docx` (master PRD, FR-1–31). This document continues that
numbering (FR-32+) so it can be folded into the master doc later without renumbering, but is kept
standalone until the scope and phasing below are agreed — this is two distinct, non-trivial
features bundled under one request, and they deserve separate go/no-go decisions per sub-feature,
not one blanket yes.

---

## 1. Problem statement

Today the tool only accepts free text (typed or wizard-synthesized). Two real gaps follow from that:

1. **Nobody starts from zero.** Most teams asking "what should our architecture look like" already
   have *something* drawn — a UML export, a draw.io sketch, a whiteboard photo, an old Visio diagram.
   Forcing them to re-describe it in prose loses information (the diagram *is* the source of truth)
   and adds friction (why type out what's already drawn?).
2. **The output lives nowhere else.** Recommendations render as HTML cards and an ADR export. If a
   team's actual working tool is Figma, draw.io, or Eraser, the recommendation has to be manually
   redrawn there — the tool's output dead-ends instead of joining the team's real workflow.

Both gaps point at the same underlying need: **diagrams in, diagrams out**, not just prose in,
prose out.

---

## 2. Goals

- Let a user upload an existing architecture diagram and have it treated as a real input — same
  quality bar as free text: every extracted element traceable, confidence-rated, never asserted
  past what was actually detected.
- Let the tool produce a *diff*, not just a fresh opinion: "here's what you have, here's what we'd
  change, here's why" — reusing the existing rule engine/KB/confidence-basis system, not forking a
  parallel one.
- Let the resulting recommendation leave the tool in a format a real design tool can open, not just
  as an HTML page.

## 3. Non-goals

- **Not building a general-purpose diagramming editor.** No freeform drawing canvas inside this
  app. Understanding and export, not authoring.
- **Not guaranteeing pixel-perfect reproduction** of an uploaded diagram's exact visual style —
  the output is a regenerated, opinionated diagram reflecting recommendations, not a lossless copy.
- **Not real-time bidirectional sync** with any external tool (no "live" Figma/draw.io connection
  that stays in sync as either side changes). One-shot import, one-shot export, v1 of this feature.
- **Not every tool in the request gets equal treatment.** See §5 — two of the six named tools
  (Canva, Sketch) don't have a technical path that fits this product without a fundamentally
  different integration model. Flagging that now, not after building toward it.

---

## 4. Feature 1 — Diagram import, understanding, suggestion, export

### 4.1 User stories

- As a user with an existing draw.io/Lucidchart export, I want to upload it and have the tool
  recognize what's already there (cloud provider, database, major components) so I don't have to
  re-describe my own architecture in prose.
- As a user with only a screenshot of a whiteboard sketch, I want the tool to make a best effort at
  reading it, clearly flagged as lower-confidence than a structured file.
- As a user reviewing the tool's suggestions, I want to see *my diagram* next to *the recommended
  changes*, not just a fresh unrelated recommendation.
- As a user, I want to download the resulting diagram in a format I can actually keep using.

### 4.2 The format question is the whole feature — tiered by reliability, not treated as one input type

"UML images or standard image formats like PNG & SVG" bundles two very different problems:

| Tier | Formats | How understanding works | Reliability |
|---|---|---|---|
| **A — Structured/machine-readable** | SVG with real element structure (not a flattened raster-in-SVG-wrapper), draw.io/diagrams.net `.drawio` XML, Mermaid text, PlantUML text | Deterministic parsing — read the actual shape/label/connection data, no guessing | High — same confidence tier as `stated` in the existing basis system |
| **B — Raster images** | PNG, JPG, a flattened/exported SVG with no real structure, a photographed whiteboard | Vision-LLM call (Claude vision) to extract entities/labels/topology | Lower, genuinely — OCR-on-diagrams is real but imperfect, especially on arrows/topology, hand-writing, low-resolution photos |

This distinction must be visible to the user, not hidden: **Tier A extractions get a `stated`-equivalent
basis; Tier B extractions get a new basis label and an explicit "extracted from an image — verify
this before relying on it" disclaimer**, following the same confidence-basis discipline already
shipped for the rule engine (ui-craft Phase 4). Silently treating a vision-guessed box-and-arrow
read the same as a structured-file parse would be a real regression in the tool's own stated
trust model — the entire product's pitch is "cited, not guessed."

**Recommendation:** ship Tier A first. It requires no vision-LLM call, works with zero backend
changes to the trust model, and covers the most common real case (someone already has a draw.io or
Mermaid source, not just a flattened screenshot). Tier B is a real, separately-scoped v2 addition —
see §4.5.

### 4.3 What "understand and suggest" actually means (reuse, don't fork)

Once a diagram is parsed (either tier), the extraction should produce the **same signal shape**
`detectSignals()` already produces from free text — not a parallel data model. Concretely:

- A recognized AWS icon/label → `s.awsShop = true`, same signal a "we use AWS" sentence sets today.
- A recognized Postgres icon/label → `s.postgresMentioned = true`.
- Recognized topology (e.g., a message queue between two services) → the same `highScale`/`realtime`-
  adjacent signals text detection already infers from language like "event-driven."

This means `computeRecommendations()`, every `pickX()` function, the KB mapping layer, the exit-cost
badges, and the confidence-basis system all work **unmodified** — the new code is purely the
extraction layer (diagram → signals) and, symmetrically, a new rendering layer (picks → diagram).
This is the single most important design decision in this feature: it's an input/output adapter
pair around the existing engine, not a second recommendation engine.

**The diff view** (recommended diagram vs. uploaded diagram) is then just: render the uploaded
diagram's extracted picks alongside the engine's actual recommendation for the same category,
using the exact same badge/why/basis components already built for the results page — element-level,
not a monolithic before/after image.

### 4.4 Export / download

- **Always available, no backend required:** SVG and PNG raster export of the results view (the
  existing stack-card grid, or a generated topology diagram) via client-side canvas rendering —
  matches NFR-1's client-first default.
- **Mermaid text export** — already exists in the ADR exporter (`renderC4` produces Mermaid syntax
  for the container diagram) — this feature extends that existing capability to be a first-class,
  user-facing "Download diagram" action, not just embedded inside the ADR bundle.
- **draw.io XML export** — new, but low-effort: `.drawio` is documented, human-readable mxGraph XML;
  generating it from the same picks data used for the Mermaid export is a formatting problem, not an
  integration problem (no API, no auth, just a downloadable file draw.io opens natively).

### 4.5 Functional requirements

| ID | Requirement |
|---|---|
| FR-32 | Accept file upload of Tier A formats (SVG with real structure, `.drawio` XML, Mermaid `.mmd`/`.md` text, PlantUML text) and parse them deterministically into the same signal shape `detectSignals()` produces from free text. |
| FR-33 | Every signal extracted from a Tier A file must carry a `stated`-equivalent confidence basis and must be inspectable back to the specific diagram element that produced it (same "why" traceability principle as FR-30). |
| FR-34 | Render a side-by-side or inline diff between the uploaded diagram's extracted picks and the engine's own recommendation for the same category, using the existing stack-card/badge/why components — not a separate UI pattern. |
| FR-35 | Provide "Download diagram" as SVG and PNG, client-side only, no backend dependency. |
| FR-36 | Provide "Download diagram" as Mermaid text, extending the existing `renderC4` capability to a standalone, user-facing export action. |
| FR-37 | Provide "Download diagram" as `.drawio` XML. |
| FR-38 *(v2, backend-required)* | Accept Tier B raster image uploads (PNG/JPG/flattened SVG) and extract signals via a vision-LLM call, gated behind the same opt-in/API-key pattern as the existing "Refine with AI" feature (FR-27) — never a silent fallback from Tier A. |
| FR-39 *(v2)* | Every signal extracted from a Tier B image must carry a distinct confidence basis (e.g. `image-extracted`) and a visible "extracted from an image — verify before relying on it" note, never presented at the same confidence as a Tier A or text-stated signal. |

### 4.6 Open questions

1. Should Tier A parsing run entirely client-side (a `.drawio`/SVG/Mermaid parser is plain
   JS/text-processing, no LLM needed) — this seems clearly yes, keeping FR-32–37 available with
   zero backend dependency, consistent with NFR-1/NFR-5. Confirm before scoping.
2. Upload size/complexity limits — a real architecture diagram could have 50+ elements; what's the
   ceiling before extraction quality/UI degrades, and what should the tool say when it's hit?
3. For Tier B (v2), which vision model — reuse the existing Anthropic-key-based path (FR-27's
   pattern) or is a dedicated vision-capable model selection needed? Affects cost and the existing
   token-budget indicator's accounting.

---

## 5. Feature 2 — External design-tool integration

### 5.1 User stories

- As a user whose team lives in draw.io/Eraser/Figma, I want the recommended architecture to land
  in that tool directly, not as a page I have to manually redraw.
- As a user, I want to know upfront which tools are genuinely supported vs. which just get a
  generic export I can manually import — not discover the difference by trying and failing.

### 5.2 Per-tool feasibility — assessed, not assumed

The six named tools are not equally buildable. Treating them as one uniform "integrate with design
tools" checkbox would be the same mistake this session has repeatedly caught elsewhere (BFSI/on-prem
handling, threshold tuning) — a plausible-sounding blanket claim that doesn't survive contact with
the actual constraints. Assessed against: does the tool have an open/documented format or API that
supports *programmatic creation* of a new diagram (not just reading/embedding existing ones)?

| Tool | Path | Auth needed | Feasibility | Recommendation |
|---|---|---|---|---|
| **Mermaid.js** | Plain text generation, already partially built (`renderC4`) | None | **High** — no API, no auth, deterministic | Ship first; it's mostly done |
| **draw.io / diagrams.net** | `.drawio` XML (mxGraph), fully open, documented format | None (file download, opens natively) | **High** | Ship alongside Mermaid — same effort shape as §4.4 |
| **Eraser.io** | Documented REST API + their own DSL for programmatic diagram creation | Eraser API key (user-supplied) | **Medium** — real API, real auth flow to build | Second wave, after Mermaid/draw.io prove the export pipeline |
| **Figma** | REST API can create/modify nodes, but meaningfully more complex than flat XML; historically write support lived mainly in the sandboxed Plugin API, not a simple server-side call | Figma OAuth (per-user account connection) | **Medium-low** — technically possible, materially more engineering than draw.io, plus a real OAuth integration to build and maintain | Third wave; don't commit to a date until a spike confirms current API capability |
| **Penpot** | Open-source, has an API, but is a general graphic-design tool, not diagram-native — would need us to model architecture shapes ourselves rather than use built-in diagram primitives | Penpot account/API token | **Medium-low**, lower priority than Figma given smaller user base | Same wave as Figma or later, reassess demand first |
| **Canva** | Connect API is oriented around templates/embedding/export automation, not general programmatic creation of arbitrary structured diagrams | Canva OAuth | **Low** | **Recommend descoping.** Canva isn't built for this; forcing a diagram-creation integration through a template-automation API would produce a worse result than just offering the generic SVG/PNG export from §4.4. |
| **Sketch** | Mac-only, proprietary bundle format, no public write API — Sketch's extensibility model is native plugins running *inside* the app, not something a web backend can drive | N/A — no viable server-side path | **Not feasible** as a true integration | **Recommend explicit exclusion from this feature**, not a "later" — the honest answer is "download SVG, import into Sketch manually," which already works via §4.4 and needs no Sketch-specific code |

**Bottom line:** of the six tools named, two (Mermaid, draw.io) are genuinely low-effort and should
ship together as the actual v1 of this feature. Two (Eraser, Figma) are real but meaningfully
bigger, each needing its own auth flow and API integration, and belong in a later phase gated on
whether the v1 export pipeline actually gets used. Two (Canva, Sketch) don't fit this product's
integration model at all and are better served by the plain SVG export already covered in Feature 1
— recommend not building tool-specific work for either.

### 5.3 Shared architecture with Feature 1

Feature 1's export layer (§4.4) and Feature 2's tool integrations are **the same underlying
capability at different fidelity levels** — a picks-to-diagram renderer that can target Mermaid,
`.drawio` XML, or (later) a tool's API payload. These should share one internal representation
(an intermediate diagram model: nodes, edges, labels, categories) rather than each tool getting its
own bespoke serializer built from scratch. Building Feature 2 without this shared layer would mean
re-solving "how do our picks become boxes and arrows" once per tool.

### 5.4 Functional requirements

| ID | Requirement |
|---|---|
| FR-40 | Define a shared internal diagram model (nodes/edges/labels/categories) that both the Feature 1 export formats and Feature 2 tool integrations serialize from — one source of truth, not per-tool logic. |
| FR-41 | Export the current recommendation as `.drawio` XML, downloadable with no external API call or auth. *(Same artifact as FR-37 — listed here too since it's also this feature's v1 deliverable.)* |
| FR-42 *(v2)* | Export to Eraser.io via their documented API, gated behind a user-supplied Eraser API key, following the same lazy-credential-prompt pattern already used for the Anthropic key (never stored server-side). |
| FR-43 *(v2, contingent on a feasibility spike)* | Export to Figma via OAuth account connection and the Figma REST API — scope and commit to this only after a spike confirms current API write capability meets the bar set by FR-40's shared model. |
| FR-44 *(explicitly out of scope)* | Canva and Sketch integrations are not planned — documented here so the decision is visible, not silently absent. |

### 5.5 Open questions

1. Who owns the Eraser/Figma API credentials in the backend — same "request-body-only, never
   server-persisted" pattern as the existing Anthropic key handling (`backend/.env.example`'s
   locked decision), or does OAuth (Figma) require a genuinely different, longer-lived credential
   model? This needs a real answer before FR-43 is scoped, not assumed to match FR-42's pattern.
2. Is a Penpot integration worth building at all before there's a specific user asking for it —
   recommend treating it as backlog, not a committed phase.

---

## 6. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-6 | Tier A diagram parsing (FR-32) must work with zero external network calls, consistent with the existing NFR-1 client-first principle — this is a hard constraint, not a nice-to-have, since it's the only sub-feature in this PRD that *could* be built client-only and shouldn't be regressed into requiring a backend. |
| NFR-7 | Any credential (Eraser API key, Figma OAuth token) must follow the existing "never stored server-side beyond the request that needs it" pattern already locked in for the Anthropic key — no new credential-handling model introduced without an explicit, separate decision. |
| NFR-8 | Image-extracted (Tier B) signals must never be visually or textually indistinguishable from text-stated or Tier-A-structured signals — the confidence-basis system's core guarantee (no unearned certainty) must hold across every new input path this PRD adds, not just the ones that existed when Phase 4 shipped. |

---

## 7. Sequencing recommendation

1. **Wave 1 (client-only, no new backend surface):** FR-32–37, FR-40–41 — Tier A diagram import,
   the diff view reusing existing components, and SVG/PNG/Mermaid/`.drawio` export. This is the
   majority of the real user value in both features, ships without touching NFR-1/NFR-5's
   client-first guarantees, and builds the shared diagram model (FR-40) the later waves depend on.
2. **Wave 2 (backend-required, opt-in):** FR-38–39 (Tier B vision extraction), FR-42 (Eraser export).
   Both follow the already-established "opt-in, degrades gracefully, never silently escalates
   confidence" pattern.
3. **Wave 3 (contingent, spike first):** FR-43 (Figma). Do not commit a date until the feasibility
   spike in §5.5 resolves.
4. **Not planned:** Canva, Sketch (FR-44), Penpot (backlog pending demand).

---

## 8. Risks

- **Vision-extraction accuracy (Tier B) undermining trust.** The whole product's value proposition
  is "cited, not guessed" — a confidently-wrong image read is a worse outcome than no image support
  at all. Mitigated by NFR-8's basis-labeling requirement, but this needs real eval (a test set of
  diagrams with known-correct extractions) before Wave 2 ships, not just a demo that looks good once.
- **Scope creep toward "become a diagramming tool."** The non-goals in §3 exist because this
  feature could easily grow into competing with draw.io/Figma directly instead of interoperating
  with them — worth re-checking against §3 at each wave's kickoff.
- **Per-tool auth maintenance burden.** Each OAuth-based integration (Figma, eventually maybe
  others) is an ongoing maintenance surface (token refresh, API version drift, rate limits) — not
  a one-time build. Factor this into whether Wave 3 is worth it versus just maintaining excellent
  generic exports (Wave 1).

---

## 9. Success metrics (draft — needs the same instrumentation-vs-NFR-1 discussion already flagged as open in the master PRD's Section 10)

- % of sessions that use diagram upload vs. text/wizard input, once shipped.
- Of uploaded diagrams, Tier A vs. Tier B mix (validates whether prioritizing Tier A first was the
  right call, or whether raster/screenshot uploads dominate real usage and Wave 2 should move up).
- Export format distribution (SVG/PNG/Mermaid/`.drawio`/Eraser/Figma) — directly informs whether
  Wave 3 (Figma) is worth its cost.
