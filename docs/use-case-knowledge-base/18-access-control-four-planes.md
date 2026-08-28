# Access Control — four planes, one coherent model

**Status:** partial — `pickPrivilegedAccess()` now covers plane 3 (PIM/JIT/break-glass); `pickMesh()`
and an existing trade-off card already cover plane 2's SPIFFE/SPIRE identity reasoning in real depth.
The rest is target design: `pickIAM()` picks a vendor without reasoning about RBAC/ABAC enforcement
location or token revocation, and plane 4's data-access auditing and same-cloud workload identity
have no representation anywhere in the engine.

**Domain:** "Access control" is not one mechanism — it is four separate planes, each answering a
different question with a different mechanism. Source:
`diagrams/reference-architecture/architecture-access-control.svg`.

**Ownership note — three existing documents, three different boundaries:**
- `13-private-network-egress-control.md` §D already owns *why* a service mesh and default-deny
  east-west exist (the network-segmentation argument). This document owns the identity layer on
  top of that: what a SPIFFE ID and an SVID actually are, and — new — the four other things a
  reviewer asks about access control once the mesh exists.
- `17-multi-cloud-bridging.md` §E already owns workload identity federation **across two cloud
  providers** (the GKE→Entra ID case). This document owns the **same-cloud** version of workload
  identity — a pod reaching its own cloud's database or secret store — and explicitly defers to
  doc 17 the moment a second cloud provider is involved, rather than restating that content.
- `15-observability-and-audit-logging.md` §H already owns *how* audit events are stored (a
  separate, immutable, write-once pipeline). This document is a **producer**, not a duplicate: every
  plane below generates events that flow into that pipeline, and this document says so without
  restating what the pipeline itself looks like.

