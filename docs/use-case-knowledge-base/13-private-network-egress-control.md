# Private Network Topology & Egress Control — private endpoints vs. the one audited exit

**Status:** target design — `pickHybridConnectivity()` covers on-prem↔cloud links, not the in-cloud network boundary.

**Domain:** How a workload reaches its dependencies without putting traffic on the public internet,
and how the traffic that genuinely must leave is constrained to a single auditable path. The
governing distinction is that **"outbound" is two different things**: managed cloud services reached
privately, and true third-party SaaS reached over the internet. Source:
`diagrams/reference-architecture/architecture-topology-azure.svg`.

## Business context

The tool reasons about hosting location, on-prem versus cloud, and hybrid connectivity
(`pickHostingLocation()`, `pickHybridConnectivity()`), and it recommends a service mesh
(`pickMesh()`) on mTLS and multi-team grounds. What it has no reasoning about is the network
boundary *within* a cloud deployment: which dependencies stay inside the virtual network, which
leave, and what controls that exit.

This is decisive for regulated buyers and for one increasingly common question the rule engine
cannot currently answer at all: **"does our data leave the network when we call an LLM?"** For a
cloud-native model endpoint reached over a private link, the answer is literally no — and that fact
frequently determines whether an AI feature is approvable.

## Signals / triggers

Network boundary: `private endpoint`, `private link`, `VNet`, `VPC`, `no public IP`, `private
subnet`, `stays in our network`, `never leaves our network`, `data residency`, `network isolation`,
`PrivateLink`, `service endpoint`. Egress: `egress control`, `egress gateway`, `allowlist`,
`outbound traffic`, `firewall rules`, `can a pod call the internet`, `NAT gateway`, `ServiceEntry`.
Regulated AI: `LLM data residency`, `does data leave`, `model call privacy`, `private LLM endpoint`,
`Azure OpenAI private`, `Bedrock VPC endpoint`, `Vertex private`. Mesh: `Istio`, `service mesh`,
`mTLS`, `east-west`, `sidecar`, `ingress gateway`.

## Decision points

### A. The two kinds of outbound — the distinction the whole topology turns on

**Managed services from your own cloud provider** are reached over a private endpoint: the service
gets a private IP inside your virtual network, a private DNS zone resolves its public hostname to
that private IP, and traffic rides the provider's backbone rather than the public internet. Managed
databases, caches, secret stores, event streaming, analytics warehouses — and, critically, the
cloud's own model-inference endpoint — all support this.

**Genuine third parties** — a payment gateway, an SMS provider, a push-notification service — have
no private link into your network. They must be reached over the internet, and the architectural job
is to make that exit singular, allowlisted and audited rather than ambient.

Conflating the two is the most common error in this area, and it cuts both ways: teams either treat
cloud-managed dependencies as "external" and over-engineer an egress path for them, or treat true
third parties as safe-by-default and allow arbitrary outbound.

### B. One public entry, everything else private

A single internet-facing edge (a global load balancer or CDN with WAF and DDoS protection) holds the
only public IP. Inside the network, the cluster's ingress gateway is an *internal* load balancer that
receives from that edge; service-to-service addresses are cluster-internal. No workload is directly
reachable from the internet.

**Condition where this changes:** a partner-facing or webhook-receiving service still terminates at
the same public edge — inbound webhooks do not justify a second public entry point, they justify a
route and an authentication rule on the existing one.

### C. One controlled exit, allowlisted per host

