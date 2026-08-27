# Secure Delivery Pipeline — CI security gates, GitOps promotion, progressive delivery

**Domain:** How code reaches production safely in a regulated environment — the security gates that
run on every pull request, the GitOps promotion model, and the progressive-delivery mechanics that
make a production release reversible. This is a *different diagram from runtime topology*: runtime
shows how traffic flows, this shows how code ships. Source: `diagrams/reference-architecture/architecture-cicd-deployment.svg`.

## Business context

The tool recommends a CI/CD pick (`pickCICD()`) and a CI/CD vendor comparison, but both answer
"which CI product" — neither reasons about *what has to happen inside the pipeline* for a regulated
buyer to accept it. A BFSI, healthcare or government reviewer does not ask which CI runner you use;
they ask who can approve a production change, whether an unsigned artifact can reach the cluster,
and how you would answer "are we exposed to CVE-X" under time pressure. That is pipeline
architecture, and the rule engine currently has no reasoning about it at all.

This matters for `/api/ask` in particular: "is our CI/CD compliant?" and "what do we need before an
audit?" are common follow-ups that the fixed rule set cannot anticipate.

## Signals / triggers

Compliance/audit: `SOX`, `audit trail`, `change management`, `segregation of duties`, `approval
workflow`, `who approved`, `evidence for auditors`, `regulated deployment`. Supply chain:
`supply chain security`, `SBOM`, `signed images`, `image signing`, `Cosign`, `provenance`,
`dependency scanning`, `CVE`, `vulnerability scanning`, `shift left`. Delivery mechanics: `GitOps`,
`ArgoCD`, `Flux`, `canary`, `blue/green`, `progressive delivery`, `feature flags`, `rollback`,
`admission control`, `OPA`, `Gatekeeper`, `policy as code`. Pipeline scanning: `SAST`, `DAST`,
`SCA`, `IaC scan`, `secrets scan`, `gitleaks`, `Trivy`, `Checkov`.

## Decision points

### A. Shift left — gates belong at the pull request, not before release

Six gate families run on every PR, each able to fail the build: **secrets scanning** (gitleaks,
trufflehog — blocks committed keys and tokens), **SAST** (SonarQube, Semgrep, CodeQL — code-level
vulnerabilities and a quality gate), **SCA** (dependency and license scanning — Snyk, OWASP
Dependency-Check), **unit tests with a coverage floor** plus consumer-contract tests, **image
scanning** (Trivy or a cloud-native equivalent — CVEs in layers, blocking on critical), and
**signing plus SBOM generation** (Cosign signature, SPDX or CycloneDX SBOM).

The economic argument is the one that persuades: a vulnerability caught at the PR costs minutes; the
same vulnerability in production is an incident *and* an audit finding. Gate placement is therefore
a cost decision, not a purity one.

**Condition where this changes:** a small team pre-revenue can start with secrets + SCA only and add
SAST/DAST later — the full six-gate set is justified by regulated data or an external audit
obligation, not by team maturity alone. What does not change is that a green pipeline is a
*precondition to merge*, never an authorisation to reach production.

### B. GitOps — Git is the desired state, the cluster reconciles to it

A config repository holds Kubernetes manifests or Helm charts as the declared desired state. ArgoCD
or Flux continuously reconciles the live cluster against it: drift auto-reverts, and rollback is a
`git revert` rather than a bespoke procedure. The CI pipeline's output is an image tag bump raised
as a PR against that config repo.

The audit property is the real payoff, and it is worth stating explicitly to a reviewer: **every
production change is a reviewed, attributable commit**. Who changed what, when, and who approved it
is the exact evidence a change-management audit asks for, and the Git history *is* the change log —
there is no separate register to maintain and reconcile.

**Condition where this changes:** GitOps assumes declarative infrastructure. A deployment target
that is not declaratively describable (some managed PaaS, certain serverless configurations) gets
less from this model, and a push-based pipeline is a defensible choice there.

### C. Environments gate risk progressively, and the gates differ per environment

**Dev** — auto-deploy on merge, smoke tests, plus the two gates that need a *running* application:
DAST (OWASP ZAP against the live app, catching runtime vulnerabilities SAST structurally cannot see)
and IaC scanning (Checkov, tfsec) before any infrastructure change applies.

**Staging** — production-like, with production-shaped but masked data. Full integration and E2E
suites, load and soak testing (k6) to validate autoscaling behaviour and size pods, and a DR or
chaos drill with fault injection. Then a **human approval** — a change-advisory or release-manager
sign-off.

