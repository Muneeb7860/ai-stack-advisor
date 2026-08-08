# Event-Driven Distributed Transactions (Saga / CQRS)

**Domain:** Multi-step workflows spanning separate services/databases with no single ACID
transaction — the classic e-commerce checkout/order-fulfillment case (reserve inventory → charge
payment → book shipping). Research date: August 2026.

## Business context

Directly extends the reasoning already validated in this project's live-quiz-app fix and the
API-gateway-splitting trade-off card — any product decomposing a multi-step business process across
independently-owned services needs an explicit answer to "how do we keep this consistent without
one giant transaction," not an ad hoc retry loop.

## Signals / triggers

`checkout`, `order processing`, `order fulfillment`, `payment then inventory then shipping`,
`distributed transaction`, `cross-service transaction`, `saga`, `compensating transaction`,
`rollback across services`, `multi-step workflow across services`, `eventual consistency`,
`event-driven architecture`, `domain events`, `outbox pattern`, `long-running transaction`,
`workflow engine`, `state machine`, `step functions`, `temporal workflow`.

## Decision points

### A. Choreography vs. Orchestration Saga

**Choreography** — each service publishes domain events (OrderCreated → InventoryReserved →
PaymentCharged → ShipmentBooked); the next service reacts. No central coordinator. Wins for a small
number of steps (2–4 services), high service autonomy, low coupling. Loses past ~4-5 steps: flow
logic gets smeared across services, hard to trace, cyclic-dependency risk.

**Orchestration** — a dedicated saga orchestrator (state machine) issues commands and tracks state
explicitly. Wins for complex workflows, multiple compensation paths, and where auditability/
visibility of "where is this order stuck" matters. The orchestrator becomes a critical component and
a potential coupling point. Named tools: **Temporal.io** (durable execution, automatic retries/
compensation, strong for long-running failure-heavy sagas) and **AWS Step Functions** (serverless
state machines, good AWS-native fit). In 2026 practice, most production e-commerce checkout flows
favor orchestration via a durable-workflow engine over hand-rolled state machines.

### B. Transactional outbox + CDC for reliable event publishing

Writing to your own DB and then separately publishing to Kafka is the **dual-write problem** — a
crash between the two leaves state inconsistent. The fix: write the event to an outbox table in the
same local transaction as the business update, then use **Debezium** CDC to tail the DB log and
publish to Kafka reliably, exactly matching what was committed. This is close to mandatory for
choreography-style sagas built on Kafka.

### C. CQRS — when it's justified vs. overkill

CQRS (separate read/write models) earns its complexity when read and write workloads have very
different shapes/scale (e.g. high-volume order search/reporting vs. low-volume order writes), or
when already event-sourcing and needing materialized read views. Overkill for simple CRUD services
with no read/write asymmetry.

### D. Event sourcing as complement or alternative

Event sourcing (storing state as an append-only event log rather than current-state rows) pairs
naturally with sagas. Multiple practitioners warn it's frequently oversold as a default
microservices pattern — real complexity (schema evolution, replay tooling, snapshotting) unjustified
unless full audit history, temporal queries, or true event-driven state reconstruction is needed.
**Axon Framework** bundles CQRS + event sourcing + saga orchestration for JVM shops wanting an
integrated stack.

## Anti-patterns

- **Two-phase commit (2PC) across microservices** — technically possible (XA transactions) but
  rejected in practice: requires synchronous locking across service boundaries, kills availability
  during partition/failure, doesn't work with most modern brokers or polyglot persistence.
  Consensus: don't use 2PC for microservices.
- **Dual writes without an outbox** — writing to DB then publishing to a broker as two separate
  operations creates a window where a crash causes silent data loss or a ghost event.
- **Over-applying CQRS/event sourcing to simple CRUD** — adds operational and cognitive overhead
  with no corresponding benefit.
- **Choreography sagas that grow past a handful of steps with no central visibility.**
- **Missing/incomplete compensating transactions** — forgetting to design the "undo" path for each
  step.

## Reference implementations

- **Temporal.io** — widely documented for saga/durable-execution workflows in order/payment
  processing.
- **AWS Step Functions** — explicit AWS reference architecture for saga orchestration in
  order-fulfillment workflows.
- **Axon Framework / AxonIQ** — JVM ecosystem reference combining CQRS, Event Sourcing, and Saga
  orchestration.
- **Debezium (Red Hat)** — the de facto reference CDC implementation for the outbox pattern.
- **microservices.io** (Chris Richardson) — the original canonical source for the Saga pattern
  definition used across the industry.

## As implemented in `index.html`

Wired into `pickTradeoffs(s)` via the `sagaWorkflow` signal — recommends orchestration (Temporal.io
or AWS Step Functions) for enterprise/large-team/finance profiles, choreography for smaller/simpler
flows, with the transactional outbox pattern and a hard warning against 2PC included in every case.

## Sources

- [microservices.io — Pattern: Saga](https://microservices.io/patterns/data/saga.html)
- [Bytebytego — Saga Pattern Demystified: Orchestration vs Choreography](https://blog.bytebytego.com/p/saga-pattern-demystified-orchestration)
- [Temporal — Mastering Saga Patterns for Distributed Transactions](https://temporal.io/blog/mastering-saga-patterns-for-distributed-transactions-in-microservices)
- [AWS Prescriptive Guidance — Saga Orchestration Pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/saga-orchestration.html)
- [Confluent — Understanding the Dual-Write Problem and Its Solutions](https://www.confluent.io/blog/dual-write-problem/)
- [Streamkap — The Outbox Pattern Explained](https://streamkap.com/resources-and-guides/outbox-pattern-explained)
- [Thorben Janssen — Distributed Transactions: Don't Use Them for Microservices](https://thorben-janssen.com/distributed-transactions-microservices/)
- [AWS Prescriptive Guidance — Decompose Monoliths into Microservices Using CQRS and Event Sourcing](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/decompose-monoliths-into-microservices-by-using-cqrs-and-event-sourcing.html)
- [Medium — Stop Overselling Event Sourcing as the Silver Bullet](https://medium.com/swlh/stop-overselling-event-sourcing-as-the-silver-bullet-to-microservice-architectures-f43ca25ff9e7)