An egress gateway is the single point through which traffic to genuine third parties leaves, with an
explicit per-host allowlist (Istio's `ServiceEntry`, or the equivalent firewall rule set). The
control this buys is precise and worth stating in those terms: **a compromised pod cannot open an
arbitrary internet connection.** That is a claim an auditor can ask you to demonstrate, and a
default-allow egress posture cannot demonstrate it.

### D. Service mesh carries east-west security, not just traffic management

Sidecars provide mTLS between services and a default-deny posture for east-west traffic, so a
service must be explicitly authorised to call another. The mesh's ingress and egress gateways are
then the two ends of the boundary described above — which is why mesh adoption and egress control
tend to be one decision rather than two.

**Condition where this changes:** below roughly ten services, a mesh's operational cost usually
exceeds its benefit and the same properties can be had from network policies plus TLS terminated at
the application. The mesh becomes justified by cross-team trust boundaries and audit requirements
rather than by service count alone.

### E. Data ownership survives the network design

Each service owns its own database instance or schema, reached over the private endpoint rail. The
network topology does not soften the ownership rule — a private link makes another service's
database *reachable*, not *shared*. Reachability is a network property; ownership is a design one,
and the first does not grant the second.

### F. Private model endpoints are what make regulated AI features approvable

Where the cloud provider offers its model endpoint over a private link, the inference call never
transits the public internet, and retrieval-augmented context can be served from a vector store
inside the same boundary. For a regulated buyer this converts "we send prompts to a model provider"
into "the model call stays on our network", which is frequently the difference between an approved
and a rejected design.

**Condition where this changes:** a third-party model provider with no private-link offering is a
true third party and belongs on the egress path, with the data-handling consequences that implies —
which is a real input to model selection, not merely a networking detail.

## Anti-patterns

**Routing cloud-managed services through the egress gateway.** They have a private path; sending
them out and back in adds latency, cost and an unnecessary internet dependency, and it dilutes the
egress allowlist that is supposed to be short enough to review.

**Default-allow egress.** If a pod can reach any host, the egress gateway is a routing convenience
rather than a control, and the "one audited exit" claim is not true.

**Public IPs on workloads for convenience.** A debugging shortcut that becomes permanent and
silently defeats the single-entry property the rest of the topology depends on.

**Assuming a private endpoint encrypts or authorises anything.** It controls *reachability*. TLS,
authentication and authorisation are still required — a private network is not a trusted one, which
is the entire premise of the mesh's default-deny posture.

**Claiming "data never leaves our network" without checking the specific service.** The claim is
true per-service and per-region, not in general. It requires that the specific dependency offers a
private link, that it is actually configured, and that private DNS resolves to it.

## Reference implementations

The source diagram models this on Azure: Front Door with WAF as the sole public entry, AKS with an
Istio mesh whose ingress gateway is an internal load balancer, private endpoints to Azure Database
for PostgreSQL (one database per service), Azure Cache for Redis, Key Vault, Event Hubs, Synapse,
and Azure OpenAI — with an Istio egress gateway and `ServiceEntry` allowlist as the only exit,
carrying traffic to a payment gateway, an SMS provider and a push service. Identity is Entra ID
workload identity for pods, so no static secrets are held.

The pattern maps directly onto AWS (PrivateLink and VPC endpoints, ALB plus WAF, EKS) and GCP
(Private Service Connect, Cloud Load Balancing plus Cloud Armor, GKE). The names change; the two
kinds of outbound do not.

## As implemented in `index.html`

Not yet implemented. `pickHybridConnectivity()` reasons about dedicated links between on-prem and
cloud, which is a different question from private-endpoint access to managed services within one
cloud. `pickMesh()` recommends a mesh on mTLS and team-boundary grounds without reasoning about its
gateways. `pickHostingLocation()` decides cloud-API versus self-hosted inference but does not model
the private-endpoint middle option that makes a cloud model endpoint acceptable to a regulated buyer
— which is the most valuable single gap identified in this document.

## Sources

**Primary source is the project owner's own architecture work** —
`diagrams/reference-architecture/architecture-topology-azure.svg`, authored for a BFSI architecture
review. The two-kinds-of-outbound framing, the single-entry/single-exit structure, and the private
model-endpoint argument are that author's.

Named services are used as representative examples of their category. This document makes no
comparative claim about any vendor's private-link implementation.

**Unsourced claims to resolve before `/api/ask` cites them as fact:** the "roughly ten services"
mesh threshold is a rule of thumb carried over from `pickMesh()`'s existing wording rather than a
researched figure, and the assertion that a given provider's model endpoint supports private access
must be verified per provider and per region before being repeated to a user as a compliance
guarantee.
