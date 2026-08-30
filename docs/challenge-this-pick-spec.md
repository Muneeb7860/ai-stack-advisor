# "Challenge This Pick" — feedback widget spec

Status: **spec only, not built**. Written to scope the feature properly before any code —
per the standing plan file's "Explore first, then plan mode" discipline used for every other
feature this session. Everything below was checked against the actual codebase before being
proposed; nothing here assumes the pasted GTM plan's mockup is accurate as-is.

## Why this exists

BRD Section 7 names "disagreement rate" as a success metric — how often an expert reviewer
disagrees with a specific pick — but there is currently **no instrumentation anywhere in the
product to measure it** (PRD Section 13, "Open Questions," lists this as unresolved). This
widget is the first real mechanism for capturing that signal from actual users, not a
cosmetic feedback button.

## Where it attaches (verified against the real card structure)

Every stack card and trade-off card is enriched by `attachRefineToCard(card, category, label,
cardKey)` (`index.html:5613`), which appends a `.refine-btns-row` containing "Refine with AI"
and "Ask a question". "Challenge this pick" is a third button in that
same row, not a new mechanism — same `cardKey` scoping, same visual treatment
(`icon-btn` class), so it participates in whatever card that button lives on without needing
its own new card-level wiring.

**Reuse, don't invent, the alternatives list.** `attachRefineToCard` already has `category` in
scope, and every stack category already has a real vendor-alternatives array (`CLOUD_VENDORS`,
`DATABASE_VENDORS`, `GUARDRAILS_VENDORS`, etc. — 14 arrays total, `index.html:2193` onward),
the same data `renderAltToggle` (`index.html:2168`) already renders as "See N alternatives" on
every card. The GTM mockup's "pre-populated with top 3 category alternatives" dropdown should
read from `{CLOUD_VENDORS, DATABASE_VENDORS, ...}[category]`, not a separately maintained list —
one source of truth for "what are the alternatives to this pick," used by two different UI
surfaces.

## UI & interaction contract

1. Button: `⚖ Challenge this pick`, appended to `.refine-btns-row`, calling
   `onChallengeToggleClick('${cardKey}')` — mirrors `onAskToggleClick`'s exact toggle pattern
   (`index.html:5723`): a single call opens/closes a form, doesn't require a second
   dedicated close function.
2. On open, an inline form (styled like `.ask-box`, not a new component family) with:
   - A `<select>`: "What would you choose instead?" — options built from
     `{category vendor array}[category]`, plus a literal `Other (specify below)` option. No
     free-standing "custom text" field duplicating the select unless `Other` is chosen — the
     GTM mockup's separate always-visible custom-text field is unnecessary UI when the vendor
     list already covers the common case.
   - A `<textarea>`: "Why is this a better fit for your case?" — required, matching the
     existing `.ask-input-row` input pattern's required-before-send convention.
   - Two actions: `Submit` and `Cancel` (not "Copy Feedback JSON" — see Data model below for
     why that's redundant here, unlike a context where there's no backend at all).
3. On submit: save locally (always) and POST to the backend (only if reachable) — see below.
   Show a brief inline confirmation ("Noted — thanks") reusing the existing toast/inline-message
   convention (`.refine-nochange`-style small text), not a new dialog.

## Data model

**Client-side, always.** New `getChallengeLog()` / `saveChallengeEntry(entry)` functions next
to `getAnalysisHistory()`/`saveAnalysisHistoryEntry()` (`index.html:6010`), same
try/catch-wrapped flat-array-under-one-`localStorage`-key pattern, key `stack_challenges`.
Entry shape: `{id, analysisText, cardKey, category, currentPick, proposedAlt, reason, ts}` —
enough to reconstruct the disagreement without needing a live `analysis_id`, so it still works
for a v1-only user who never hit the backend at all (NFR-1: v1 must work with zero external
network calls).