**Production** — canary via Argo Rollouts stepping 5% → 25% → 50% → 100%, promoting only while SLOs
hold (error rate, P99 latency, saturation) and auto-rolling-back on breach. Blue/green is the
alternative when a release is database-risky: a full standby environment with traffic flipped at the
ingress, so rollback is flipping back rather than redeploying.

### D. Deploy and release are different events

Feature flags decouple them. Code ships dark, then is enabled per cohort — which makes a release a
configuration change rather than a redeploy, and makes "turn it off" a seconds-long operation rather
than a rollback. This is what allows a risky feature to reach production infrastructure long before
it reaches users.

### E. Admission control is the enforcement point that makes the rest true

OPA Gatekeeper or the cloud's equivalent policy engine rejects, at deploy time: unsigned images,
privileged pods, workloads with no resource limits, and images from non-allowlisted registries.

This is the difference between a pipeline that *should* produce safe artifacts and a cluster that
*cannot run* unsafe ones. Every gate in section A is advisory until something at the cluster edge
refuses to run what failed them — a pipeline can be bypassed, an admission controller cannot be
without an audited policy change.

## Anti-patterns

**Treating a green pipeline as authorisation to deploy to production.** Green means the artifact is
eligible. Promotion to production is a separate, human-approved decision — conflating them removes
the segregation-of-duties control that regulated reviewers specifically look for.

**The approver being the author.** SOX-style segregation of duties requires that the person
approving the production promotion is not the person who wrote the change. A pipeline that lets an
author self-approve has no meaningful approval control regardless of how many gates precede it.

**Storing long-lived cloud credentials in the pipeline.** OIDC workload-identity federation lets the
runner exchange a short-lived token for cloud access with no stored secret. A pipeline holding a
static cloud key is a standing credential with broad blast radius and no natural expiry.

**Scanning images but not enforcing at admission.** If the cluster will run an unsigned or unscanned
image, the scan is reporting, not control. The scan and the admission policy have to be paired.

**Generating an SBOM and never using it.** The SBOM's value is answering "are we exposed to CVE-X?"
in minutes across every deployed release. Produced and discarded, it is compliance theatre.

**Drawing runtime topology and delivery pipeline as one diagram.** They answer different questions
for different audiences and change at different rates. Keeping them separate is a documentation
decision worth stating, not an accident.

## Reference implementations

The source diagram models an Azure/AKS instance of this pattern: GitHub Actions or Azure DevOps as
the runner authenticating via OIDC workload identity federation, Azure Container Registry holding
signed images and SBOMs with geo-replication and quarantine, ArgoCD reconciling AKS namespaces per
environment, Argo Rollouts driving the canary, and Azure Policy for AKS alongside OPA Gatekeeper at
admission. The pattern is cloud-agnostic — the equivalent AWS path is ECR plus CodePipeline or
Actions with IAM roles for service accounts, and GCP's is Artifact Registry plus Cloud Build with
workload identity federation.

## As implemented in `index.html`

Not yet implemented. `pickCICD()` selects a CI platform and deployment shape but reasons about
neither the security-gate set nor the promotion model; `pickGuardrails()` covers AI guardrails, a
different concern entirely. The nearest existing surface is the CI/CD stack card and its vendor
comparison. A trade-off card ("pipeline security gates: which subset, and when the full set is
justified") and a governance-section extension are the natural wiring points.

## Sources

**Primary source is the project owner's own architecture work** —
`diagrams/reference-architecture/architecture-cicd-deployment.svg`, authored for a BFSI
architecture review. The decision structure, gate ordering, and the audit-control framing above are
that author's, contributed to this corpus deliberately.

Named tools (gitleaks, Semgrep, CodeQL, Snyk, Trivy, Cosign, Checkov, tfsec, k6, ArgoCD, Flux, Argo
Rollouts, OPA Gatekeeper) are identified as representative examples of their category rather than as
benchmarked recommendations — this document makes no comparative performance or pricing claim about
any of them.

**Unsourced claims to resolve before `/api/ask` cites them as fact:** the specific canary step
percentages (5/25/50/100) are a common default rather than a researched threshold, and the
SOX segregation-of-duties framing is stated here as an architecture principle without a citation to
the controlling text. Both should acquire a source before being quoted to a user as a compliance
requirement rather than as a design convention.
