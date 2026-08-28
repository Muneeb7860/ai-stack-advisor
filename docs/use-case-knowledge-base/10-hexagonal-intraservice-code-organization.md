# Hexagonal (Ports & Adapters) — Intra-Service Code Organization

**Status:** implemented — `pickArchitecture()` appends its `hexagonalNote` to every branch.

**Domain:** How a single service's codebase is internally organized around hexagonal/ports-and-
adapters principles — one level deeper than the system-level "monolith vs. microservices, hexagonal
internal structure" decision the tool already makes in `pickArchitecture()`. Research date:
August 2026.

## Business context

The rule engine already recommends hexagonal architecture at the system level for every
architecture-style branch (modular monolith, enterprise microservices, mid-size microservices) —
but "hexagonal" at that level just means "isolate domain logic from infrastructure," without saying
what that looks like inside one service's folder structure. This gap surfaced directly from the
user's own prior-project repository blueprint shared during this session, which named multiple
Java Spring Boot services with an implied hexagonal-core structure — this document makes that
structure explicit instead of leaving it implicit in the system-level recommendation.

## Signals / triggers

Pattern names: `hexagonal architecture`, `ports and adapters`, `clean architecture`, `onion
architecture`, `domain-driven design`, `DDD`. Code organisation: `folder structure`, `project
layout`, `how should we structure the code`, `where does business logic go`, `package by feature`,
`package by layer`, `separation of concerns`. Symptoms: `business logic in the controller`,
`framework coupling`, `hard to test`, `database logic everywhere`, `swap the database`, `mock the
repository`, `testable without a database`.

## The pattern

A hexagonal (ports & adapters) service has three layers, and the dependency rule only goes one
direction:

1. **Domain / core** — business logic and domain models with **zero framework imports**: no ORM
   decorators (`@Entity`, `@Column`), no HTTP framework types (`Request`, `Response`), no direct
   database client imports. This layer defines *interfaces* (ports) it needs — e.g. `interface
   OrderRepository { save(order): void }` — without knowing or caring how they're implemented.
2. **Ports** — the interfaces themselves, owned by the domain layer, expressing what the domain
   needs from the outside world (a repository, an email sender, a payment processor) without
   specifying how.
3. **Adapters** — concrete implementations of ports, living in an outer layer that depends inward
   on the domain (never the reverse): the actual Postgres-backed `OrderRepository` implementation,
   the actual REST controller translating HTTP requests into domain calls, the actual Stripe client
   implementing a `PaymentProcessor` port.

**The practical test that catches violations:** the domain/core layer should compile and type-check
with your web framework and database driver both uninstalled. If deleting your ORM package breaks
your domain module's build, framework leakage has already happened.

## Why this matters beyond "clean code"

- **Testability** — domain logic can be unit-tested with in-memory fake adapters (a fake
  `OrderRepository` backed by a plain array/map), no database or HTTP server needed for the tests
  that matter most.
- **Swap cost** — replacing Postgres with a different database, or REST with gRPC, touches only the
  adapter layer; the domain logic is untouched. This is what makes a later monolith-to-microservices
  split (the system-level path the tool already recommends for `startupMvp`/`smallTeam`) cheap
  instead of a rewrite — the domain boundaries were already clean.
- **Onboarding clarity** — a new engineer can read the domain layer and understand the business
  rules without wading through framework/infrastructure noise.

## Common mistakes

- **Domain objects doubling as ORM entities** — putting `@Entity`/`@Column` annotations directly on
  domain model classes couples business logic to a specific ORM/database from day one, defeating
  the whole point. Use separate persistence models mapped to/from domain models in the adapter
  layer.
- **"Ports" that are really just DTOs with no behavior** — a port should express a capability the
  domain needs (`save`, `findById`, `sendNotification`), not just be a data-shape interface.
- **Fat adapters that leak business logic** — validation or business rules implemented inside a
  controller or repository implementation instead of the domain layer; the adapter's job is
  translation only (HTTP ↔ domain call, SQL row ↔ domain object), not decision-making.
- **Treating this as all-or-nothing** — a small team doesn't need a fully generalized ports
  abstraction for every dependency on day one; the discipline that actually matters is keeping
  framework types out of the domain layer, which can be maintained incrementally even in a young
  codebase.

## Revisit triggers

- If a database, transport protocol (REST → gRPC), or third-party integration needs to be swapped
  and the change turns out to touch domain logic rather than just the adapter layer, that is the
  signature of framework types having leaked into the domain — the fix is separating persistence
  models from domain models, not deferring the pattern further.
- **"Treating this as all-or-nothing"** (see Common mistakes): a small, young codebase does not need
  a fully generalized ports abstraction for every dependency on day one — start with the one
  discipline that matters (no framework types in the domain layer) and formalize further only when
  a second engineer's onboarding friction, or an actual planned swap, makes the gap concrete.

## As implemented in `index.html`

`pickArchitecture(s)` now appends a `hexagonalNote` to every branch's `why` text, stating the
three-layer structure and the "uninstall your framework/DB driver" test explicitly, rather than
leaving "hexagonal" as an unexplained label at the system-architecture level.

## Sources

This document synthesizes the standard Ports & Adapters pattern (Alistair Cockburn's original
formulation) as applied in current (2026) practice; no single new source was needed beyond the
pattern's well-established definition, which the tool's existing `pickArchitecture()` function
already referenced by name before this document made the intra-service structure explicit.
