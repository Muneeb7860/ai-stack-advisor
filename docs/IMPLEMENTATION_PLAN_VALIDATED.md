# Validated Implementation Plan: PRD/BRD Ingestion, SVG Topology, Executive ARB View

> **Status: the original plan needs substantial revision before implementation.**
> It is directionally reasonable, but it proposes building four things that already
> exist, and one component (a backend ingestion API) that inverts a deliberate,
> documented architecture decision. Every claim below was checked against the
> codebase on the date this file was written — file and line references included so
> each is independently verifiable.
>
> This document does not replace the original; it records what the original got
> wrong about the current codebase and what the corrected scope actually is.

---

## 0. What already exists (checked, not assumed)

The original plan's biggest problem is that it was written without inspecting the
current `index.html`. These are all present today:

| Original plan proposes to build | Already exists | Evidence |
|---|---|---|
| Backend `/api/ingest-document` with `pypdf`/`python-docx` | Client-side ingestion via a ports-and-adapters registry, incl. a working `.docx` adapter | `index.html`: registry `DOCUMENT_ADAPTERS` + `registerDocumentAdapter`; the `.docx` adapter (`id: 'docx'`) reads `word/document.xml` via `zipFindEntry` / `docxBlocksFromXml` |
| An SVG architecture canvas in vanilla JS | `generateSvgDiagram(rec, signals)` | `generateSvgDiagram` in `index.html` |
| An Executive ARB Summary view + ADR export | ARB review pack — but see note below; this shipped *after* the plan was written | `backend/tests/test_arb_review_pack.py` (320 lines) |
| Itemized monthly cost estimate, summed | Per-category cost **bands** that deliberately never sum | the `computeBand` / `dbBand` / `llmBand` definitions in `index.html`; forbidden by **one** test, `test_the_cost_panel_never_adds_the_bands_up`, and only inside `arbCostRows` |