**Backend, opt-in — new `Disagreement` table**, following the exact pattern
`RefinementResult`/`ConversationMessage` already establish (`backend/app/models.py:43-73`):
append-only, `analysis_id` foreign key, no update/delete endpoint (matching
`RefinementResult`'s "never overwrite, never worry about the disagreement rate metric being
skewed by edits" rationale, `models.py:43`). Requires `ensureAnalysisId()` to have already run
(same lazy-creation convention `onRefineClick`/`onAskClick` already use,
`index.html:5441`) — a disagreement about a pick you never persisted to the backend just
stays local-only, which is correct: nothing about "you disagreed with X" needs a server row if
the analysis itself was never shared with the server.

```python
class Disagreement(Base):
    """Captures BRD Section 7's disagreement-rate metric. Append-only, same rationale as
    RefinementResult (models.py:43) — a disagreement is a fact about a moment, editing it
    later would corrupt the rate calculation, not just the record.
    """
    __tablename__ = "disagreements"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    current_pick: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_alternative: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

New endpoint `POST /api/analyses/{id}/disagreements`, following `refine.py`/`ask.py`'s own
conventions exactly: request/response Pydantic models in `schemas.py` next to
`RefineRequest`/`AskRequest`, a router file `backend/app/routers/disagreements.py`, no LLM
call at all (this one's pure CRUD, unlike refine/ask) — so no API-key handling, no
`llm_providers.py` involvement, the simplest of the four routers.

Client sends this **best-effort, fire-and-forget** — same posture as the existing
`/health` probe pattern (`probeBackendHealth`): if the backend is unreachable, the local
`localStorage` save already happened, so nothing is lost, and the UI never blocks or shows an
error for a background sync failing.

## Explicitly NOT in this spec (real scope boundaries, not oversights)

- ~~**No aggregate dashboard/analytics view of disagreements**~~ — scoped and shipped separately,
  see `docs/aggregate-disagreements-dashboard-spec.md` (a local, read-only report script; no new
  network endpoint, since no auth infra exists anywhere in this backend and a public feed of
  every beta tester's stated disagreements isn't the same access-control shape as `share.py`'s
  public-by-design links).
- **No "Copy Feedback JSON" button** — that made sense in the GTM mockup's framing (manually
  relaying feedback with no backend), but this spec already has a real persistence path
  (localStorage + opt-in backend row), so a manual copy/paste step is redundant, not a nice-to-have.
- ~~**Not wired into the Flow View's node popovers**~~ — shipped: `showFlowPopover()`
  (`index.html`, search `attachChallengeToFlowNode`) now appends the same Challenge button/box
  via `buildChallengeButtonHtml`/`buildChallengeBoxHtml` (factored out of `attachRefineToCard`
  for this reuse), with a small `FLOW_NODE_CATEGORY_OVERRIDES` map for the handful of flow node
  ids that don't equal their `STACK_CARD_CATEGORY` key directly (`arch`→`architecture`,
  `computemodel`→`compute`, `lang`→`languages`, `db`→`database`). Flow-only nodes with no
  `STACK_CARD_CATEGORY` entry at all (`llm`, `rag`, `vectordb`, `mcp`, `guardrails`) fall through
  to the same free-text-only form every card-side category without a vendor array already uses —
  not specially handled. Refine/Ask were deliberately NOT added to the Flow View in this pass;
  only Challenge This Pick, per this note's original scope.

## Testing approach (once this moves from spec to implementation)

Following this session's established pattern exactly:
- Node-harness test with a **real in-memory localStorage stub** (matching
  `test_analysis_history.py`'s approach, not the no-op stub other harness tests use) for
  `getChallengeLog()`/`saveChallengeEntry()` round-trip.
- `backend/tests/test_disagreements.py` following `test_ask.py`/`test_refine.py`'s existing
  structure (FastAPI `TestClient`, a live-Postgres-backed integration test, no LLM
  monkeypatching needed since this router never calls one).
- A static regression lock (matching `test_bug8_provenance_map_does_not_key_on_context_signals`'s
  style) asserting the per-category vendor arrays used by the new dropdown are the SAME
  arrays `renderAltToggle` already reads — i.e. a test that fails if someone duplicates the
  list instead of reusing it.
- Every new assertion mutation-tested (revert, confirm failure, restore) before considering the
  feature done, per this session's unbroken discipline.

## Open decision needed before implementation starts

Whether the vendor-alternatives dropdown should also let a user select "none of the
alternatives — my pick isn't even in this KB," which would itself be a useful signal (a KB
gap, not just a preference disagreement) but changes the entry shape (`proposedAlt` becomes
optional, a new `unlistedAlternative: true` flag needed). Not decided here — flagging it as a
real fork rather than picking one silently.
