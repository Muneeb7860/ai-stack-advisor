# Harness Engineering — concept skeleton (draft, market research landed 2026-08-31)

Status: **not implemented, not scoped for a PR**. Market research (below) has now landed and
been independently spot-checked — this doc folds in the verified findings and sharpens the
open questions, but shape (A vs. B) and scope are still not decided. That's a conversation to
have together, not something to lock in overnight.

## Market research: "Four Kinds of Harness" (2026-08-30 survey)

Full report: https://claude.ai/code/artifact/beb45641-5214-44c8-8dfa-d4652448dbf7

Shared as a published artifact, cross-checked before folding in — same discipline as
everything else pasted into this session. Verification outcome:

- **The three claims about this workspace specifically were checked directly against the
  filesystem and are all accurate**: `deepseek-harness` is a real git clone of
  `deepseek-ai/deepseek-harness` (`git remote -v` confirms the upstream origin, `package.json`
  name is `@deepseek-ai/dsh-root`) — so its `AGENTS.md`/`CLAUDE.md` symlink is upstream's
  discipline, not ours, correcting what `HARNESS_AUDIT.md` implied. `ai_defense_rag` does index
  DeepEval and DeepTeam docs (confirmed by grep). `deepseek-harness/native/landlock-run` is a
  real directory with real README/docs files.
- **The report's central institutional claim — AGENTS.md/MCP/goose under a Linux Foundation
  "Agentic AI Foundation"** — verified independently via web search, not just trusted: real,
  formed 2025-12-09, exact platinum-member list matches (AWS, Anthropic, Block, Bloomberg,
  Cloudflare, Google, Microsoft, OpenAI). This is the report's load-bearing claim and it holds.
