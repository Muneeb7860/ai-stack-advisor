# Request-Path Layer Ordering — what sits where, and which boxes are alternatives

**Status:** partial — the canonical graph assigns tiers, but ordering and mutual exclusion are never surfaced to the reader.

**Domain:** The order of the layers a request passes through from client to data, and — the part
that is most often got wrong — which apparently-sequential boxes are actually *alternatives for one
layer*. Source: `diagrams/reference-architecture/architecture-layers.svg`.

## Business context

The tool presents its recommendation as sixteen stack cards. That is the right shape for "what do I
need", but it is flat: nothing in the output tells a reader that DNS resolves before the edge, that
the API gateway sits *after* the load balancer, or that Kubernetes and a serverless container runtime
are two answers to the same question rather than two things you deploy together.

This produces a specific and observable failure: a reader assembles the recommended cards into a
mental architecture with the layers in the wrong order, or stacks alternatives that should be
exclusive. The knowledge needed to prevent that is ordering and mutual-exclusion knowledge, and the
engine currently encodes neither.

It is also the highest-frequency shape of `/api/ask` question about a generated recommendation:
"where does X sit relative to Y", "do I need both", "is this before or after the gateway".

## Signals / triggers

Ordering: `where does the gateway sit`, `before or after the load balancer`, `request flow`,
`architecture layers`, `end to end flow`, `what happens first`, `order of components`, `north-south`,
`traffic path`. Confusion pairs: `Route 53 load balancer`, `DNS vs load balancer`, `gateway vs load
balancer`, `CDN vs WAF`, `do I need both`, `Kubernetes and Cloud Run`, `OpenShift vs Kubernetes`,
`API gateway and ingress`. Platform choice: `where do my services run`, `compute platform`,
`cluster or serverless`, `scale to zero`, `cold start`. Read/write path: `analytics from the
production database`, `report off the transactional database`, `OLAP`, `data warehouse feed`,
`read replica for reporting`, `BI queries`, `separate analytics store`, `who owns the data`.

## Decision points

### A. The order, and why each step is where it is

**Client → DNS → Edge (CDN + WAF + DDoS) → Load balancer → API gateway → Compute platform →
Services → Async backbone → Data.**

The two positions that are most often inverted:

**DNS is name resolution, not traffic distribution.** A managed DNS service performs geo and
failover *routing* by handing back different answers, which is why it is mistaken for a load
balancer. It never sees a request. Calling it a load balancer leads to designs with no actual
health-checked distribution layer.

**The load balancer comes before the API gateway.** The load balancer is the network door — it
terminates TLS and distributes across healthy targets. The gateway is application-layer policy —
authentication, authorisation, rate limiting, quotas, versioning, request mediation. Policy needs a
terminated connection to inspect, so it cannot precede the thing that terminates it.

**Condition where this collapses:** a cross-cloud edge product can provide DNS, CDN, WAF and DDoS in
one service, replacing parts of layers 2 and 3. That is a legitimate simplification — the error is
stacking both it *and* the cloud-native equivalents, paying twice for one function.

### B. The compute platform is one box with mutually exclusive options

This is the layer most often drawn as a sequence when it is a choice. A managed Kubernetes service,
an enterprise Kubernetes distribution, and a serverless container runtime are **three answers to one
question** — where your services run. You pick one.

**Managed Kubernetes** — appropriate for a steady baseline load and where pod-level control matters
(sidecars, daemon sets, a service mesh). No cold start; you pay for idle nodes.

**Enterprise Kubernetes distribution** — the same layer with a vendor-supported enterprise wrapper,
stricter security defaults and bundled CI/CD. Chosen for an on-prem or hybrid mandate, or where
vendor support is a procurement requirement. Heavier and licensed.

**Serverless containers** — no cluster and no nodes, scaling to zero. Appropriate for bursty or
spiky traffic and stateless, low-ops workloads. The trade-off is cold starts, which are materially
worse for JVM-based stacks; mitigations are a minimum-instance floor or an ahead-of-time-compiled
runtime.

The framing that prevents the error: **these are alternatives for one box, not sequential steps.**

### C. Services run *on* the compute platform — they are not a peer layer

The bounded contexts are a layer below the platform in the diagram because they are deployed onto
it, not chained after it. Service-to-service security and traffic management wrap this layer via the
mesh rather than sitting between it and the platform.

### D. Synchronous stays in-layer; asynchronous drops to the backbone

Calls between services in the same layer are synchronous and direct. Anything crossing a bounded
context asynchronously goes through the event backbone — with the transactional outbox pattern and
change-data-capture as the mechanism that gets an event onto a topic without a distributed
transaction, and an orchestrator coordinating multi-step workflows.

