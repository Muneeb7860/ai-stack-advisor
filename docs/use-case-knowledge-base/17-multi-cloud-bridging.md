# Multi-Cloud Bridging — a constraint, not a preference

**Status:** partial — a new `multiCloudMentioned` signal plus `pickMultiCloudBridging()` now reason
about the constraint-first framing, IaC-source, interconnect-tier, and federation guidance (decision
points A–E) once two distinct cloud providers are named. `pickCloud()` still always returns exactly
one provider — the split itself is not modeled structurally, only named in the pick's prose.

**Domain:** How to bridge two different cloud providers when a hard constraint forces it — the
physical link between networks that do not otherwise share a backbone, cross-cloud identity
federation, and the latency/cost tax that comes with the split. Source:
`diagrams/reference-architecture/architecture-multicloud.svg`.

**Ownership note:** `13-private-network-egress-control.md` owns the network boundary *within* one
cloud — what stays on a private link and what has to cross to the public internet. This document
owns the disjoint problem: bridging two providers whose networks do not otherwise touch at all,
which needs an actual physical or virtual link provisioned between them before anything private is
possible, plus identity federation across a trust boundary neither provider owns. Neither document
restates the other. §E's federation is specifically the *cross-cloud* case — the same pattern
applied *within* one cloud (a pod reaching its own cloud's database or secret store) is owned by
`18-access-control-four-planes.md` §F, which defers back here the moment a second provider is
involved.

## Business context

Nothing in the engine or corpus reasons about a split-provider architecture at all — `pickCloud()`
is structurally single-answer. That gap matters specifically because the honest first thing to say
about a multi-cloud design is that it is usually the wrong default: the question a reviewer asks
first is not "how do you bridge them" but "why are you doing this instead of picking one," and a
tool with no reasoning here cannot help answer either question.

## Signals / triggers

Multi-cloud shape: `multi-cloud`, `multicloud`, `two cloud providers`, `GCP and Azure`, `AWS and
GCP`, `compute in one cloud data in another`, `hybrid cloud providers`, `cloud-to-cloud`. Drivers:
`data residency law`, `org mandate two clouds`, `M&A different clouds`, `avoid vendor lock-in`,
`why are we using two clouds`. Bridging: `cross-cloud link`, `cross-cloud latency`, `cross-cloud
egress`, `interconnect between clouds`, `Partner Interconnect`, `Cloud Interconnect ExpressRoute`,
`VPN between clouds`, `non-overlapping CIDR`. Identity: `workload identity federation`,
`cross-cloud authentication`, `federate to Entra ID from GCP`, `no stored cloud secret`.

## Decision points

### A. Lead with the constraint, not the design

A split-provider architecture is justified by a hard constraint — a data-residency law binding one
provider, an organisational mandate (frequently post-acquisition, inheriting two estates), or a
specific managed service only one provider offers. It is not justified by "avoiding lock-in" as a
general principle; that trades a real, named risk for a smaller, harder-to-name one, while paying
the ongoing cost described below every day regardless.

**The honest framing, stated first, before any diagram:** left to choose freely, compute and data
belong in the same cloud. Every call that crosses between providers costs latency and (usually)
egress fees that a single-cloud design does not pay at all. A design that hides this trade-off
behind the diagram is a worse answer than one that states it and defends it.

### B. The latency floor is physics, not configuration

Within the same geographic region, a well-provisioned cross-cloud link adds on the order of a few
milliseconds versus an intra-cloud call — a real but usually absorbable tax. Crossing regions in
addition to crossing providers compounds that by an order of magnitude or more, and is felt on every
synchronous call. The practical rule: co-locate compute and data in one geographic region even when
they sit in two different clouds, and treat "which region" as a decision made once, jointly, for both
providers — not independently per provider.

**The reframe worth stating explicitly:** a cross-cloud hop is not something to *optimise* — tuning
cannot remove speed-of-light and inter-network-hop latency. It is something to *minimise the count
of*, and to make asynchronous wherever the call does not need an immediate answer.

### C. One infrastructure-as-code source, two providers

A single Terraform (or equivalent) configuration invoking two providers — one resource graph, one
state, one review process, applied across both clouds — does not make the providers interchangeable,
but it does keep the parts that make a multi-cloud design reviewable in one place: the cross-cloud
link itself, the workload-identity federation configuration, and the firewall/allowlist rules
governing what may cross. Splitting these across two separate IaC pipelines (one per cloud, reviewed
independently) is how the cross-cloud boundary — the highest-risk part of the whole design — ends up
with no single reviewer who can see both sides of it at once.

### D. Three ways to bridge two networks — chosen by volume and sensitivity, not by convenience

**Public endpoint with mTLS and IP allowlisting** — the traffic transits the public internet with
mutual-TLS and a source-IP allowlist as the controls. Cheapest and fastest to stand up (minutes), but
latency is variable and the traffic is, physically, on the internet. Defensible only for low-volume,
non-sensitive data — not for a regulated institution moving real customer data between clouds.

**Site-to-site VPN (IPsec)** — a private routing path layered over the public internet backbone.
Meaningfully more private than the first option, but throughput is capped per tunnel and latency,
while private, is not predictable in the way a dedicated circuit is. The workable middle ground when
volume is moderate and full dedicated interconnect is not yet justified.

**Dedicated interconnect** (e.g. a cloud's own Partner/Dedicated Interconnect terminating into the
other cloud's equivalent, such as ExpressRoute) — a physical or carrier-provisioned circuit off the
public internet entirely. Lowest and most *predictable* latency, SLA-backed, highest throughput.
Weeks to provision and the most expensive option. This is the answer for a regulated institution
moving real transaction or customer data between clouds: predictability and an SLA are themselves
the compliance-relevant property, not just raw speed.

**Condition that governs all three:** the two networks must be provisioned with non-overlapping IP
address ranges before any of them can work — this is a prerequisite, not a detail, and is the single
most common reason a first attempt at a cross-cloud link fails to route at all.

### E. Cross-cloud authentication is federation, never a stored credential

A workload in one cloud proves its identity to the other cloud by federating: the origin cloud's
workload identity is presented to the destination cloud's identity provider, which issues a
short-lived token scoped to that specific workload. No long-lived credential for the second cloud is
generated, stored, or rotated anywhere in the first cloud's configuration or secrets store.

The network link (decision point D) gets two networks talking to each other; it does not by itself
authenticate anything crossing it. Federation is the separate, necessary second half — a private
network path carrying a static credential is not meaningfully more secure than a public one carrying
the same credential, because the credential itself is the thing a compromise would target.

### F. Mitigate what cannot be removed: cache locally, cross asynchronously

Two techniques absorb the cross-cloud tax rather than eliminate it, because it cannot be eliminated
while the providers remain split. **Cache on the compute side, not the data side** — a hot-read cache
co-located with compute turns many repeated cross-cloud reads into effectively zero after the first;
placing that same cache next to the data instead does nothing for the calls that matter, since the
compute side still crosses the link to reach it. **Push what tolerates delay onto an asynchronous
path** — event-driven work (an outbox pattern feeding a message backbone) absorbs cross-cloud latency
far better than a synchronous call sitting in a user-facing request path, so the design question for
every cross-cloud interaction is which category it falls into, not whether the hop can be made
faster.

## Anti-patterns

**Choosing a multi-cloud split for "avoiding lock-in" with no other named constraint.** Trades one
real, named risk (concentration in a single vendor) for the ongoing, compounding cost described
above, paid on every request, indefinitely — and the second risk is usually harder to reason about
than the first.

**A private network link with a stored, long-lived credential riding on top of it.** The network
being private does not make the credential safe; see decision point E. This is the cross-cloud
version of "a private endpoint doesn't authorise anything by itself," stated in
`13-private-network-egress-control.md`.

**Provisioning both clouds' networks with overlapping CIDR ranges and discovering it at connection
time.** The most common reason a first cross-cloud link attempt fails outright — see the condition in
decision point D.

**Caching on the data-plane side of the hop.** Does not reduce the number of cross-cloud calls the
compute side makes; the cache has to sit where the calls originate to do anything.

**Managing the cross-cloud link and identity federation in two separate, independently-reviewed IaC
pipelines.** The highest-risk part of a multi-cloud design ends up with no single reviewer who sees
both sides — see decision point C.

**Presenting the split as a design preference rather than naming the constraint that forced it.** A
reviewer's first question is "why two clouds," and an architecture that cannot answer that in one
sentence reads as accidental rather than deliberate.

## Reference implementations

The source diagram models GCP as the compute plane (GKE, Cloud Load Balancing, Apigee) and Azure as
the residency-bound data plane (Postgres, Redis, Event Hubs, Entra ID), bridged by a dedicated
interconnect for a regulated institution, with GKE workloads federating to Entra ID for short-lived
tokens rather than holding a stored Azure credential, and a GCP-side Memorystore cache absorbing
repeated reads so only genuinely new data and async events cross the link. One Terraform
configuration provisions both providers plus the link and firewall rules between them.

The pattern generalises to any provider pair: the compute/data split, the three-tier choice of
bridging mechanism, the federation requirement, and the cache-locally/cross-asynchronously mitigation
do not depend on which two clouds are involved.

## As implemented in `index.html`

Partially. A new `multiCloudMentioned` signal (two or more distinct cloud-vendor groups named —
counts vendor groups, not raw keyword hits) feeds `pickMultiCloudBridging()` (its own "Multi-Cloud
Bridging" stack card), which is conditional rather than always-substantive: a single-cloud or
on-prem requirement gets an explicit "Not applicable," and a genuine multi-cloud requirement gets the
constraint-first framing (decision point A) before naming a single IaC source across both providers
(C), a dedicated interconnect for real data volume (D), and workload-identity federation over a
stored credential (E), with the cache-locally/cross-async mitigation (F) named in the rationale.
`pickCloud()` remains structurally single-answer — the split itself is stated in prose, not modeled
as two separate cloud picks. `pickHybridConnectivity()` remains the separate on-prem↔one-cloud
question this document does not own.

## Sources

**Primary source is the project owner's own architecture work** —
`diagrams/reference-architecture/architecture-multicloud.svg`, authored for a BFSI architecture
review. The constraint-first framing (decision point A), the three-tier bridging comparison, the
federation-not-credential argument, and the cache-locally/cross-asynchronously mitigation are that
author's.

**The latency figures are stated as order-of-magnitude expectations, not measurements.** The source
diagram gave specific ranges (same-region cross-cloud ~1–5ms, cross-region 10–100ms+) with no
citation or measurement methodology behind them — physically plausible for well-provisioned
same-region interconnects, but presented with the same confidence as a benchmark. This document
states them qualitatively (decision point B) rather than repeating the specific numbers as fact, per
the same discipline applied to the SAMA claim in `16-testing-strategy-and-environments.md`. Before
`/api/ask` quotes a specific millisecond figure to a user, it should come from that user's own
measured link, not from this corpus.

Named services (GKE, Apigee, Cloud Load Balancing, Azure DB for PostgreSQL, Event Hubs, Entra ID,
Partner Interconnect, ExpressRoute) are identified as representative examples of their category, not
as a comparative or benchmarked recommendation between providers.
