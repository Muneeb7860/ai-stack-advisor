# Validation Pass — Bugs Found & Fixed

Ran 6 crafted scenarios beyond the 5 built-in examples — deliberately including sparse input, internally conflicting requirements, and edge cases (pure batch pipeline, IoT, air-gapped/on-prem) — to sanity-check the rule engine before adding more scope. Found three real bugs, all fixed and re-verified against both the new scenarios and the original 5 examples (no regressions).

## Bugs found

**1. Negation wasn't handled — stated non-requirements were read as requirements.**
The keyword matcher does plain substring search, so "no document search" matched the `document search` keyword, and "don't have compliance requirements yet" matched `compliance`. This wasn't just a theoretical edge case — it was live in the tool's own MVP example: that scenario says *"don't have compliance requirements yet"* but the compliance signal was firing anyway, causing it to incorrectly recommend local/self-hosted LLM infrastructure and compliance-driven guardrails for a startup that explicitly said it didn't need them.
*Fix:* added a `stripNegations()` preprocessing pass that removes short clauses following "no/not/without/don't/never/etc." before keyword matching runs. Re-verified: the MVP example now correctly shows "Cloud API (hosted, pay-per-token)" hosting instead of local.

**2. No handling at all for air-gapped / on-premises / "no public cloud" requirements.**
There was no signal for this and no fallback — an explicit "cannot use any public cloud, air-gapped, on-prem" requirement still fell through to the generic enterprise default and recommended **Microsoft Azure**, directly contradicting the stated constraint. This also propagated wrong recommendations for compute (serverless, which doesn't exist on-prem), containers (managed EKS/GKE/AKS, which aren't available air-gapped), observability (SaaS Datadog/Splunk, unreachable without internet egress), CI/CD (cloud-hosted runners, same problem), and DNS (public providers).
*Fix:* added an `onPrem` signal (detected on raw, non-negation-stripped text, since phrases like "no public cloud" are themselves the requirement, not something being negated away) and an on-prem override branch at the top of cloud, gateway, compute, containers, observability, CI/CD, DNS, hosting, and the cloud-strategy trade-off — each now recommends the private/self-hosted equivalent with an explanation of why the public-cloud default doesn't apply.

**3. No data warehouse option — analytics/ETL-heavy workloads got Postgres/Mongo/Cassandra instead.**
A pure batch-ETL/analytics-dashboard scenario (no transactional app, no chat, no RAG) was getting recommended MongoDB and Cassandra as its database — neither is what you'd actually run BI dashboards or large aggregations against.
*Fix:* added a warehouse-need detector (data-heavy signal present, without transactional/chat/RAG signals) that recommends a columnar cloud warehouse (BigQuery/Snowflake/Redshift) as the analytics store, with Postgres/Cassandra layered in only if a transactional or high-volume-ingestion component is also present.

## Also tightened

- **Compute vs. team-size conflicts:** previously, `startupMvp` alone triggered a pure serverless recommendation even when `highScale`/`enterprise`/`realtime` were also present, and the justification text ("ideal for small teams") didn't acknowledge the conflict. Now a small team with real-time/high-scale/enterprise needs gets a middle path (serverless containers with autoscaling) with an explicit note about the tension, instead of a recommendation whose own rationale contradicted half the input.
- **Architecture style priority:** `enterprise`/`largeTeam` was checked before `startupMvp`/`smallTeam`, so a 3-person team with a compliance requirement got "microservices" — operationally unrealistic for that team size regardless of compliance need. Team size now takes priority for the monolith-vs-microservices decision specifically (Conway's law reasoning), with compliance needs met through governance practices inside the monolith instead.
- **Small-team detection was too narrow:** only matched literal phrases like "3 engineers"; a "4-person ops team" wasn't recognized. Added a regex fallback for "N-person"/"team of N" phrasing.

## Re-verification

All 5 original built-in examples still render correctly (spot-checked cloud, hosting, RAG, guardrail count, compute, and architecture per example — no regressions from the fixes above). All 6 new validation scenarios now produce internally consistent, defensible recommendations, including the air-gapped case correctly refusing to recommend any public-cloud service anywhere in the output.
