# Observability & Audit Logging — instrument once, alert on symptoms, audit separately

**Status:** partial — `pickAuditLogging()` now covers §H (audit logging as a separate immutable
pipeline). `pickObservability()` still only selects an APM vendor; alerting policy, trace
propagation, sampling, and cardinality (the rest of the reasoning below) remain unimplemented.

**Domain:** What to emit, where it goes, what wakes a human, and why audit logging is a separate
system rather than a log level. Source:
`diagrams/reference-architecture/architecture-observability-v2.svg`.

## Business context

The engine's entire observability reasoning is vendor selection: `pickObservability()` returns
"OpenTelemetry + <vendor>" and stops. Measured against the whole repository and this corpus before
this document existed: `error budget` 0 occurrences, `burn rate` 0, `traceparent` 0, `WORM` 0,
`tail-based sampling` 0, `RED`/`USE` as named methods 1. The tool could tell a user *which* APM
product to buy and nothing about what to do with it.

That gap matters most for the two questions a regulated reviewer actually asks — "how would you know
this was broken?" and "can an administrator delete the audit trail?" — neither of which a vendor
name answers.

## Signals / triggers

Monitoring/alerting: `observability`, `monitoring`, `alerting`, `alert fatigue`, `on-call`, `paging`,
`SLO`, `SLI`, `error budget`, `burn rate`, `golden signals`, `RED metrics`, `USE method`, `dashboards`,
`runbook`, `incident response`, `MTTR`. Telemetry: `OpenTelemetry`, `OTel`, `instrumentation`,
`metrics logs traces`, `three pillars`, `distributed tracing`, `trace ID`, `traceparent`, `span`,
`correlation ID`, `sampling`, `tail-based sampling`, `collector`, `cardinality`, `structured
logging`, `log volume`, `log retention`. Outside-in: `synthetic monitoring`, `black-box monitoring`,
`uptime check`, `availability probe`, `canary probe`, `is the site up`. Audit: `audit log`, `audit
trail`, `immutable log`, `WORM`, `tamper-evident`, `who did what`, `retention years`, `regulator
evidence`, `SIEM`, `activity log`.

## Decision points

### A. Monitoring and observability are different questions

**Monitoring** answers *is it healthy?* — known questions, fixed dashboards and alerts.
**Observability** answers *why?* — unknown questions, explored against telemetry after the fact.
Logging is one input to both, not a strategy in itself.

The practical consequence: a system can be perfectly monitored and unobservable. Dashboards that
answer every question you thought of in advance tell you nothing about the outage you did not.

### B. Three signals, instrumented once