**Term-collision note:** `05-multi-tenant-saas.md` also uses "Row-Level Security" — for a different
concept (tenant isolation, one tenant's rows hidden from another tenant). This document's RLS use is
per-user, within-tenant authorization (one user's rows hidden from another user of the *same*
tenant). Same Postgres feature, different problem — worth stating explicitly so retrieval and a
reader don't conflate the two.

## Business context

The rule engine and every other security-adjacent KB document (12's segregation of duties, 13's
mesh, 15's audit pipeline, 17's workload federation) each cover one fragment of access control, but
nothing states the fragments *as* fragments of one model, and nothing covers the two planes a BFSI
reviewer actually probes hardest: privileged human access to infrastructure, and how a workload
authenticates to a resource without holding a credential. Most candidates — and, before this
document, this tool — answer "access control" with authentication/authorization for end users and
stop there.

## Signals / triggers

Structure: `access control`, `four planes`, `who can access what`, `authz model`, `authorization
architecture`. End-user: `RBAC`, `ABAC`, `role-based access`, `attribute-based access`, `OIDC`,
`OAuth2`, `MFA`, `conditional access`, `coarse authz`, `fine-grained authz`, `token revocation`,
`revoke a token`, `JWT expiry`, `deny list`, `token introspection`. Service identity: `SPIFFE`,
`SPIRE`, `SVID`, `workload identity`, `mTLS`, `secret zero`, `secrets rotation`. Human/privileged:
`PIM`, `privileged identity management`, `just-in-time access`, `JIT access`, `break-glass`,
`break glass account`, `standing access`, `standing admin`, `access review`, `recertification`,
`segregation of duties`, `bastion host`, `who can read production data`, `DBA access`, `dynamic data
masking`, `privileged access management`, `PAM`. Workload identity: `managed identity`, `IRSA`,
`workload identity federation`, `no stored credential`, `no stored password`.

## Decision points

### A. Four planes, four different questions

**End-user** (*"who is this user, what may they do?"*) — a customer or admin reaching the
application. **Service-to-service** (*"is this really the service it claims to be?"*) — one
microservice calling another. **Human operator → infrastructure** (*"how does a human get admin,
and can we prove who did what?"*) — an engineer reaching the cluster or cloud console. **Workload →
resource** (*"how does a pod authenticate to a database without holding a password?"*) — a running
process reaching a data store or secret manager.

Treating these as one undifferentiated "access control" is the mistake this document exists to
correct. Each plane has a different threat model, a different mechanism, and — for a regulated
buyer — a different audit expectation. Opening an access-control discussion by naming the four
planes, before describing any one of them, is itself the signal that the answer comes from real
review experience rather than having built a login page once.

**Condition on emphasis:** for a regulated institution, planes 3 and 4 are where audit findings
actually land — standing privileged access and credentials embedded in configuration are the two
most common real findings — so they warrant more depth than planes 1 and 2, not equal treatment.

### B. End-user: two enforcement layers, plus a third for defense in depth

Authentication (OIDC/OAuth2, MFA, conditional access on device/risk/location) establishes who is
calling. Authorization splits across two enforcement points that must both exist: **RBAC at the
gateway** — coarse, "is this caller a valid, authorized client at all" — and **fine-grained
authorization inside the service** — "can this specific user touch this specific record," which a
gateway structurally cannot know because it has no view of the data model. ABAC (attributes like
department, transaction amount, region) layers contextual rules on top of role membership for cases
a role alone can't express.

**Row-level security in the database is a third layer, not a replacement for the first two** —
defense in depth so a bug in service-layer authorization logic doesn't become a data exposure, since
even a flawed query still can't return rows the database itself won't release. (Distinct from
`05-multi-tenant-saas.md`'s RLS use — see the term-collision note above.)

### C. Token revocation is the gap coarse/fine-grained authorization doesn't close

A JWT is valid until it expires, full stop — firing an employee or detecting a compromised session
doesn't invalidate a token already issued. Two things narrow this gap because neither closes it
completely: short token TTLs (minutes, not hours) shrink the exposure window, and a deny-list or
introspection endpoint gives an instant-kill path for a specific token when short TTL alone isn't
fast enough. Refresh-token rotation (a used refresh token is invalidated) limits how far a stolen
refresh token can be replayed.

**This is worth naming unprompted** — it's the natural follow-up to any token-based-auth answer, and
answering it before being asked is the same signal as opening with the four-plane split.

### D. Service identity is attested, not asserted

A SPIFFE ID (e.g. `spiffe://bank/ns/prod/sa/payment`) is carried inside an X.509 SVID — a
short-lived, cryptographically verifiable identity document, not a certificate the service
configures itself. SPIRE issues it by **attestation**: proving what the workload actually is (which
node, which pod, which service account) before handing over an identity, rather than trusting a
value the workload simply claims. The mesh sidecar handles issuance and rotation, so application code
never touches TLS or identity material directly.

This is the identity layer sitting on top of the network segmentation `13-private-network-egress-
control.md` §D already covers — that document explains why the mesh and default-deny east-west
exist; this section explains what proves a service is who it claims to be once traffic is allowed to
flow at all.

### E. Secret zero: the loop only closes if nothing bootstraps a secret with a secret

For the few secrets that genuinely must exist (a third-party API key with no federation option),
rotation and versioned storage in a secrets manager, fetched at runtime, are necessary but not
sufficient. The remaining question is **how the workload authenticates to the secrets manager in the
first place** — if that requires its own stored credential, the problem has only moved, not
disappeared.

The answer is that it doesn't hold one: workload identity (decision point F) bootstraps access to
the secrets manager itself, so the chain terminates in a platform-attested identity rather than a
planted credential anywhere in the chain. This is the same principle as decision point D applied one
layer further — attestation, not a secret, all the way down.

### F. Workload-to-resource identity, and where it stops being this document's job

A pod's own identity (its Kubernetes service account, in the common case) federates to the cloud's
IAM to receive a short-lived token scoped to a specific database or secret store — nothing is stored
in the image, the config, or an environment variable, and there is nothing to leak because nothing
persists. Per-cloud names for the same pattern: Azure Managed/Workload Identity, AWS IRSA, GCP
Workload Identity.

**This document's scope stops at one cloud.** The moment the resource being reached lives in a
*different* cloud from the workload, this is `17-multi-cloud-bridging.md` §E's subject
(federation across the trust boundary between two providers) — that document should be cited for the
cross-cloud case rather than this section restated.

### G. Access to infrastructure is not access to data — the sharpest audit question

Just-in-time elevation (PIM: request, time-boxed, approved, MFA'd on activation, auto-expiring,
every activation logged), break-glass accounts (a small fixed number, excluded from conditional
access, hardware MFA, alerting on *any* use), periodic access review/recertification, bastion access
rather than public SSH/RDP, and segregation of duties (the approver is never the requester) together
answer "how does a human get infrastructure admin, and can it be proven after the fact."

**They do not answer a distinct, higher-sensitivity question**: who can read production *data*.
Infrastructure access and data access are different grants and need to be treated as such — a DBA
with legitimate infrastructure access querying live customer records is a separate, auditable event,
ideally itself JIT-elevated, with dynamic data masking so even an authorized privileged query
returns masked PII unless the specific need is explicit. The sentence that carries this: *access to
the box is not access to the data.*

### H. Every access decision is an audit event — access control and audit are one story

Who authenticated, whose token was issued, which human elevated via PIM, which pod received a
database token, which query a privileged session ran — all of it is evidence, and all of it needs to
land in the same immutable pipeline `15-observability-and-audit-logging.md` §H already specifies.
This document does not redefine that pipeline; the relationship is that access control is where the
evidence originates and that document is where it becomes tamper-evident and durable.

**The line worth carrying:** a grant that cannot be proven to have happened is a grant that cannot be
defended in an audit — which is the reason planes 3 and 4 matter as much as they do to a regulated
buyer specifically, not just as a general good practice.

## Anti-patterns

**Answering "access control" with only plane 1.** Authentication and RBAC/ABAC for end users is the
part every product needs and the part every candidate names. Stopping there, for a regulated
audience, answers the easy 20% and skips the 80% an actual audit examines.

**Trusting gateway-level authorization as sufficient.** The gateway cannot know row-level business
rules; a coarse pass there is not a substitute for fine-grained checks in the service, and neither is
a substitute for row-level security in the database.

**Treating standing admin as normal.** If engineers hold persistent elevated access rather than
requesting it JIT, there is no meaningful "who did this and when" answer available after an
incident — only "who could have."

**Conflating infrastructure access with data access.** Provisioning a DBA role that can both manage
the database *and* read every row through it collapses two grants that a reviewer expects to see
separated, audited, and masked independently.

**A workload holding a credential to fetch its other credentials.** If the secrets-manager
authentication itself requires a stored secret, secret zero was never actually solved — it was moved
one layer down.

**No revocation path for a token-based session.** "It's a JWT, it just expires" is a true statement
and an incomplete answer — the follow-up ("how fast, and can you kill one early") is exactly the
question this document's decision point C exists to pre-empt.

## Reference implementations

The source diagram models this for an Azure-hosted bank: Entra External ID/CIAM plus Apigee for
plane 1, Istio with SPIRE-attested SPIFFE identities for plane 2, Entra PIM plus monitored
break-glass accounts and Bastion for plane 3, and Azure Managed/Workload Identity (with Workload
Identity Federation for the cross-cloud case, deferred to doc 17) for plane 4 — all four flowing into
the same immutable audit pipeline doc 15 specifies. The four-plane structure and every named
mechanism generalise directly to AWS (IAM Identity Center, IRSA, Systems Manager Session Manager as
the bastion equivalent) and GCP (Identity Platform, Workload Identity, IAP) — the plane boundaries
and the "attested, short-lived identity over stored secret" principle don't change with the vendor.

## As implemented in `index.html`

Partially. `pickIAM()` selects an identity vendor for plane 1 without reasoning about RBAC/ABAC
enforcement location or token revocation. `pickMesh()` and the existing "Edge auth (JWT) vs.
service-to-service identity" trade-off card already cover plane 2's SPIFFE/SPIRE reasoning in real
depth — this document adds the SVID/attestation mechanics underneath that pick rather than
duplicating it. `pickPrivilegedAccess()` (its own "Privileged Access" stack card) now covers plane 3:
an air-gapped requirement gets bastion-plus-JIT-local-admin, a solo minimal project is told no formal
process is needed yet, a compliance/finance/healthcare/enterprise requirement gets full PIM/JIT/
break-glass/segregation-of-duties with the infra-access-vs-data-access distinction named explicitly,
and everything else gets a proportionate named-admin-list middle tier — deliberately not duplicating
`pickIAM()`, which picks a vendor rather than reasoning about how a human gets elevated. Plane 4
(data-access auditing, same-cloud workload identity) still has no representation anywhere in the
engine. The natural remaining wiring point is a data-access card distinct from the existing
`pick_governance` audit-log mentions, which are about access control generally rather than a
separate data-access grant.

## Sources

**Primary source is the project owner's own architecture work** —
`diagrams/reference-architecture/architecture-access-control.svg`, authored for a BFSI
architecture review. The four-plane structure, the token-revocation and secret-zero follow-ups, the
infrastructure-versus-data-access distinction, and the audit-pipeline tie-in are that author's.

Named products (Entra External ID, Apigee, Istio, SPIRE, Azure PIM, Managed/Workload Identity, IRSA)
are identified as representative examples of their category. This document makes no comparative
claim between identity providers or PAM products.

**Unsourced claims to resolve before `/api/ask` cites them as fact:** "break-glass: 2 accounts" is
stated as a specific number in the source diagram; this document deliberately generalised it to "a
small fixed number" rather than repeat a specific count with no sourced rationale for why two is the
right number for every organisation. The claim that standing admin and unaudited data access are the
most common real audit findings is stated here as the author's professional experience, not a cited
study — worth a source before being repeated to a user as an established statistic rather than
informed judgement.
