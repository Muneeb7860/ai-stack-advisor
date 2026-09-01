# Document ingestion (PRD / BRD / spec) — scope

**Status:** Phases 1-4 SHIPPED (PR #73) — the port and registry, the plaintext and `.docx`
adapters, section classification, confirm-with-provenance, routing precedence, and the
Refine/Ask privacy guard. Phase 5 (`.pdf`) remains deliberately unshipped as a documented
extension point. One item still open: `DecompressionStream('deflate-raw')` is confirmed in the
Node runtime the tests use but has NOT been verified in the project's real target browsers,
which the `.docx` adapter depends on.

Every number below was measured against the current engine, not estimated.

## Why the obvious implementation ships a regression

The proposal is "drag in a PRD, extract the text, feed it to the engine." Measured, that makes
recommendations dramatically **worse** on exactly the documents it targets.

Starting from a correct short prompt (healthcare portal, HIPAA, 25,000 concurrent, 4 Python
engineers) and appending the sections every real PRD has — *Alternatives Considered and Rejected*,
*Non-Goals*, *Glossary*:

| | signals fired | picks wrong |
| --- | --- | --- |
| Correct short prompt | 6 | — |
| Raw PRD text | 13 | **24** |
| PRD with non-requirement sections removed | 6 | **0** |

All seven extra signals were false. `onPrem` fired on *"An on-premise air-gapped deployment was
discussed but is **explicitly out of scope**."* `kafkaMentioned` on *"we evaluated Kafka but
**rejected** it."* `pciMentioned` on a **glossary entry saying "not applicable."**

The result was not subtly off. The whole stack flipped from AWS / Cloudflare / serverless / EKS /
React to on-premises bare metal, self-hosted Keycloak, self-managed Kubernetes and GitLab CE — a
confident, fully-formed, completely wrong architecture, produced silently.

`strip_negations` handles adjacent negation ("we do not want on-premise") and nothing else. It
leaves "explicitly out of scope" and "we rejected Kafka" fully intact, by design — it was built for
short prompts, where that is the right scope.

**So the feature is not text extraction. It is deciding which parts of a document are
requirements.** Extraction is the packaging.

## Architecture: ports and adapters

Chosen because it is already how this codebase works, not as ceremony. `rule_engine.py` is a domain
core with zero framework imports; the MCP server and the FastAPI routers are adapters over it. The
product also *recommends* hexagonal architecture to its own users, with a stated test: swap the
adapter and the domain does not move.

### The port

```
DocumentAdapter = {
  id, label,
  accepts(filename, headBytes) -> bool,
  extract(content)             -> { blocks: [{ heading, text }], wordCount }
}
```

**The port returns blocks, not text.** This is the load-bearing decision. If the port returns a
flat string, section classification has to happen inside each adapter — written three times, wrong
twice, and absent entirely for any adapter added later. Returning structure puts classification
downstream of every adapter, in the domain, written once.

### The layers

- **Adapters** (format-specific, pluggable): `.txt` / `.md` trivially; `.docx` by reading
  `word/document.xml` out of the ZIP; `.pdf` **not shipped** — see below.
- **Domain** (format-blind, the actual feature): classify blocks as requirement / non-requirement,
  assemble the requirement text, and report what was dropped.
- **Existing domain, untouched**: `detectSignals` and `computeRecommendations` never learn that
  documents exist. Ingestion joins the same funnel every other entry mode uses —
  `setAnalysis(text, detectSignals(text))` — exactly as manifest ingestion does.

### What this buys on `.pdf`

PDF text lives in compressed content streams with font encoding maps; extracting it reliably means
a real parser. The README states the invariant: *"No build step, no dependencies, no server. Works
offline."*

As an adapter, PDF stops being a dilemma. The shipped artifact carries `.txt`/`.md`/`.docx` and
keeps the invariant; anyone needing PDF registers an adapter carrying its own parser. **Do not
inline a PDF library into index.html to close a format gap.**

`.docx` is genuinely dependency-free: it is a ZIP, and `DecompressionStream('deflate-raw')` handles
the inflate (confirmed available in the Node runtime used by this repo's tests; **verify browser
support against the project's actual target browsers before building the adapter** — it is the one
technical assumption here that has not been checked where it matters).

### Honest limit on "pluggable"

`index.html` has no module system, so pluggable means **one registry plus an extension point**, not
runtime plugin loading. Adding an adapter still means appending a `<script>` or editing the file.
Precedent exists — `window.__API_BASE__`, the localStorage custom-technology catalog — so it is
consistent with how this file already does extensibility, but it should not be described as more
than it is.

## The hard part, and where it fails

Section classification recovers the correct answer completely (24 wrong → 0) **when the document
has headings the classifier recognises**. Heading detection is the fragile part, and two prototype
regexes each handled a different subset:

| Heading style | Prototype A | Prototype B |
| --- | --- | --- |
| `Section 8 — Non-Goals.` | caught | **missed** |
| `## Non-Goals` | missed | caught |
| `NON-GOALS` (all caps) | missed | caught |
| no headings at all | **cannot be caught** | **cannot be caught** |
| `We rejected an on-premise deployment.` (inline) | **cannot be caught** | **cannot be caught** |

The last two rows are the important ones. A rejection stated inside a requirement paragraph, or a
document with no section structure, is not reachable by classification at any level of effort — the
information that it is a rejection is semantic, not structural.

**This is why the confirm-and-edit step is not polish.** It is the safety net for the cases
classification provably cannot reach. Surface each detected signal with the sentence that produced
it — "on-prem — *from: 'explicitly out of scope'*" is visibly wrong to a human and one click from
removal. The manifest flow's confirm-the-chips pattern applies directly; the difference is that
here it is load-bearing rather than courteous.

## Review findings (added after re-reading this against the code)

Three things this scope originally missed or got slightly wrong.

**Routing precedence.** `parseDiagramInput` already claims `.md` and `.txt`: anything it does not
recognise falls through to a raw-line fallback that turns the first 15 lines into chips. A PRD
dropped today becomes fifteen chips of prose. So document adapters must be routed **after** the
manifest check (exact filenames) and the diagram sniffs (extension/content), and must **replace**
the raw-line fallback rather than sit beside it. That fallback is the current behaviour for exactly
the files this feature is for.

**What gets confirmed is signals, not components.** The manifest and diagram flows confirm
*components* — a chip per detected technology. A document produces one requirement text plus a set
of inferred signals, and the thing a user needs to correct is a **signal** ("on-prem — from:
'explicitly out of scope'"), not a component. The confirm *pattern* carries over; the content does
not. Saying "the manifest chips pattern applies directly" was too glib.

**Provenance is obtainable without exposing the keyword tables.** `detectSignals` is pure and costs
0.054 ms, so running it per block and attributing each fired signal to the block(s) that produce it
gives block-level provenance for free — no need to expose or duplicate the internal keyword lists.
Block-level ("this came from *Section 7 — Alternatives Rejected*") is also the right granularity:
it is what the user needs to judge whether the section should count at all.

**Convergence with the what-if levers.** Confirming a signal means turning one off, and
`signalOverrides` today carries only `{excluded, known}` — it cannot express "ignore this boolean".
That is the *same* capability `WHATIF_LEVERS_SCOPE.md` Phase 1 needs. Build boolean signal
overrides through `applySignalOverrides` once and both features get it. Whichever is built first
should build it as shared machinery rather than a local hack, and the other then costs materially
less than its own scope doc estimates.

## Privacy, stated rather than assumed

The pitch for this feature is that confidential documents never leave the machine. For the analysis
that is true (NFR-1/NFR-5). But `/api/refine`, `/api/ask` and `/api/analyses` exist, so a user who
uploads a confidential PRD and then clicks **Refine with AI** sends its content to an LLM.

Either guard that path for document-sourced analyses or state plainly what leaves the browser.
Advertising confidentiality while leaving it unguarded is worse than not advertising it.

## Phasing

1. **Port, registry, `.txt`/`.md` adapters.** Small; proves the seam. On its own this ships the
   regression measured above, so it is not independently releasable.
2. **Section classification in the domain.** The actual feature. Not releasable without (3).
3. **Confirm-and-edit of detected signals, with provenance.** Together, 1–3 are the first
   releasable unit.
4. **`.docx` adapter.**
5. **`.pdf`** — documented extension point, not shipped.

## Testing

- Adapters are pure `content -> blocks` functions: Node-harness tests, same pattern as the manifest
  parsers.
- A corpus of realistic document shapes — the heading-style table above is the starting set, and
  every style found in the wild gets added rather than the regex being tuned by eye.
- The load-bearing assertion: **a document whose non-requirement sections are removed produces the
  same recommendations as the equivalent short prompt.** That is the property, measured at 24 → 0
  above; a test that only checks headings were detected would pass while the picks stayed wrong.
- An explicit test that inline rejections are NOT silently mishandled — since classification cannot
  catch them, the requirement is that they reach the confirm step visibly, not that they are fixed.
- Mutation-test every assertion, per standing practice.

## Out of scope

- Changing `strip_negations`. It is correct for short prompts; document-level context is a
  different problem and widening it would risk the entry mode that currently works.
- Any change to `detectSignals` or `computeRecommendations`. If ingestion needs the domain to
  change, the design is wrong.
- Summarising or rewriting the document with an LLM before analysis. That would put a
  non-deterministic step in front of a deterministic engine and forfeit the property the product
  is built on.