> **Provenance note on the ARB view.** `test_arb_review_pack.py` was created by
> commit `4905d56` ("A review view that shows the decision pack rather than
> re-deriving it", #98), which landed *this working session* — confirmed via
> `git log --diff-filter=A -- backend/tests/test_arb_review_pack.py`. So the ARB
> Summary is not something the original plan's author missed in pre-existing code;
> at the time the plan was written it did not exist. The conclusion ("don't build
> it twice") stands, but the reason is "it was built in parallel," not "it was
> overlooked." Two of the four items were genuinely pre-existing; this one and its
> cost-total guard arrived with #98.

> **Correction on the cost guard.** An earlier draft of this doc claimed the cost
> total is "forbidden by two tests." That overstated it by one.
> `test_hero_does_not_invent_a_single_cost_figure` (`test_hero_does_not_invent_a_single_cost_figure` (`test_density_pass.py`))
> asserts only that `costEstimate` and `Cost` are absent from `heroSpine` — it is
> indifferent to the ARB view. Exactly **one** test forbids a total, and only
> inside `arbCostRows`. An itemized modeler built as a new function elsewhere would
> pass both tests today. The no-total rule is therefore a product decision to make
> deliberately, not a fence the test suite already enforces everywhere.

`app/llm_providers.py` **does** exist (`backend/app/llm_providers.py`), so the
optional-refinement reference in the original is valid.

---

## 1. Blocker-level corrections

### 1.1 Phase 1 inverts a locked invariant — do NOT add a backend ingestion API

`AGENTS.md` states, verbatim:

> "Entry-mode parsing is frontend-only. `parseDiagramInput`, `parseManifest`,
> `ingestDocument` and `synthesizeRequirementText` have no Python twin **by design**,
> so they carry no parity surface. Don't port them; don't add parity tests for them."

Ingestion runs in the browser on purpose: a PRD dropped on the page is parsed and
shown for confirmation with **no network call**, which is the offline/zero-network
core promise the landing page asserts and `test_landing_claims_are_current.py`
guards. A backend `/api/ingest-document` route breaks that promise — a document
would suddenly require a running FastAPI server to parse.

**Corrected scope:** add a `.pdf` adapter to the existing client-side
`DOCUMENT_ADAPTERS` registry (`DOCUMENT_ADAPTERS` / `registerDocumentAdapter` in `index.html`, extended via `.push()` at
via `registerDocumentAdapter`). The `.docx` adapter (`id: 'docx'`) is the template to follow: it declares
`label`, `accepts(filename)`, and an extract step, and reads bytes in-browser.

The one legitimate exception — and the only case where a backend route would be
justified — is **scanned/image PDFs requiring OCR**, which cannot run in-browser.
If that capability is wanted, it must be argued explicitly against NFR-5 (offline
core) and scoped as an *optional enhancement path* that degrades cleanly when the
backend is absent, not as the default ingestion route. Text-extractable PDFs (the
overwhelming majority of PRDs) do not need it — `pdf.js`-style text extraction runs
client-side.

### 1.2 Phase 3 SVG work is an extension, not a new build

`generateSvgDiagram` exists. Rewording required: the topology canvas should
**extend the existing generator** into an interactive, node-clickable view, reusing
`openGlidePanel` for the details drawer (which the original correctly identified as
the drawer to use). Building a second SVG generator in parallel is the
two-implementations-drift failure `AGENTS.md` warns about repeatedly.

### 1.3 The ARB cost modeler collides with two tests — bands, not totals

The original's "Itemized monthly infrastructure estimates (Vector DB tier + LLM
token budget + Orchestrator instances + Monitoring)" summed into a total is a
category error, not just an imprecise one. On an on-prem analysis the three bands
read `Not applicable — capex, not opex`, `$25–$100/mo`, and `$0` — summing those
adds amortised hardware capex to a monthly cloud bill, which is a different unit,
not a rounder number.

Exactly one test enforces this today:

- `test_the_cost_panel_never_adds_the_bands_up` (`test_arb_review_pack.py`) `test_the_cost_panel_never_adds_the_bands_up` —
  "Three bands, each carrying its own caveat, and no fourth row totalling them."
  Scoped to `arbCostRows`.

Note `test_hero_does_not_invent_a_single_cost_figure` does **not** cover this — it
only checks `heroSpine`. So a new itemized modeler built elsewhere would pass the
suite. The rule holds because it is a sound product decision, not because a test
blocks it — which means it is exactly the kind of invariant that erodes quietly
unless the decision is made on the record.

**Corrected scope:** the ARB view may *display* the existing per-category bands
(`computeBand`, `dbBand`, `llmBand` at the `computeBand` / `dbBand` / `llmBand` definitions in `index.html`), each with its
caveat intact. It must not add a total. If a stakeholder genuinely wants a run-rate
number, that is a product-philosophy decision to raise explicitly with the owner —
not something to slip in under "cost modeler," and not something to weaken the two
tests for without that decision being made on the record.

### 1.4 Phase 4 quotes a forbidden, and stale, test count

The original says "zero regressions against the existing 1,309 passing tests."
`AGENTS.md`: "Never quote a pass count from any document, including this one...
Stale ones have twice been used to claim a green baseline that was not real."
**Corrected wording:** "Run `cd backend && python3 -m pytest -q`, read the output,
and report this run's numbers. The baseline is whatever that run prints, not a
figure copied from a plan."

> This document deliberately records **no** pass count, for the reason above. An
> earlier draft named one ("1,348 earlier") — that was the same defect this section
> flags: a remembered number in a planning doc is stale the moment another commit
> lands, and #98 added ten tests after it was written. The only valid number is the
> one your own `pytest` run prints now.

---

## 2. What is genuinely new and sound

Stripped of the parts that already exist, the real, buildable delta is:

1. **A `.pdf` client-side adapter** — new leaf in the existing registry. Small,
   self-contained, testable with a fixture PDF. (Phase 1, relocated to frontend.)
2. **The tabbed results shell** — `[Technical Recommendations] [Topology] [Executive
   ARB]` segmented control in `.results-header`. New, conflicts with nothing. Wire it
   to show/hide the three already-existing views rather than generate them.
3. **Interactivity on the existing SVG** — click-to-highlight + drawer. Extension of
   `generateSvgDiagram`, reusing `openGlidePanel`.
4. **A shared, multi-reviewer voting ledger** — this is the one genuinely new,
   genuinely hard piece, and it is *not* greenfield the way the original implies. #98
   already shipped a four-role sign-off checklist in localStorage, keyed to a
   fingerprint of the deck's contents, and that panel honestly labels itself "a local
   checklist, not an approval system." The gap is not storage size — it is that
   localStorage is per-browser, so four reviewers on four machines can never see each
   other's ticks. Turning the local checklist into real multi-stakeholder voting
   needs **identity and shared state**, i.e. an auth story nobody has scoped. These
   are two different features, not two settings of one. See §4.1.

---

## 3. Corrected phase plan

### Phase 1 — `.pdf` client-side adapter (frontend only)
- Add a `pdf` entry to `DOCUMENT_ADAPTERS` following the `.docx` adapter's shape.
- **Fail-loud on non-extracting PDFs is the primary requirement, not OCR** (see §4.3).
  After text extraction, if the yield is empty or effectively all-whitespace — the
  `Type0`/`Identity-H` case, which Word and Google Docs both produce — reject the
  file with the same "save as .md/.txt and re-upload" guidance the `.docx` path gives
  on decompression failure (the `.docx` decompression-failure path in `index.html` (grep `Save the document as .md or .txt`)). Silently passing whitespace to the
  advisor produces confident output from nothing, which is worse than an error.
- Text-extractable PDFs are the supported happy path. Image-only (`/DCTDecode`)
  PDFs are detected and rejected here; OCR for them is out of scope for this adapter.
- Test: because these adapters are frontend-only by contract, they carry **no pytest
  parity surface**. Verification is a browser check plus, if a headless harness
  exists, a DOM assertion — not a Python test. Do not add a Python twin.

### Phase 2 — dropzone copy + extracted-requirements card
- Extend the existing dropzone accept list and copy to name `.pdf` — the
  `#diagramDropzone` / `#diagramFileInput` elements and the `.dropzone-sub` line
  (cite by symbol: line numbers here moved +47 when #98 landed and will move
  again when the uncommitted accessibility pass is committed).
- The confirmation card the original describes is reasonable and mostly new UI;
  it should feed `synthesizeRequirementText` (which already exists) rather than a new
  transfer path.

### Phase 3 — tabbed shell + topology interactivity + ARB display
- Tabbed shell: new segmented control, show/hide existing views.
- Topology: extend `generateSvgDiagram`; reuse `openGlidePanel`.
- ARB: display existing bands (no total); add the voting ledger per the §2.4 decision.
- If any **new recommendation category / stack card** is introduced here, wire it
  through every enumeration point the codebase requires — grep the category-registration
  sites in `rule_engine.py` and `index.html` and confirm parity, because a card added
  in one engine and not the other is precisely the drift the dual-engine tests catch.

### Phase 4 — verification
- `cd backend && python3 -m pytest -q`; report this run's numbers.
- Keyboard + screen-reader pass (aligns with the accessibility work already sitting
  uncommitted in `index.html`).
- Confirm no new `<script src="http…">`, no root `package.json`, `<main>` balance
  intact — the single-file/offline invariant guards.

---

## 4. Open decisions for the owner (blocking)

### 4.1 Voting ledger — neither option as originally posed
The local checklist already exists (#98). "Session-only vs persisted" is a false
choice: real multi-stakeholder voting requires identity + shared state + an auth
story that has not been scoped, and that is a distinct feature, not a storage
setting. **Recommendation:** keep the local checklist until someone actually needs
to see a colleague's sign-off. At that point it is a backend feature *with an auth
prerequisite*, scoped on its own — not part of this one.

### 4.2 Cost total — hold, and it is not close
On an on-prem analysis the bands are `Not applicable — capex, not opex`,
`$25–$100/mo`, `$0`. Summing them adds capex to opex — a unit error, not a
precision trade-off. **Recommendation:** hold the no-total rule. If a run-rate is
ever genuinely wanted, it is a recorded product decision that also means rewriting
`test_the_cost_panel_never_adds_the_bands_up`, not a quiet addition.

### 4.3 PDF ingestion — "OCR" scopes out the more common failure
Measured on three real PDFs: one `/DCTDecode` image-only (the OCR case); one with
`Type0`/`Identity-H` fonts that yielded 912 characters of **pure whitespace,
silently**; one that extracted cleanly. Word and Google Docs both export the
Identity-H shape, so the whitespace case is *more common* than the scanned case —
and more dangerous, because it produces confident recommendations from an empty
string rather than an error. **Therefore the `.pdf` adapter's first requirement is
not OCR — it is to detect a non-extracting PDF (near-empty or all-whitespace text
yield) and fail loudly with the same "save as .md/.txt and re-upload" guidance the
`.docx` path already gives**, rather than silently feeding whitespace to the engine.
OCR for image-only PDFs remains a separate, optional, backend-only enhancement that
must degrade cleanly offline.

Until 4.1 and 4.2 are answered, the ARB portion of Phase 3 cannot be scoped
precisely. Phase 1 (the `.pdf` adapter, with 4.3's fail-loud requirement),
Phase 2, and the tabbed shell can proceed now.