- The report itself discloses its own lower-confidence claims in a "Method and caveats"
  section (star counts, single-benchmark cold-start figures, a named list of "individually
  unverified against primary sources" items) — a real, meaningful difference in rigor from the
  earlier pasted "5-Pillar" document, which asserted a fabricated Ed25519 capability with zero
  hedging. Worth trusting this one more, while still not treating unhedged-but-unverified
  figures in it (e.g. exact acquisition dollar amounts) as certain.

### The finding that reframes the product question

"Harness" is four unrelated markets, not one:

| Sense | What it is | Age | Relevant to us? |
|---|---|---|---|
| Packaged coding agent | Claude Code, Codex, Cursor, opencode | 2024– | No — we're not building an agent |
| **Harness framework** | The loop itself as a product: MAF, DeepSeek Harness, eve, Flue, Pi | **2026, genuinely new** | **This is the category "help teams build their own harness" lands in** |
| Execution substrate | E2B, Modal, sandboxes, credential brokering | 2025– | No — infrastructure, not our layer |
| Evaluation harness | Inspect, lm-eval-harness, Harbor, Promptfoo | 2021– | Adjacent — Harbor is literally "the harness factored out as a standalone product" for evals, closest existing analogue to shape B below |

The report's own 5-layer breakdown maps directly onto the PDF's 5 components, with a maturity
read attached to each — this is the most useful single fact for scoping:

| Layer (report's language) | Maturity per report | Product implication |
|---|---|---|
| System of record | **Settled** — AGENTS.md won, Linux Foundation project | Teaching this is just correct advice now, not opinion |
| Tools | **Settled** — MCP universal, also Linux Foundation | Same |
| Verification | **"Thinnest layer in the stack"** | **Likely the best wedge** — explicitly under-served, nobody sells this |
| Guardrails & permissions | **Split in two** — content filtering commoditized to zero, action-level policy bought by security platforms (Check Point/Lakera, Palo Alto/Protect AI, Snyk/Invariant, etc.) | Don't build a guardrails *product* — that market just consolidated into security platforms. Teaching teams to set their *own* allow/ask/deny rules (what `HARNESS_AUDIT.md` actually recommends) is different from selling a guardrails SaaS, and still open |
| Observability & memory | **Consolidating** — OTel GenAI conventions exist but still "Development status" | Too early to standardize against; describe patterns, don't build to a spec yet |

Report's own "Still nobody's problem" list is a second, independent signal pointing at the same
gap: verification ("yours to build," per Pi's own docs), cross-layer policy composition, and
burst-reliability testing are all named as unsolved. Three different angles in one report
converge on **verification/self-audit being the most defensible wedge**, not guardrails or
tooling-inventory (which the earlier "5-Pillar" doc emphasized and which turns out to be exactly
the layer that just got bought out by five different security platforms).

## Where this comes from (full input list)

- `HarnessEngineeringBuildGuide.pdf` (Aishwarya Srinivasan, companion handout) — verified as
  legitimate practitioner material sourced from Hashimoto, OpenAI's Codex harness-engineering
  post, Anthropic's long-running-agent guidance, and Manus's context-engineering post.
- A pasted "5-Pillar Agent Harness Architecture" writeup, which I checked against this
  workspace's actual repos and largely could not verify — see "What's real vs. not"
  below. Treated as a lead to check, not a spec to build from.
- `HARNESS_AUDIT.md` (workspace root) — an existing, independently-produced audit that scored
  this workspace 4/15 on the PDF's own rubric. Still load-bearing: the workspace itself is not
  a reference implementation of the thing we'd be teaching.
- "Four Kinds of Harness" market survey (above) — the newest, best-corroborated input; treat as
  primary for scoping decisions over the PDF or the 5-Pillar doc where they conflict.

## What's real vs. not (carried over from the verified analysis)

| Claim | Status |
|---|---|
| PDF's 5-component model (system of record, tools, verification, guardrails, observability) | Real, well-sourced |
| PDF's 15-point self-audit rubric | Real, directly reusable as a product mechanic |
| `agentic-redteam` — 65 real security probes | Verified (ran the suite myself) |
| `swishos-agent-tooling` — Ed25519 signing / crypto governance | **Fabricated.** Repo is actually a grounding/anti-hallucination tool (`ground_truth.py`, `task_contract.py`) — a different, real, but unrelated idea |
| Workspace as a whole is a "battle-tested harness" | **False per `HARNESS_AUDIT.md`** — scores 4/15, zero deny/ask rules, 298 unreviewed allow rules, root config not version-controlled |
| `ai-stack-advisor`'s own dual-engine parity + mutation testing | Real, and arguably the best-executed harness component in the workspace — this product's own test discipline is a legitimate case study, not a claim |

## Candidate product shape (for discussion, not decided)

Two shapes this could take. The market survey doesn't fully settle A vs. B on its own — that
still needs a real conversation — but it does sharpen what either shape should actually score,
which is the part I'd have otherwise guessed at:

**A. A feature inside ai-stack-advisor** — after the stack recommendation, offer a "Harness
Readiness" pass: same detect-signals → pick → recommend architecture already used for every
vendor category this session, but scoring the user's own team/repo description against the
5-component rubric instead of recommending a vendor. Natural fit if the buyer is the same
person already using the stack advisor (an architect scoping a new build) and wants harness
readiness as one more section of the same report.

**B. A standalone tool** — a CLI or web scorer that takes a repo (or a description of one) and
produces the Appendix B scorecard directly, with fix-order output matching `HARNESS_AUDIT.md`'s
own "ranked by leverage" structure. Report's closest real analogue is **Harbor** (Laude
Institute) — "the harness factored out as a standalone product," but for evals, not self-audit.
No direct competitor exists yet for "score my own team's harness maturity" specifically — that
gap is real, not just unresearched.

**Whichever shape wins, score verification hardest, not guardrails.** The report independently
converges on this from three directions (the layer maturity table above, the "still nobody's
problem" list, and the guardrail-market-evaporation timeline) — a harness-readiness product that
leads with "here are your allow/ask/deny rules" is walking into a layer five security platforms
just finished buying. Leading with "here's whether your agent can catch its own mistakes before
you do" (the PDF's own framing for step 2, "the highest-leverage step") is the layer the market
survey says is still open.

## Skeleton data model (illustrative — field names/shape will change)

Mirrors the existing `rule_engine.py` signal → pick pattern, adapted to scoring rather than
recommending:

```python
# NOT real code — shape only, for discussion.

HARNESS_COMPONENTS = [
    {"id": "system_of_record", "name": "System of record",
     "question": "What does it need to know?",
     "looks_like": ["AGENTS.md", "CLAUDE.md", "a docs/ tree the root file points into"]},
    {"id": "tools", "name": "Tools",
     "question": "What can it actually do?",
     "looks_like": ["shell access", "file edit", "test runner", "MCP servers"]},
    {"id": "verification", "name": "Feedback and verification",
     "question": "How does it know it worked?",
     "looks_like": ["linter", "type checker", "real test suite", "end-to-end run"]},
    {"id": "guardrails", "name": "Guardrails and permissions",
     "question": "What must it never do?",
     "looks_like": ["allow/ask/deny rules", "sandboxed execution", "approval checkpoints"]},
    {"id": "observability", "name": "Observability and memory",
     "question": "What happened, and what carries over?",
     "looks_like": ["session transcripts", "structured logs", "a progress file"]},
]

SCORE_BANDS = [
    {"range": (0, 4), "band": "Harness consumer", "note": "Using someone else's defaults"},
    {"range": (5, 9), "band": "Real harness exists", "note": "Find the lowest-scoring component"},
    {"range": (10, 13), "band": "Production grade", "note": "Read failures systematically"},
    {"range": (14, 15), "band": "Mature", "note": "Practice subtraction"},
]

def score_component(signals_for_component) -> int:
    """0 = absent, 1 = ad hoc, 2 = deliberate, 3 = self-correcting.
    Real implementation TBD — likely a mix of user-answered questions (can't detect a
    team's actual repo practices from free text the way vendor signals work today) and,
    for shape B, actual repo inspection (grep for hooks, deny rules, AGENTS.md, etc.,
    the same technique used to write HARNESS_AUDIT.md by hand)."""
    raise NotImplementedError
```

## Open questions — what the research answered vs. still doesn't

**Answered by the market survey:**
- Is "harness framework" a real, distinct, currently-forming category worth building for? Yes
  — report calls it "2026's genuinely new category," names 5 funded/shipping entrants (MAF,
  DeepSeek Harness, eve, Flue, Pi), all less than a year old.
- Which layer to lead with? Verification, not guardrails — see above.
- Is there a direct existing competitor for "score your own harness maturity"? Not found —
  Harbor is the nearest analogue and it's eval-scoring, not self-audit.

**Still genuinely open, not something I should guess at:**
1. Shape A vs. B (feature vs. standalone tool) — depends on who the buyer/user actually is
   (an architect already using ai-stack-advisor, vs. an engineering lead auditing a team), which
   the survey doesn't resolve on its own.
2. For shape B: can scoring realistically be automated (grep a repo for hooks/deny-rules/
   AGENTS.md presence), or does it need a free-text interview like the existing product?
   `HARNESS_AUDIT.md` was produced by a careful manual read — worth checking how much of that
   generalizes into a deterministic checker vs. needs a human/LLM judgment call per repo.
3. Do we use this workspace's own repos as worked examples in the product (`agentic-redteam`'s
   real 65 probes, `ai-stack-advisor`'s own parity+mutation discipline) — that's honest and
   provable — or avoid workspace-specific references entirely for a product meant for other
   teams' repos?
4. Licensing/attribution on the PDF's methodology before building a product visibly derived
   from it — Aishwarya Srinivasan / The Gen Academy is a named source, not public domain.
5. New from the survey: does "verification" as a wedge mean building toward the OTel GenAI
   conventions eventually (report says still "Development status" — too early to commit to) or
   staying spec-agnostic and teaching the pattern the way the PDF does (linter → tests → e2e,
   wired to lifecycle hooks)? Leans toward the latter given the spec's own immaturity, but that's
   a real call to make together, not decided here.

## Non-goals right now

- Not porting `agentic-redteam/tests` or `swishos-agent-tooling/tests` into other repos (the
  pasted document's "how to port" section) — the source material's own guardrail score is 0/15,
  and copying tests without also copying enforcement (hooks, deny rules) propagates the gap.
- Not fixing this workspace's own `HARNESS_AUDIT.md` findings as part of this effort — that's a
  separate, real, and worthwhile cleanup, but orthogonal to whether/how we build a product
  around the concept.
