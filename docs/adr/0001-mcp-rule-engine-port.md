# ADR 0001: Port the v1 rule engine to Python for the MCP tool, rather than shelling out or proxying

**Status:** Accepted
**Date:** 2026-08-07
**Context:** `backend/app/mcp/server.py`'s original stub docstring posed this as an open
decision to make explicitly before building the MCP tool wrapper (PRD FR-29, DDD Section 3.4
"Integration Context").

## Decision

Port `detectSignals()` and the ~30 `pickX()` functions from `index.html`'s JavaScript to a
new Python module, `backend/app/rule_engine.py`, and have the MCP server import and call it
directly (option **(a)** from the original stub's three options).

**Rejected alternatives:**
- **(b) Shell out to Node** to run the existing JS unmodified — adds a Node runtime
  dependency to a Python backend, plus process-spawn overhead per invocation, for a
  component the DDD explicitly wants to stay "the thinnest layer... not a source of business
  rules" (Section 3.4). A subprocess call is a heavier, slower, harder-to-test dependency
  than an in-process function call.
- **(c) Proxy over HTTP to a deployed copy of the frontend's logic** — `index.html` has no
  server-side deployment target by design (PRD NFR-1: v1 is client-side-only, zero network
  calls); standing one up just to give the MCP server something to call would be new
  infrastructure built solely to avoid porting ~500 lines of logic, and would add a network
  hop and a new failure mode (that service being unreachable) for no offsetting benefit.

## Risk this decision creates, and how it was mitigated

The real risk of a manual port is silent drift or reintroduced bugs — `index.html` already
went through a validation pass (`../validation-report.md`) that found and fixed three real
bugs (negation handling, missing on-prem/air-gapped support, missing data-warehouse
detection) plus tightened team-size and architecture-style conflict handling. A careless
re-implementation "from the spec" rather than from the actual current source risks
reintroducing exactly those bugs.

**Mitigation — verified, not assumed:** before `app/mcp/server.py` was written to depend on
it, `app/rule_engine.py` was diffed against the actual running JavaScript (extracted from
`index.html`, executed under Node) across 13 scenarios:
- The 5 built-in example scenarios (fintech, healthcare, e-commerce, enterprise, early-stage MVP).
- 8 additional scenarios specifically targeting every bug category in the validation report:
  an air-gapped/no-public-cloud case, a pure-ETL/warehouse case, an IoT/time-series case, a
  small-team-with-high-scale-needs conflict case, the "4-person team" regex-fallback case, the
  original negation-handling MVP example, a structured/SQL-RAG case, and a "hybrid on-prem
  and cloud" edge case (which must NOT trigger the on-prem override, per `detectSignals()`'s
  own softOnPrem logic).

Result: **zero differences** between the JS and Python outputs across all 13 scenarios,
compared as full deep-equal JSON (signals dict + all ~30 recommendation categories per
scenario). The verification harness was a temporary script, not committed — this ADR and the
zero-diff result are the durable record of that check having been done.

## Consequences

- `app/rule_engine.py` and `index.html`'s `<script>` block are now two independent
  implementations of the same logic, which **will drift** if one is changed without the
  other. There is no shared-source mechanism preventing this (by design — v1 must stay a
  single self-contained HTML file with no backend dependency, so it can't import from the
  Python backend, and the backend shouldn't parse/execute the frontend's JS at runtime).
- **Action required on every future rule-engine change:** if `index.html`'s `detectSignals()`
  or any `pickX()` function changes, `app/rule_engine.py` needs the equivalent change in the
  same commit (or a follow-up commit that says so explicitly) — this is called out again in
  `app/rule_engine.py`'s own module docstring so it isn't missed by someone only looking at
  one of the two files.
- No automated CI check currently re-runs the cross-language diff on every change (the
  verification harness wasn't committed). If this becomes a real maintenance burden, a
  worthwhile follow-up would be committing a small Node+pytest harness that re-runs this
  comparison automatically — flagged here as a real gap, not silently deferred.

## Addendum: post-merge validation round (same day)

A dedicated validation/verification pass, run after this ADR's decision had already shipped
(not as part of deciding it), re-ran the same JS-vs-Python diff with an expanded scenario set
— 33 total, the original 13 plus 20 new ones specifically targeting `pickIAM()`'s many
vendor-selection branches (Entra, Ping/ForgeRock, Oracle, JumpCloud, OneLogin, CyberArk,
Saviynt, identity-governance complementary picks) and a few signal-detection edge cases
(Java-not-JavaScript, "go" as a verb vs. the language, an overloaded many-signals input).
**Zero diffs** across all 33. This doesn't change the decision above; it's additional
confidence that the port's coverage extends well past the original 13 scenarios into
branches that hadn't been exercised yet.

That same validation round is also where the real bug documented in
`backend/app/mcp/server.py` (`_client_name_from_context`'s `.clientInfo` vs. `.client_info`
attribute-name mistake) was found — by driving an actual stdio MCP session end-to-end, not by
this ADR's JS-vs-Python diff (that diff only exercises `rule_engine.py`, which was correct
throughout; the bug was in `mcp/server.py`'s protocol-layer glue code, a different file this
ADR doesn't cover). Noted here because it's the same validation effort, not because it's part
of the port decision itself.

## Addendum 2: full re-port after the frontend expansion pass

A separate, parallel design/research session (see `KICKOFF_BRIEF.md` Section 0) expanded
`index.html`'s rule engine substantially: signal count grew from ~35 to 65+, `pickX()`
functions from ~30 to 45 — new use-case domains (collaborative editing, video conferencing,
micro-frontends, event-driven sagas, multi-tenant SaaS, marketplaces, ML feature stores,
search/recommendation), a directional cost estimator (`pickCostEstimate`), a 4-group
vendor-alternatives comparison layer (`pick*Vendor()` functions + their data tables, ~17 new
functions), governance/security dimensions (Waterfall/Agile, TOGAF/SAFe, COBIT/ITIL,
mTLS+SPIFFE/SPIRE), and `pickVRAMTier()` was replaced entirely by a 5-tier `pickComputeTier()`
continuum plus a new `pickRuntime()` (Ollama/OpenRouter/direct-SDK) decision.

`app/rule_engine.py` was fully re-ported against this expanded source — not patched
incrementally — and re-verified the same way as the original port: JS extracted from the
current `index.html`, executed under Node, diffed against the Python port's output. Scenario
set expanded to **41 total** (the prior 33 plus 8 new scenarios specifically targeting the new
dimensions: live-multiplayer/leaderboard, collaborative editing, video conferencing/
telehealth, micro-frontends, saga workflows, multi-tenant SaaS, marketplaces, ML feature
stores, search/recommendation, semantic routing, social-feed fan-out, geospatial/fleet,
fixed-scope/government delivery, TOGAF/SAFe, COBIT/ITIL, mTLS/SPIFFE, mobile/web BFF,
Ollama/OpenRouter runtime selection, on-device mobile/tablet sizing, and both cost-estimate
scale tiers). **Zero diffs across all 41.**

This re-port also added `pick_cost_estimate()`, `pick_compute_tier()`, `pick_runtime()`, and
the full vendor-comparison layer (`pick_cloud_vendor()` through `pick_frontend_vendor()`, plus
their `*_VENDORS` data tables) to the Python port and to `recommend_stack()`'s output shape —
the MCP tool's `recommend_stack()` output now includes `cost_estimate`, `compute_tier`,
`runtime`, and per-category `*_vendor` keys that didn't exist in the original port. This is a
response-shape change for any existing MCP client code parsing the old category set — see
`backend/tests/test_rule_engine.py` for the updated set of expected top-level keys.
