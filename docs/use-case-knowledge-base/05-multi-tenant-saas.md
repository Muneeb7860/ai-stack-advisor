# Multi-Tenant SaaS

**Status:** implemented — wired into `pickTradeoffs()` via the `multiTenant` signal.

**Domain:** One codebase and shared infrastructure serving many customer organizations
("tenants"), each with data and users that must never be visible to another tenant. Research date:
August 2026.

## Business context

Relevant for any B2B SaaS product serving multiple customer organizations from shared
infrastructure — a distinct and commonly under-specified requirement set from a single-tenant
consumer app, with data-isolation guarantees that go beyond ordinary access control.

## Signals / triggers

`multi-tenant`, `multitenant`, `multi-tenancy`, `SaaS for multiple companies/organizations`, `B2B
SaaS platform`, `white-label`, `per-customer data isolation`, `tenant isolation`, `each customer's
own workspace/org/account`, `serve multiple clients from one platform`, `customer-specific
branding`, `organization-based access control`, `data residency per customer`, `enterprise customers
need dedicated instance`, `subdomain per customer`, `SSO per organization`, `noisy neighbor`,
`row-level security`.

## Decision points

### A. Isolation model — Silo vs. Pool vs. Bridge (AWS SaaS Lens terminology)

**Silo** — dedicated infrastructure (VPC, compute, DB) per tenant. Strongest isolation, easiest
compliance story (HIPAA/FedRAMP/finance), highest cost/operational overhead; doesn't scale to
thousands of tenants.

**Pool** — fully shared compute and shared storage/schema, tenant identity carried as a
discriminator column. Cheapest and most scalable, weakest isolation, hardest to prevent
noisy-neighbor effects.

**Bridge/hybrid** — shared compute with logically isolated data (per-tenant schema, RLS policies,
or partitioning), sometimes with targeted silo-ing for specific high-value/regulated tenants layered
on a mostly pooled system. Most production SaaS in 2026 land here.

### B. Database strategy

- **Database-per-tenant** — strongest isolation, simplest per-tenant backup/restore and data
  residency, but doesn't scale past low hundreds/thousands of tenants (connection-pool exhaustion,
  migration fan-out, per-DB fixed overhead).
- **Schema-per-tenant** — middle ground, one instance, N schemas; schema-count sprawl becomes a
  migration/connection-pooling problem at scale.
- **Shared-schema + `tenant_id` + Postgres Row-Level Security (RLS)** — single schema, every table
  has a `tenant_id` column, RLS policies enforce `tenant_id = current_setting('app.tenant_id')` at
  the database layer so isolation holds even if application code forgets a `WHERE` clause. **The
  dominant 2026 pattern** for high-tenant-count SaaS because it scales cheaply and still gives
  DB-enforced (not just app-enforced) isolation.
- Justification by scale: shared-schema+RLS for thousands of small/mid tenants (typical PLG/B2B
  SaaS); schema-per-tenant for hundreds of mid-size tenants needing customization/backup
  granularity; database-per-tenant or full silo for a small number of large enterprise or regulated
  tenants demanding contractual isolation/residency guarantees.

### C. Tenant-aware caching and rate-limiting

Cache keys and rate-limit buckets must be namespaced by `tenant_id` (Redis key prefixes, per-tenant
token buckets) to prevent one tenant's cache entries or throughput from starving another. Per-tenant
quotas/throttling at the API gateway layer is the standard mitigation for noisy neighbors in pooled
compute.

### D. Blast-radius containment via cell-based architecture

At very large scale, companies partition the entire pooled fleet into independent "cells" (each a
full stack instance serving a subset of tenants) so a failure/overload in one cell can't cascade to
all tenants.

## Anti-patterns

- **Shared-schema without enforced RLS** — relying solely on application code to append `WHERE
  tenant_id = ?` is the single most common cause of cross-tenant data leaks: one missed clause, one
  buggy ORM query, or one raw SQL escape hatch exposes another tenant's data. DB-level enforcement
  (RLS or separate schemas) is treated as mandatory, not optional, by OWASP and multiple production
  write-ups.
