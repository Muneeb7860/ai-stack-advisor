# Testing Strategy — the functional pyramid, named performance tests, and test data

**Status:** target design — nothing below is implemented. `pickCICD()` selects a CI platform and
deployment shape; no reasoning about what to test, how to size performance testing, or how test data
is sourced exists anywhere in the engine.

**Domain:** What to test (the functional pyramid plus non-functional test types) and how to source
test data without ever letting real production data reach a lower environment. Source:
`diagrams/reference-architecture/architecture-testing-full.svg`.

**Ownership note:** this document does not restate the environment ladder or the deployment
promotion mechanics — those are owned by `12-secure-delivery-pipeline.md` §C, which this document
references by name rather than duplicating. This document is authoritative for test *taxonomy*: the
functional pyramid, the four named performance-test types, the three test-data strategies and their
trade-offs, and DR verification as evidence rather than a log entry. Split this way because a rule
stated in two documents, worded two ways, is what broke retrieval the first time this corpus grew
(see `00-INDEX-AND-INGESTION-GUIDE.md` §2b) — each document states what it alone is authoritative
for, and points at the other for the rest.

## Business context

The engine reasons about CI/CD deployment shape (`pickCICD()`) and, once
`12-secure-delivery-pipeline.md` is wired in, about pipeline security gates and promotion — but
nothing reasons about *what gets tested* or *how test data is sourced*. Those are exactly the
questions a technical reviewer asks after the pipeline mechanics: "what's your test pyramid," "how
do you performance-test," "where does your test data come from." A tool that can describe a full
delivery pipeline and cannot answer any of those three has a visible, specific gap.

## Signals / triggers

Functional testing: `test pyramid`, `unit tests`, `integration tests`, `contract tests`, `Pact`,
`component tests`, `E2E tests`, `end to end tests`, `smoke tests`, `regression tests`, `UAT`,
`user acceptance testing`, `exploratory testing`, `ice-cream cone`, `too many E2E tests`, `flaky
tests`. Performance: `load testing`, `stress testing`, `soak testing`, `endurance testing`, `spike
testing`, `k6`, `Gatling`, `JMeter`, `performance testing`, `does it hold up under load`, `memory
leak`, `capacity testing`, `scalability testing`. Resilience: `chaos engineering`, `chaos testing`,
`fault injection`, `DR drill`, `disaster recovery testing`, `failover testing`, `RTO`, `RPO`,
`backup restore testing`, `can we actually recover`. Test data: `test data`, `masked data`,
`anonymised data`, `synthetic test data`, `data subsetting`, `PII in test environments`, `production
data in staging`, `test data strategy`, `referential integrity`, `data masking`.

## Decision points

### A. Functional tests are a pyramid — many fast, few slow

Base to tip: **unit** (pure logic, mocked collaborators — thousands of tests, milliseconds each, run
on every push), **integration** (a service against real dependencies — a real database, a real
message broker, via Testcontainers rather than mocks), **contract** (Pact-style: verify that
service A's calls match service B's actual schema, without a full end-to-end run — the tool that
scales with microservice count, because pairwise E2E coverage does not), **component/API** (one
service exercised through its own API surface), **E2E** (few, slow, the whole system).

Layered on top rather than sitting in the pyramid itself: **smoke** (a minimal check immediately
post-deploy), **regression** (the full suite re-run), **sanity** (a targeted re-check after a fix),
**UAT** (business sign-off), **exploratory** (unscripted manual testing aimed at what the scripted
suite would not think to check).

**Condition where this changes:** a single-service, low-integration system has less need for the
contract-test tier — contract testing earns its cost specifically when services multiply and
pairwise E2E stops scaling.

### B. Performance testing is four different tests, not one

**Load** — expected peak traffic; does the system hold its stated SLOs. **Stress** — pushed past
breaking point, to learn *where* and *how* it fails, not just *whether*. **Soak (endurance)** —
sustained load for hours; this is what finds a memory leak, and the one type teams skip because
nothing looks wrong in a short run. **Spike** — a sudden surge (a payday, a market open), testing
how fast autoscaling reacts rather than steady-state capacity.

Load and stress results size compute and validate autoscaling thresholds directly. Volume testing
(very large data sets) and scalability testing (does adding nodes actually add throughput, or does a
bottleneck elsewhere cap it) are extensions of this same band, not separate categories.

**The distinction is the point, not decoration.** Naming "load testing" as a single activity is the
answer that stops at recognising performance testing exists; naming which of the four applies to a
given risk, and why, is the answer that shows the difference has been understood.

### C. Resilience and recovery testing is a control, not a nicety, for a regulated system

**Chaos engineering / fault injection** — deliberately kill a pod, a node, or an availability zone
and confirm the system self-heals per its own design, rather than assuming it does. **DR / failover
drill** — an actual region or environment failover, exercised to prove stated RTO/RPO figures are
real rather than aspirational numbers on a slide. **Backup restore verification** — actually
restoring from a backup. A log line reading "backup succeeded" is not evidence of recoverability;
only a completed restore is.