### E. Each service owns its store, and analytics is a separate sink

Transactional stores are per-service. Cache and session state is a separate tier. A document store
is added only against a *named* access pattern rather than by default. The analytics store is fed
from the async backbone — never by querying the transactional databases directly, which couples
reporting load to the serving path.

### F. Cross-cutting concerns wrap every layer and are not steps in the flow

Security and secrets, observability, delivery, and governance apply at every layer. Drawing them as
a step in the request path is a category error — they are a column beside the flow, not a box in it.

Two anti-duplication rules belong here. On telemetry: instrument once with a vendor-neutral
standard, then — **one backend per signal class — never two backends for the same signal.** That is
the principle; routing different signal *classes* (application traces, infrastructure metrics, logs,
security analytics) to products suited to each is a refinement of it, not an exception to it, and
`15-observability-and-audit-logging.md` §C works that through. On policy: treat it as code inherited
across environments rather than reimplemented per environment.

## Anti-patterns

**Treating DNS as a load balancer.** Produces an architecture with no health-checked distribution
layer, and a failover story that depends entirely on record TTLs.

**Putting the API gateway in front of the load balancer.** Application-layer policy cannot inspect a
connection that has not been terminated, and the gateway becomes a single point of failure with no
distribution behind it.

**Stacking a cross-cloud edge product on top of the cloud-native CDN and WAF.** Two products
performing one function, paid twice, with two rule sets to keep consistent.

**Deploying Kubernetes *and* a serverless container runtime for the same services.** They are
alternatives. Running both for one workload class means operating two platforms and getting the
worst property of each.

**Choosing serverless containers for a JVM service without addressing cold start.** The cold-start
penalty is worst exactly where the runtime is heaviest; unaddressed, it presents as intermittent
latency that load testing at steady state will not reproduce.

**Adding a document store with no named access pattern.** "We might need flexible schema" is not an
access pattern. Without one, it is an additional operational burden and a second consistency model
for no measured benefit.

**Feeding analytics from the transactional database.** Couples reporting load to the serving path,
and makes a heavy query a production-latency incident.

**Shipping telemetry to several observability backends at once.** Instrumentation is worth doing
once; fan-out to multiple vendors multiplies cost and splits the investigation surface.

## Reference implementations

The source diagram presents the layers with per-cloud equivalents named side by side for AWS, Azure
and GCP — the point being that the *ordering* is invariant across providers even though every
product name changes. The cross-cutting column covers security and secrets, observability, delivery
and governance, and it is drawn beside the stack rather than within it for the reason given in
decision point F.

## Revisit triggers

- **§A ("condition where this collapses"):** if a cross-cloud edge product already provides DNS,
  CDN, WAF and DDoS in one service, layers 2 and 3 legitimately collapse into it — the error to
  revisit is stacking both that product and the cloud-native equivalents, paying twice for one
  function.
- **§B (compute platform):** this is not a "when to move on" trigger like most of this corpus — it's
  a reminder that managed Kubernetes, an enterprise Kubernetes distribution, and serverless
  containers are mutually exclusive answers to one question. Revisit the choice itself (not "add
  another layer") if the original driver changes — e.g. an on-prem/hybrid mandate appearing after a
  serverless choice was made, or a workload's traffic shape moving from bursty to steady baseline.

## As implemented in `index.html`

Partially, and structurally rather than as reasoning. `buildCanonicalArchitectureGraph()` assigns
nodes to tiers, and the C4 export maps knowledge-base categories onto ui/app/data/platform layers —
which is the same idea at lower resolution. What is absent is (a) any statement of ordering in the
user-facing output, and (b) any notion of mutual exclusion: the sixteen stack cards are presented as
a flat set, so nothing communicates that the compute-platform options are alternatives. Wiring this
in would most naturally be an ordering annotation on the Flow View and a trade-off card for the
compute-platform choice.

## Sources

**Primary source is the project owner's own architecture work** —
`diagrams/reference-architecture/architecture-layers.svg`, authored as a reference architecture. The
layer ordering, the DNS-is-not-a-load-balancer and gateway-after-load-balancer corrections, and the
one-box-three-alternatives framing for the compute platform are that author's.

Per-cloud product names are identified as equivalents, not recommendations; this document makes no
comparative claim between providers.

**Unsourced claims to resolve before `/api/ask` cites them as fact:** the cold-start severity for
JVM workloads on serverless container runtimes is stated qualitatively and would need a benchmark
citation before being quoted with any specific figure, and the mitigations named (minimum instances,
ahead-of-time compilation) are directionally standard but unbenchmarked here.