- **Over-engineering silo-per-tenant for a mass-market product** — standing up dedicated DB/VPC per
  tenant for thousands of small SMB customers multiplies infra cost and ops burden without a
  compliance reason to justify it.
- **Ignoring the noisy-neighbor problem** — pooling compute/DB without per-tenant rate limits,
  connection caps, or query timeouts lets one large/misbehaving tenant degrade the experience for
  everyone else.
- **Mixing isolation strategies inconsistently across services** — e.g. RLS on the primary DB but
  no tenant scoping in caches, search indexes, logs, or background job queues, leaking tenant
  boundaries through side channels.

## Reference implementations

- **Salesforce** — the canonical large-scale pooled multi-tenant architecture: a single shared
  database schema (metadata-driven, virtual per-tenant schemas) serves all customers.
- **Slack** — migrated from a purely pooled/sharded model to a cell-based architecture specifically
  to contain blast radius and improve reliability at scale.
- **Citus (Microsoft/Azure Postgres)** — well-known reference pattern for multi-tenant apps on
  distributed Postgres, including guidance on moving away from schema-per-tenant at scale.
- **Neon and Nile** — both publish current (2025–2026) reference architectures specifically for
  RLS-based and database-per-tenant Postgres multi-tenancy.

## Revisit triggers

- **§A/§B (isolation and DB strategy):** as tenant count and mix change, the right answer changes
  with it — shared-schema+RLS for thousands of small/mid tenants, schema-per-tenant once mid-size
  tenants demand backup/customization granularity, database-per-tenant or full silo once a small
  number of large enterprise or regulated tenants demand contractual isolation. A growing enterprise
  segment inside an otherwise-pooled system is the signal to revisit, not a wholesale migration.
- **§B (database-per-tenant specifically):** if connection-pool exhaustion or migration fan-out
  starts becoming a recurring operational problem, database-per-tenant has hit its scaling ceiling
  (low hundreds/thousands of tenants) — this is the point to move toward schema-per-tenant or
  shared-schema+RLS, not add more database instances.
- **§D (cell-based architecture):** if a single tenant's overload or failure has started visibly
  affecting other tenants on shared pooled compute, that blast-radius leak is the trigger for
  cell-based partitioning — not a scale number alone.

## As implemented in `index.html`

Wired into `pickTradeoffs(s)` via the `multiTenant` signal — recommends the bridge model (shared
compute, Postgres RLS-enforced tenant isolation) as the default, with targeted silo-ing called out
as an exception for specific large/regulated tenants rather than an all-or-nothing switch.

## Sources

- [AWS Well-Architected — SaaS Lens: Silo, Pool, and Bridge Models](https://docs.aws.amazon.com/wellarchitected/latest/saas-lens/silo-pool-and-bridge-models.html)
- [OWASP — Multi Tenant Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html)
- [Redis — Data Isolation in Multi-Tenant SaaS](https://redis.io/blog/data-isolation-multi-tenant-saas/)
- [Nile — Shipping Multi-Tenant SaaS Using Postgres Row-Level Security](https://www.thenile.dev/blog/multi-tenant-rls)
- [Neon — Multi-Tenancy and Database-per-User Design in Postgres](https://neon.com/blog/multi-tenancy-and-database-per-user-design-in-postgres)
- [Citus Docs — Multi-Tenant Schema Migration](https://docs.citusdata.com/en/v7.4/develop/migration_mt_schema.html)
- [Slack Engineering — Slack's Migration to a Cellular Architecture](https://slack.engineering/slacks-migration-to-a-cellular-architecture/)
- [Salesforce Developer Wiki — Multi Tenant Architecture](https://developer.salesforce.com/ja/wiki/multi_tenant_architecture)
- [SSOJet — Tenant Isolation Strategies: Infrastructure Patterns for Multi-Tenant SaaS](https://ssojet.com/blog/tenant-isolation-strategies-infrastructure-patterns-multi-tenant-saas)