Metrics (cheap, the basis for alerting), logs (forensic detail, structured JSON), traces (one
request's journey across services). Emit all three through one vendor-neutral instrumentation
standard, and put a collector between the application and the backends.

The collector is where backends get swapped, where attributes are normalised, and where sampling
decisions are made — **without touching application code**. That property is the whole reason to run
one, and it is what makes the vendor choice reversible rather than a lock-in.

### C. The backend rule — principle first, then the refinement

**The principle: one backend per signal class — never two backends for the same signal.** Shipping
the same metrics to two products doubles cost, splits the investigation surface, and guarantees the
two disagree during the incident when you can least afford to reconcile them.

**The refinement:** "one backend" does not mean one *product* for everything. Signal classes have
genuinely different shapes, and it is normal and correct to route them differently — an APM product
for application traces and dependency mapping, a metrics stack for infrastructure and orchestrator
telemetry, a log store for structured logs, and a SIEM for security analytics. That is one backend
*per class*, which satisfies the principle. What violates it is two APM products, or the same
metrics scraped into two systems in parallel.

Stated as a test a reader can apply: *for any single signal, can you name exactly one system of
record?* If yes, the split is a refinement. If no, it is duplication.

**Condition where the refinement collapses back to the principle:** below a certain size the
operational cost of four backends exceeds the benefit of specialisation, and one product covering
all four classes adequately beats four covering them well. The split is justified by scale and by
having someone to operate it, not by completeness.

### D. Inside-out telemetry is blind to total failure

Application telemetry describes how the system feels about itself. If the application is fully down
it emits nothing at all — and dashboards fed only by inside-out telemetry look calm during a total
outage, because silence and health are indistinguishable to them.

Synthetic (black-box) probes hit the public entry point on a schedule from outside. They are the
only signal that fires when everything else has stopped. This is what catches "users cannot log in"
while every internal dashboard is green.

### E. Correlation across the async hop is the microservices-hard part

One trace ID must follow a request through every service *and* across the message bus. Synchronous
hops propagate context automatically via the standard trace header. **Asynchronous hops do not** —
trace context has to be injected into the message's own headers and extracted by the consumer, or
the trace ends at the bus.

When that breaks, the symptom is specific and expensive: "payment is slow" never resolves to
"because the scoring service timed out", because the two halves of the request are two unrelated
traces. This is the single highest-value thing to get right in a distributed system's telemetry, and
it is the thing most often discovered missing during an incident rather than before one.

### F. Alert on symptoms, not causes

Alert on what a user experiences — error rate, latency, failed logins — not on resource utilisation
that may harm nobody. CPU at 80% is a dashboard; checkout failing is a page.

Formalise it as an SLO with an error budget and **alert on burn rate**: fast burn pages a human,
slow burn raises a ticket. Tier severity explicitly — page for user impact, ticket for degradation,
dashboard-only for informational.

Two named methods worth stating because they prevent argument about what to measure: **RED** (rate,
errors, duration) for request-driven services, and **USE** (utilisation, saturation, errors) for
resources like nodes, pools and queues.

Every alert carries a runbook link and an escalation policy. **A page nobody knows how to action is
noise**, and noise is how on-call stops reading pages.

### G. Three things that silently break in production

These share a shape: each looks correct in a diagram and in a staging environment, and fails only at
production scale or under production data — which is why they belong together as conditions rather
than as footnotes.

**Tail-based sampling needs a gateway tier, not per-node agents.** Deciding to keep a trace *after*
seeing whether it errored or ran slow requires every span of that trace to reach the same collector
instance. A per-node agent deployment cannot guarantee that, so tail sampling silently keeps the
wrong traces — it appears to work, and the traces you most needed are the ones it dropped. The
deployment requirement is a gateway tier with trace-ID-aware routing in front of the exporters.

**PII redaction belongs at the service, with the collector as a safety net.** Redacting only in the
collector means the data was already written to the container's stdout and already crossed the
network before anything removed it. Both of those are places a regulator counts as disclosure. The
control is at the emitting service; the collector catches what the service missed. For regulated
data this is the difference between a control and a gap, not a matter of defence in depth.

**Metric cardinality is the standard way the bill explodes.** Every distinct combination of label
values is a separate time series. Putting a user ID, a request ID, a full URL path or a raw error
string into a metric label multiplies series count without bound — it degrades the metrics backend
and produces a bill nobody can attribute after the fact. High-cardinality values belong in logs and
trace attributes, which are built for them; metrics labels are for bounded dimensions.

### H. Audit logging is a different system, not a log level

Application logs are sampled, retained for weeks, exist for debugging, and must have PII kept out of
them. Audit events — *who did what, to what data, when* — are **complete (never sampled), retained
for years, immutable, and tamper-evident**. They answer a regulator, not an engineer.

They therefore travel a separate pipeline that bypasses the application logging path entirely, and
land in write-once storage. Infrastructure-level and orchestrator-level audit trails belong in the
same destination, so "who changed the cluster" and "who read the customer record" are answerable
from one place.

The line that makes this concrete to a reviewer: **an audit log an administrator can delete is not
an audit log.** Immutability is the property being bought; retention and completeness are how it is
demonstrated.

**Condition:** enforce the shipping of these logs by policy rather than by convention. A diagnostic
setting a team can forget to enable is a control that exists in the diagram and not in the estate.

**Ownership note:** this section owns *how* audit events are stored — the pipeline, immutability,
retention. It does not enumerate *what produces* them. `18-access-control-four-planes.md` §H is the
producer side: every authentication, PIM elevation, workload token issuance, and privileged data
query is an audit event that lands here, without this document needing to restate what generated it.

### I. Observability cost is a real architecture input

Telemetry is routinely a top-three cloud line item, driven mostly by log volume and retention rather
than by metric or trace count. That collides directly with decision point H and with security
analytics: a SIEM wants long retention over broad data, and cost wants the opposite.

Resolve it deliberately by tiering — short hot retention for debugging, long cold or archive
retention for audit and security — rather than by discovering the bill. See
`09-cost-estimation-methodology.md` for how this corpus reasons about cost bands generally.

## Anti-patterns

**Shipping the same signal to two backends "so we can compare".** Doubles cost, splits the
investigation, and the two will disagree mid-incident. See decision point C.

**Alerting on resource utilisation by default.** Produces pages nobody can action and trains on-call
to ignore the channel — after which the one real page is also ignored.

**Treating audit logging as a log level.** `logger.info("user viewed record")` into the application
log stream is sampled, deletable, and mixed with debug output. It is not an audit trail regardless
of what it contains.

**Putting PII in application logs and planning to redact later.** Once written, it is written;
retroactive redaction across a log store is expensive at best and incomplete at worst.

**Unbounded metric labels.** See decision point G — user IDs and URLs in labels is the standard
cardinality explosion.

**Relying only on inside-out telemetry.** A total outage produces silence, and silence looks like
health on a dashboard that has no synthetic probe.

**Instrumenting per-vendor rather than per-standard.** Vendor SDKs in application code make the
backend choice irreversible, which is the one thing a collector exists to prevent.

## Reference implementations

The source diagram models this on Azure: services on AKS emitting through an OTel collector into
Azure Monitor — Application Insights for application traces and APM, Log Analytics as the log store,
managed Prometheus and Grafana for infrastructure and cluster metrics, and Microsoft Sentinel for
security analytics on the same workspace. Availability tests provide the outside-in probe. The audit
path is separate: Azure Activity Log and the Kubernetes API audit log into immutable storage with
multi-year retention.

The pattern is provider-agnostic. The signal classes, the collector's position, the async
propagation requirement and the separate audit path are invariant; only the product names change.

## Revisit triggers

- `pickAuditLogging()`'s minimal-project floor (application logs only) holds until this system
  handles real user data or gains a compliance obligation — either one is the trigger to add a
  separate immutable audit pipeline, not a scheduled migration.
- If "who did what, to what data, when" is ever asked by an actual auditor, regulator, or customer
  contract and the honest answer requires reconstructing it from sampled, weeks-retained application
  logs, that gap is itself the revisit trigger — it means the audit pipeline should have already
  existed.

## As implemented in `index.html`

Partially. `pickAuditLogging()` (its own "Audit Logging" stack card) now implements §H: a minimal,
non-regulated project is told application logs are enough, a compliance/finance/healthcare/large-
enterprise requirement gets a separate immutable WORM-storage audit pipeline distinct from
application logs, and the middle case gets application logs today with an explicit revisit trigger —
closing the highest-value gap this document identified. `pickObservability()` still only chooses an
APM vendor from team-skill and enterprise/compliance signals and emits a single "OpenTelemetry
(instrumentation standard) + <vendor>" string; there is still no reasoning about alerting policy,
SLOs, trace propagation, sampling, or cardinality, and `pickGovernance()`'s audit-log mentions remain
about access control rather than the immutable trail (that distinction is now `pickAuditLogging()`'s
job, not `pickGovernance()`'s).

The natural next wiring points are a trade-off card for the backend-per-signal-class rule and an
observability section extension covering alerting policy, sampling, and cardinality.

## Sources

**Primary source is the project owner's own architecture work** —
`diagrams/reference-architecture/architecture-observability-v2.svg`, authored for a BFSI architecture
review. The monitoring-versus-observability framing, the inside-out/outside-in distinction, the
async-hop correlation point and the audit-separation argument are that author's.

Decision point G is **not** from the source diagram — it was added during review of it. The diagram
hedges the collector as "(DaemonSet / gateway)" without stating that tail sampling requires the
gateway form, marks logs "PII redacted" at the service while also listing redaction as a collector
processor without resolving which is the control, and does not mention cardinality at all. All three
are recorded here as conditions because each fails silently in production.

RED and USE are established named methods attributed to their originators in the literature; this
document names them without citation and does not reproduce their definitions beyond the expansions
given.

**Unsourced claims to resolve before `/api/ask` cites them as fact:** "top-three cloud line item"
for observability spend is a widely-repeated industry figure stated here without a source; the
burn-rate alerting model derives from published SRE practice but no specific multi-window threshold
is recommended here, and any specific figure would need one; and the claim that a given provider's
storage offers genuine write-once immutability must be verified per provider before being repeated
to a user as a compliance guarantee.
