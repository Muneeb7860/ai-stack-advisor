# Alternatives Research — Group 2: Data Layer
## Databases · Cache · Messaging

**Status:** Draft for audit — standalone research document, not yet wired into `index.html`.
**Prerequisite:** Group 1 (Infra) is complete and audited — see
`01-infra-cloud-compute-containers-gateway.md`. This document follows the same format and the same
step-by-step instruction ("complete 1, do proper audit, then take next").
**Research method:** live web search + fetch, grounded in 2026 sources. Pricing/positioning claims are
sourced, not drawn from training-data priors.

---

## 1. Primary Database Alternatives

`index.html`'s "database" category likely defaults among Postgres/MySQL/MongoDB/managed-cloud-DB as a
style choice. This section separates that into two real sub-decisions: **relational (SQL)** and
**document/NoSQL/wide-column**, which answer different requirement shapes and shouldn't be one flat list.

### 1a. Relational (SQL)

| Database | Best for | Strength | Drawback | Pricing signal |
|---|---|---|---|---|
| **PostgreSQL** | SaaS platforms, AI/ML workloads (pgvector), analytics, fintech, geospatial | JSONB native + indexed, 300+ extension ecosystem (PostGIS/pgvector/Citus/TimescaleDB), native row-level security, permissive licensing | Requires connection pooling (pgBouncer) at high concurrency; steeper learning curve than MySQL; ~5–7% cloud pricing premium over MySQL | Free OSS; managed from ~$0.036/hr on-demand (AWS RDS-class pricing) |
| **MySQL** | WordPress/CMS, high-read simple CRUD, legacy PHP apps | 20–30% faster on simple SELECTs, 30% faster single-node writes, universal CMS ecosystem support, native Group Replication | GPL licensing complicates commercial redistribution (Oracle commercial license needed); 65,535-byte row limit; JSON support materially weaker than Postgres JSONB; no PostGIS/pgvector equivalent | GPL free or Oracle commercial; managed ~$0.034/hr on-demand |
| **CockroachDB** | Startups needing horizontal scale + Postgres compatibility without re-architecting | Postgres-wire-compatible, distributed by default, automatic failover, most generous free-tier storage (10GiB) among researched options | Operational complexity for teams that don't actually need distribution; single-region only on free tier | Free tier: 10GiB storage, 50M request units/mo; paid usage-based |
| **Neon** | Postgres purists wanting serverless/branching workflow, CI/CD preview databases | True database branching (instant copies for PR previews), scale-to-zero, strong DX | Smaller per-project storage (0.5GB free) than competitors; multi-project management overhead at scale | Free: 0.5GB/project, 100 compute-hrs/mo; usage-based beyond |
| **Supabase (Postgres)** | Full-stack apps wanting bundled auth + storage + realtime on top of standard Postgres | Low lock-in (it's just Postgres underneath), all-in-one (auth/storage/edge functions/realtime) | Free projects pause after 1 week idle; smaller free storage (500MB) than Neon/CockroachDB | Free: 500MB storage, 50K MAU auth; usage-based beyond |

**Categorization note:** Supabase and Neon are not "alternative databases" in the same sense as MySQL or
CockroachDB — both run on standard Postgres. They're alternatives to *self-managing* Postgres, i.e. a
different axis (hosting/DX model) from the SQL-engine choice itself. If wired into the product, these
should be a secondary "hosting model" signal, not conflated with the primary engine pick.

### 1b. Document / NoSQL / Wide-Column

| Database | Category | Best for | Strength | Drawback | Pricing signal |
|---|---|---|---|---|---|
| **MongoDB** | Document store | Flexible-schema CMS, e-commerce catalogs | Atlas Vector Search built in, queryable encryption, time-series collections, 100M+ queries/sec at scale | Schema flexibility can become a data-integrity liability without discipline; not covered in the same benchmark studies as Postgres so head-to-head numbers are harder to source cleanly | Atlas managed: consumption-based |
| **DynamoDB (AWS)** | Key-value / serverless | Gaming leaderboards, shopping carts, AWS-native serverless apps | Fully managed, automatic scaling, single-digit ms latency, global tables | AWS lock-in; limited query flexibility (no ad-hoc joins/queries) | On-demand pay-per-request or provisioned capacity |
| **Cassandra** | Wide-column | Time-series/IoT, transaction logs, high-availability multi-DC | Linear scalability via masterless ring architecture, tunable consistency | Operational complexity; eventual-consistency model requires app-level awareness | OSS free; managed via DataStax Astra |
| **ScyllaDB** | Wide-column (Cassandra-compatible) | Real-time bidding, fraud detection, high-throughput messaging | Reports ~10x Cassandra's throughput and CPU efficiency at the same hardware footprint | Smaller ecosystem/community than Cassandra | OSS free; cloud subscription available |
| **Neo4j** | Graph | Social/recommendation graphs, fraud detection, knowledge graphs | Index-free adjacency (fast multi-hop traversal), 65+ built-in graph algorithms, vector indexing | Wrong tool for non-relational/non-graph workloads — not a general-purpose substitute | Aura managed: consumption-based |
| **Couchbase** | Document (multi-model) | Apps wanting integrated cache + DB, mobile offline-first | Memory-first design, integrated full-text search, mobile sync built in | More complex operational model than a plain document store | Capella managed: subscription |
| **InfluxDB** | Time-series | Infra monitoring, IoT sensor data, financial tick data, dashboards | 1M+ points/sec ingestion, 10–20x compression | Purpose-built for time-series only — not a general database | Cloud Serverless pay-per-query or subscription tiers |

**Best-bet logic (proposed):** the existing signal set already likely detects "AI/ML," "geospatial,"
"high write throughput," "flexible schema" style requirements — those map cleanly to Postgres+pgvector,
PostGIS-flagged Postgres, Cassandra/ScyllaDB, and MongoDB respectively. A `graphRelationships` or
`recommendationEngine` signal (not currently in the tool, based on the summary of `detectSignals()`) would
be needed to ever surface Neo4j — worth flagging as a possible future signal rather than assuming it fits
an existing one.

**Sources:** [tech-insider.org: PostgreSQL vs MySQL 2026](https://tech-insider.org/postgresql-vs-mysql-2026/), [Tasrie IT: Top 10 NoSQL Databases 2026](https://tasrieit.com/blog/top-10-nosql-databases-2026), [agentdeals.dev: Database Free Tier Comparison 2026](https://agentdeals.dev/database-free-tier-comparison-2026)

---

## 2. Cache Alternatives

`index.html`'s cache signal (if present) likely defaults straight to Redis. Real alternatives exist and
differ meaningfully on license terms and threading model — both relevant to a "which cache" decision.

| Cache | Threading model | Best for | Strength | Drawback | License/pricing |
|---|---|---|---|---|---|
| **Redis** | Single-threaded | Shared state, pub/sub, rich data structures, Lua scripting | 15+ years production-proven, massive ecosystem, richest data-type support (hashes/sorted sets/streams/HyperLogLog) | Single-threaded ceiling limits raw throughput; license moved to SSPL/RSALv2 (not OSI-approved open source) — a real consideration for orgs with open-source-license policies | Free self-hosted under SSPL/RSALv2; managed options vary |
| **Valkey** | Single-threaded | Drop-in Redis replacement for teams avoiding the licensing change | BSD-3 licensed, Linux Foundation-backed, AWS/Google/Oracle committed support, performance parity with Redis | Fewer bundled modules than Redis Stack; younger community | Free, BSD-3 |
| **DragonflyDB** | Multi-threaded | Maximum single-node throughput, Redis-protocol-compatible workloads | Reports 1–4M ops/sec (3–25x Redis) via shared-nothing multi-threaded architecture; lower P50 latency (0.25ms vs Redis' 0.3ms) | Smaller community/fewer production deployments; BSL 1.1 license is source-available, not fully open source | Free self-hosted under BSL 1.1 |
| **KeyDB** | Multi-threaded | Multi-threaded Redis with active-active replication | Active replication support, 300K–1M ops/sec | Smaller community; slower development pace than Redis itself | Free, BSD-3 |
| **Memcached** | Multi-threaded | Simple key-value caching, session stores, lowest protocol overhead | Simplest protocol, lowest per-key overhead, mature and boring (in a good way) | No data structures beyond strings, no persistence, no pub/sub/scripting | Free, BSD |

**Categorization note:** the license distinction (Redis' SSPL/RSALv2 vs. Valkey/KeyDB/Memcached's
permissive BSD-3 vs. Dragonfly's source-available BSL) is a genuinely different axis from performance —
worth its own comparison row if this ever becomes a signal, since a compliance-sensitive requirement
("avoid non-OSI licenses") would route away from Redis/Dragonfly specifically for licensing, not
performance, reasons.

**Sources:** [cachee.ai: Cache Comparison 2026](https://cachee.ai/cache-comparison-2026)

---

## 3. Messaging / Event Streaming Alternatives

`index.html`'s "messaging" category (if it maps directly to Kafka today) is the clearest case in this
whole group where the default may be actively wrong for a meaningful share of requirements — Kafka is
frequently over-provisioned for what's actually a simple task-queue need.

| Broker | Category | Best for | Strength | Drawback | Cost signal (self-hosted, 3-node) |
|---|---|---|---|---|---|
| **Kafka** | Distributed event log | Ordered event streams needing replay | Per-partition ordering, offset-based replay, 1M+ msgs/sec, rich ecosystem (Connect, Schema Registry); KRaft mode removed the ZooKeeper dependency as of Kafka 4.0 | Operationally heavy; overkill for simple task queues; partition rebalancing can spike latency | ~$1,500–5,000/mo |
| **RabbitMQ** | AMQP broker, flexible routing | Task queues with competing consumers; complex routing (direct/topic/fanout/headers) | Purpose-built for the "many workers pulling from one queue" pattern; lower p99 latency (1–50ms) than Kafka; medium ops complexity | No replay — messages are gone after consumption; per-queue (not global) ordering only; ~50K msgs/sec ceiling | ~$500–1,500/mo |
| **NATS (Core + JetStream)** | Lightweight pub/sub, optional persistence | Service-to-service RPC (Core), lightweight multi-tenant streaming (JetStream) | Sub-millisecond latency, built-in request-reply, cheap per-tenant streams — a good fit for SaaS multi-tenancy specifically | Core NATS has no persistence; JetStream throughput (50–200K msgs/sec) trails Kafka; smaller ecosystem/less mature tooling | ~$300–800/mo — cheapest of the researched self-hosted options |
| **Amazon SQS** | Managed queue (AWS-native) | Fire-and-forget task queues inside AWS, teams wanting zero ops | Fully managed, automatic scaling, built-in competing-consumer model, high-throughput FIFO up to 70K msg/sec | No replay (deleted after consumption); Standard queues only offer best-effort ordering; AWS-only; max retention 14 days | Pay-per-request — no fixed infra cost, but AWS lock-in |
| **Apache Pulsar** | Multi-region geo-replicated streaming | Compliance-driven multi-region deployments, tenant-per-topic topologies | Built-in geo-replication (same topic across regions), independently scalable broker/storage (BookKeeper) layers | Smaller community than Kafka; thinner ecosystem; multi-region ops needs specialized expertise | Self-hosted, complex; commercial support available |
| **Redpanda** | Kafka-wire-compatible event log | Sub-10ms tail-latency workloads — trading systems, real-time fraud detection | Drop-in Kafka client compatibility, C++/Seastar thread-per-core design bypasses the Linux page cache for deterministic latency | No Kafka Streams support (materialized views instead); Kafka Connect not officially supported; smaller ecosystem | Self-hosted; commercial/cloud options available |

**Categorization note — this is the one worth flagging most strongly for the audit:** Kafka and SQS solve
genuinely different problems (ordered replayable log vs. fire-and-forget task queue) and the tool
presenting one as a strict substitute for the other would be a real modeling error, structurally identical
to the Cloud-Run-isn't-a-Kubernetes-alternative issue flagged in Group 1. A "does this workload need
replay/ordering-across-consumers" signal — which the current `detectSignals()` set, per the earlier
summary, doesn't appear to have — would be the right lever if this gets wired in later; without it, a
naive port risks recommending Kafka by default when RabbitMQ/SQS/NATS would better match a simpler
requirement.

**Sources:** [backendbytes.com: Kafka vs RabbitMQ vs NATS vs SQS](https://backendbytes.com/articles/message-queue-comparison/)

---

## 4. Cross-Section Observations (pre-audit)

- **Kafka-as-fallback risk (verified against actual code, not just hypothesized).** `index.html`'s
  `pickMessaging()` already gates Kafka behind `highScale`/`realtime`/`finance` signals and correctly
  steers `startupMvp` cases toward a managed queue instead — the logic is more careful than a "default to
  Kafka" pattern. The one real gap found: its zero-signal fallback still names Kafka first. A minor,
  precise fix candidate, not a structural problem.
- **Free-tier volatility is real here too**, consistent with Group 1's finding: PlanetScale's April 2024
  free-tier removal (cited as a "cautionary case study" by the source itself) and Firebase's Feb 2026
  Cloud Storage removal from its free tier both illustrate that any pricing/free-tier claim in this
  document should be treated as point-in-time, not permanent.
- **Redis licensing is a compliance-relevant fact, not just a technical one.** Some organizations have
  open-source-license policies that would exclude SSPL/RSALv2/BSL software outright — this is a different
  kind of "drawback" than a performance tradeoff and deserves distinct treatment if ever encoded as a
  signal.

---

## 5. Audit Log

Fact-check and consistency pass performed after first draft, before marking Group 2 complete.

**Claims spot-checked:**

1. **PlanetScale free-tier removal date (April 2024)** — cited directly in the agentdeals.dev source as a
   named case study, not inferred; treated as reliable since it's presented as a specific, checkable past
   event rather than a current pricing figure that could have drifted.
2. **Kafka KRaft / ZooKeeper removal** — the backendbytes.com source states ZooKeeper was removed "as of
   Kafka 4.0." This matches known Kafka roadmap direction (KRaft as the only mode from 4.0 onward) and is
   presented as settled fact rather than a disputed claim, so no second source was pulled — flagged here
   for transparency rather than independently re-verified via a primary Apache Kafka source, unlike the
   Mesos date in Group 1 which got that treatment because it directly affected a "don't recommend this"
   claim.
3. **Redis license characterization (SSPL/RSALv2, not OSI-approved)** — this is a widely reported, stable
   fact as of the source's writing and consistent with what was already publicly known before this
   session's knowledge cutoff, so it's treated as low-risk, but is exactly the kind of claim that should
   be re-verified before being surfaced as a hard "compliance blocker" in a live product, since license
   terms and vendor positioning around them can change.

**Internal consistency checks:**

4. **Supabase/Neon categorization** — checked that the doc explicitly separates "which SQL engine" from
   "which hosting model," preventing them from being flattened into a same-tier alternative to
   MySQL/CockroachDB the way Cloud Run wasn't flattened into a same-tier Kubernetes alternative in Group
   1. Present in first draft; verified it holds.
5. **Kafka-vs-SQS scope mismatch** — checked that the messaging table's categorization note doesn't
   present these as interchangeable. Then went further than a Section-4-only note: read the actual
   `pickMessaging()` function in `index.html` rather than leaving this as a hypothesis. Verdict (see
   follow-up below): the shipped logic is already reasonably careful, with one narrow, real gap in its
   fallback case.
6. **No contradictions found** between Section 1 (databases), Section 2 (cache), and Section 3
   (messaging) — no vendor appears in more than one section with conflicting claims.

**Follow-up resolved during audit:** checked the actual `pickMessaging()` function in `index.html` (line
492) rather than leaving this as an open hypothesis. Finding: the existing logic is **better than the
Section 4 hypothesis assumed** — it already gates Kafka behind `highScale`/`realtime`/`finance` signals and
explicitly recommends "Managed queue (SQS/Pub/Sub) rather than self-managed Kafka" when `startupMvp &&
!highScale`. The one real gap: the no-signal-matched fallback (line 497) still says "Kafka for event
streaming, Redis for pub/sub-style ephemeral messaging" — Kafka as a fallback default when nothing else
fired, rather than RabbitMQ/NATS/SQS, which per this document's own research are better fits for the
generic/no-strong-signal case. This is a narrower, more precise finding than the original hypothesis: not
"the tool over-defaults to Kafka broadly," but "the zero-signal fallback specifically could point to a
lighter option first." Worth a small fix if this ever gets actioned, not a structural rewrite.

**Known limitations carried forward:**

- MongoDB pricing/benchmark data came from a source that didn't include head-to-head numbers against
  Postgres/MySQL the way the SQL comparison did — the MongoDB row is positioning-only, not benchmark-
  backed, and shouldn't be read as having the same evidentiary weight as the SQL rows above it.

**Audit verdict:** Group 2 (Data layer) is complete and internally consistent. No pricing/fact corrections
were needed this pass (unlike Group 1's Kong pricing fix), and the one open question raised by this
document's own research — whether the shipped product over-defaults to Kafka — was checked directly
against `index.html`'s code rather than left as speculation: the logic is largely sound, with one small,
concrete fallback-ordering gap identified as a fix candidate. Ready to proceed to **Group 3: AI/LLM layer
(models/vector DB/RAG/guardrails)**.