For a regulated financial institution, resilience testing of this kind is typically an expected
control under business-continuity frameworks (e.g., Saudi Arabia's SAMA BCM framework and equivalent
regimes elsewhere), not an optional maturity practice — see the Sources section for the strength of
that claim as stated here.

### D. Test data has three strategies, and the rule above all of them is absolute

`12-secure-delivery-pipeline.md` §C states the masking obligation this document assumes: real
production data does not reach a lower environment. The three ways to satisfy that obligation trade
off differently, and picking one is itself an architecture decision:

**Masked/anonymised production copy** — tokenise identifiers, shuffle names, perturb values, before
the data leaves the production boundary. Highest fidelity to real-world data shape. Must be
referentially intact (a masked claim must still resolve to its masked customer, or joins break),
irreversible (no key exists to re-identify), and consistent (the same input token maps to the same
output every time, across tables). The masking pipeline itself becomes a security-sensitive
component and needs to be treated as one.

**Synthetic generation** — data modelled on production's shape and statistical distribution,
generated from no real record at all. Zero re-identification risk because there is nothing real to
leak. The trade-off: synthetic data captures the distribution you modelled, not the specific
malformed, decades-old, or otherwise weird records that only exist in a real production dataset —
and those are disproportionately where bugs hide.

**Subsetting** (typically combined with masking) — take a referentially complete slice of production
(a percentage of customers plus every row that belongs to them), then mask that slice. Cheaper and
faster to refresh than a full clone, and integrity is preserved because the slice was drawn to be
self-contained.

**The common answer in practice is not one of the three alone**: synthetic data for volume and
load-shape, plus a masked, subsetted slice specifically for the edge-case realism that only real
(masked) records provide.

## Anti-patterns

**The "ice-cream cone."** Mostly E2E tests, few unit tests — the pyramid inverted. Slow, flaky, and
because everyone learns to distrust the flaky suite, eventually ignored, which is a worse state than
having no automated tests and knowing it.

**Calling every performance test "load testing."** Conflates four different risk questions into one
label, and specifically hides soak testing, which is the one that finds the leak — see decision
point B.

**Trusting a "backup successful" log as disaster-recovery evidence.** It confirms a write happened,
not that the resulting artifact restores to a working system. Only a completed restore proves that.

**Any production data in a lower environment, "temporarily," for any reason, including debugging a
live bug.** This is the one absolute rule in the document — see decision point D and
`12-secure-delivery-pipeline.md` §C. There is no exception that survives an audit.

**A masking pipeline that breaks referential integrity.** Data that is safely anonymised but no
longer joins correctly is not usable test data — it is destroyed data that happens to still exist.

**Treating staging as prod-like without the same IaC and the same sizing.** A pass on an
under-sized, hand-patched staging environment does not transfer to production — see
`12-secure-delivery-pipeline.md` §C, which owns this point.

## Reference implementations

The source diagram models the pyramid with unit/integration/contract(Pact)/component/E2E tiers,
smoke/regression/sanity/UAT/exploratory layered across them, k6/Gatling/JMeter for the four named
performance-test types, and chaos/DR-drill/restore-verification as the resilience band — alongside a
compliance/usability strip covering accessibility (WCAG), localisation, and audit-trail evidencing.
Test-data strategy is drawn as three parallel approaches (masked copy, synthetic generation,
subsetting) with the common-practice combination stated explicitly.

## As implemented in `index.html`

Nothing of this document is implemented. `pickCICD()` selects a CI platform and deployment topology
and reasons about neither test taxonomy nor test-data strategy. The natural wiring point is a new
trade-off card for the performance-test-type distinction (decision point B) and a governance-section
extension for the test-data rule (decision point D), the latter being the highest-value single
addition for any requirement carrying a compliance signal.

## Sources

**Primary source is the project owner's own architecture work** —
`diagrams/reference-architecture/architecture-testing-full.svg`, authored for a BFSI architecture
review. The pyramid-plus-cross-cutting-layers framing, the four-named-performance-tests distinction,
the resilience-as-control argument, and the three-strategy test-data framework are that author's.

**The SAMA claim is deliberately hedged, not stated as fact.** The source diagram's own text read
"SAMA-style BCM frameworks mandate evidenced DR testing" — a specific regulatory assertion with no
citation to the controlling provision. This document does not repeat that as fact: decision point C
above states it as "typically an expected control under business-continuity frameworks... and
equivalent regimes elsewhere," which is defensible without a citation, and does not name a specific
mandated clause. Before `/api/ask` cites SAMA (or any other named regulator) by name on this point,
the specific BCM framework provision needs to be identified and cited here — an interviewer or
auditor who knows the framework will ask which control, specifically, and "SAMA requires it" without
a citation is a worse answer than the hedge above.

Named tools (Pact, k6, Gatling, JMeter, Testcontainers) are identified as representative examples of
their category, not as benchmarked recommendations.

**Other unsourced claims to resolve before being cited as fact:** no specific numeric RTO/RPO target
is stated or implied here — the document says such targets should be proven real, not what they
should be, and any specific figure quoted to a user would need to come from that user's own recovery
requirements, not from this corpus.
