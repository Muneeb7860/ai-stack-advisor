# Real-Time Collaborative Editing

**Domain:** Multi-user concurrent document/canvas editing — Google Docs, Figma, Notion, Linear-style
products. Research date: August 2026.

## Business context

A team building a product where multiple users edit the same document, spreadsheet, design canvas,
or whiteboard simultaneously and expect changes to appear instantly for everyone, without one
person's edit silently overwriting another's. This is a distinct product category from generic
"real-time" apps (live dashboards, notifications) — the defining requirement is **conflict-free
concurrent mutation of shared, structured state**, not just fast one-way data push.

## Signals / triggers

`collaborative editing`, `real-time collaboration`, `multiplayer document`, `concurrent editing`,
`shared whiteboard`, `real-time cursors`, `live cursors`, `presence indicators`, `co-editing`,
`simultaneous editing`, `conflict resolution`, `offline sync`, `merge conflicts`, `CRDT`,
`operational transformation`, `Google-Docs-like`, `Figma-like`, `Notion-like`, `sync engine`,
`multi-user document`, `who's viewing this`, `commenting and cursors`, `live collaboration`,
`shared canvas`.

## Decision points

### A. Conflict-resolution algorithm — CRDT vs. Operational Transformation (OT)

**OT** (historically used by Google Docs) transforms each incoming operation against concurrent
operations so it replays correctly; it typically requires a central server holding canonical order
to mediate transforms. Transform functions are notoriously hard to get correct for rich/nested data
structures. Wins when: you need a small wire format and already have a central authority server,
plain-text documents specifically (its best-proven case).

**CRDTs** resolve conflicts via mathematically commutative/associative merge rules, so any two
replicas that have seen the same updates converge without a central arbiter — enabling true
peer-to-peer sync, offline editing, and a "dumb" relay server. This is the dominant choice for new
products in 2026. Named libraries: **Yjs** (JS/WASM, most mature ecosystem, powers Notion-like/
BlockNote/Tiptap collaboration), **Automerge** (Rust core, strong JSON-document semantics, easy
time-travel/history), **Loro** (newer Rust/WASM, benchmarks competitive/faster than Yjs and Automerge
for large documents).

**Recommendation:** default to CRDT (Yjs specifically, for ecosystem maturity) for any new
product in this category. OT is a legacy/plain-text-only choice at this point, not a 2026 default.

### B. Sync transport / backend

Self-hosted: **y-websocket** (bare-bones reference server, DIY), **Hocuspocus** (opinionated Yjs
server framework with hooks/auth/persistence), **y-sweet** (serverless-friendly, S3-backed
persistence). Cloudflare-based general-purpose real-time infra: **PartyKit**. Fully managed SaaS:
**Liveblocks** (sync + presence + comments + storage bundled).

**Recommendation:** self-host (Hocuspocus) for control and no per-seat cost once you have the ops
capacity; use a managed provider (Liveblocks, PartyKit) to skip building the relay/persistence layer
yourself, especially pre-product-market-fit when engineering time is the scarcer resource than
subscription cost.

### C. Persistence strategy for CRDT documents

Storing the raw, ever-growing CRDT update log forever is expensive and slows load time. Best
practice: periodically compact/snapshot the CRDT state (e.g. Yjs `Y.encodeStateAsUpdate` merges),
store snapshots plus a bounded recent-update log, and garbage-collect tombstones once all clients
have acknowledged them.

### D. Presence / awareness / cursor sharing

Cursor position, selection, and "who's online" data is ephemeral, high-frequency, and disposable —
it must never go through the durable CRDT/document persistence path or a transactional database. The
standard pattern (`y-protocols/awareness`, used by Yjs and mirrored by Liveblocks' presence API) is a
separate lightweight, non-persisted broadcast channel keyed by client ID with heartbeat/timeout-based
expiry, sent over the same WebSocket connection but logically distinct from document updates.

## Anti-patterns

- **Naive last-write-wins** on whole fields/documents — silently discards concurrent edits.
- **Storing full unbounded CRDT operation history** without snapshotting/compaction — documents
  balloon and load times degrade over the document's lifetime.
- **Using a regular relational/transactional DB for cursor/presence updates** — ephemeral,
  per-keystroke presence data treated like durable business data causes write-amplification and
  latency; belongs on a pub/sub or in-memory ephemeral channel.
- **Rolling your own OT transform functions for rich/nested data** — extremely error-prone outside
  plain linear text; a major reason the industry moved to CRDTs.
- **Coupling the sync server to business logic/authorization checks per-operation** instead of
  keeping the relay "dumb" and checking permissions at the room/document level.

## Reference implementations

- **Figma** — custom, simplified CRDT system (not textbook Yjs/Automerge); property-based conflict
  resolution per object with the server as source-of-truth relay.
- **Notion** — block-based data model with an OT-like operation log per block, backed by sharded
  Postgres.
- **Linear** — custom local-first "sync engine": full local object graph (SQLite/IndexedDB) synced
  via deltas, prioritizing instant local reads over server round-trips.
- **Liveblocks** — managed platform, CRDT-style storage plus presence/comments/notifications APIs,
  commonly paired with Yjs for text editors.
- **Yjs ecosystem** (Tiptap, BlockNote, y-sweet, Hocuspocus) — the de facto open-source standard for
  rich-text/block editors.

## As implemented in `index.html`

Wired into `pickMessaging(s)` via the `collabEditing` signal: recommends a CRDT sync relay
(Yjs + y-websocket/Hocuspocus self-hosted, or Liveblocks/PartyKit managed) instead of Kafka or a
generic pub/sub broker, with an explicit note that presence/cursor data needs its own ephemeral
channel, never the durable document-update path.

## Sources

- [Zylos Research — CRDTs and Real-Time Collaboration](https://zylos.ai/research/2026-01-29-crdt-real-time-collaboration/)
- [Taskade — OT vs CRDT in 2026](https://www.taskade.com/blog/ot-vs-crdt)
- [HackerNoon — CRDTs vs OT: Practical Guide](https://hackernoon.com/crdts-vs-operational-transformation-a-practical-guide-to-real-time-collaboration)
- [PkgPulse — Yjs vs Automerge vs Loro (2026)](https://www.pkgpulse.com/guides/yjs-vs-automerge-vs-loro-crdt-libraries-2026)
- [PkgPulse — Liveblocks vs PartyKit vs Hocuspocus (2026)](https://www.pkgpulse.com/guides/liveblocks-vs-partykit-vs-hocuspocus-realtime-2026)
- [madebyevan.com — How Figma's Multiplayer Technology Works](https://madebyevan.com/figma/how-figmas-multiplayer-technology-works/)
- [Notion — Exploring Notion's Data Model](https://www.notion.com/blog/data-model-behind-notion)
- [fujimon.com — Linear's Sync Engine Architecture](https://www.fujimon.com/blog/linear-sync-engine)
- [Yjs Docs — Awareness](https://docs.yjs.dev/getting-started/adding-awareness)
- [Electric — Yjs over HTTP on Durable Streams](https://electric.ax/blog/2026/04/07/yjs-durable-streams-on-electric-cloud)
