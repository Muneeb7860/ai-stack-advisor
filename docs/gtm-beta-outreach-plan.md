# GTM / beta-outreach plan

Status: **draft, not started**. Written to satisfy the two open business requirements this
product actually has — not a generic startup-launch template. Every claim about the product
below was checked against the current codebase before being written; every claim about
audiences, channels, or timing is this document's own judgment, not something I can verify,
and is flagged as such.

## Why this exists, specifically

Two Business Requirements have been open since the BRD was written and are still unmet
(`docs/brd_gen.js` Section 6/9):

- **BR-7**: "The product must reach real external users to test demand and recommendation
  quality before further feature investment." Status: not met — zero external users to date.
- **BR-8**: "The product must define and commit to a primary target segment... to focus
  positioning and future feature investment." Status: not met — open decision.

This plan's job is to close both, using the five metrics the BRD already defines (Section 7:
completion rate, re-use rate, disagreement rate, segment concentration, cost per active user) —
not to invent new success criteria. It deliberately does not try to pick BR-8's segment for you;
picking it *from real usage data* is the point of running this plan, not a precondition for it.

**One thing changed since that risk register was written**: the BRD's own risk mitigation note
(Section 8) says "track disagreement rate once feedback capture exists" — as of the "Challenge
This Pick" widget (merged), it exists. This plan is the first chance to actually use it.

## Deployment status (Resolved)

**The site is live on GitHub Pages.** Served directly from the master branch root:
- **Landing page**: `https://muneeb7860.github.io/ai-stack-advisor/landing.html`
- **App**: `https://muneeb7860.github.io/ai-stack-advisor/index.html`

Both `landing.html` and `index.html` run 100% client-side with zero backend dependencies, satisfying NFR-5. The v2 backend (refine/ask/share) remains optional and opt-in. Week 1's deployment prerequisite is complete.

## The metrics constraint this plan has to respect

NFR-1 states v1 "must run entirely client-side with zero external network calls." That's a
real, deliberate privacy posture — it also means **no drop-in analytics tool** (Plausible,
GA, PostHog) can be added to `index.html`/`landing.html` without either violating that NFR or
making it opt-in and disclosed, which is a real product decision, not a GTM detail to slip in
quietly. Two of the five BRD metrics (completion rate, re-use rate) genuinely need *some* way
to count sessions; the other three (disagreement rate, segment concentration, cost per active
user) can be measured without any client-side tracking at all:

- **Disagreement rate**: already captured, per-session, in `localStorage['stack_challenges']`
  and (when an analysis was persisted) the backend `disagreements` table — readable today via
  a direct DB query, no dashboard needed yet for a beta-scale cohort.
- **Segment concentration**: ask beta testers directly (a one-question intake form: "which of
  these three best describes you") rather than inferring it from behavior — more reliable at
  small scale anyway.
- **Cost per active user**: only relevant once the v2 backend is deployed and receiving real
  traffic; not applicable to a v1-only beta.

If you want completion/re-use rate for real, the honest options are: (a) a same-origin,
self-hosted, cookieless counter (e.g. a single `<img>` pixel to a small endpoint you control,
disclosed in the page), or (b) skip automated tracking entirely for this beta round and rely on
direct outreach follow-up ("did you come back and use it again?"). Not deciding this here —
flagging it as the one real product decision this plan can't make for you.

## Segment-testing strategy (not segment-picking)

Since BR-8 is explicitly open, this plan runs small, direct outreach to **all three** segments
in parallel rather than guessing one — the BRD's own segment-concentration metric is the whole
point of doing it this way:

| Segment | Where a first cohort plausibly exists | What to ask them to do |
|---|---|---|
| Developer / technical founder | Communities where people already discuss AI-app architecture choices | Run one real analysis on something they're actually building, then use "Challenge This Pick" on anything they'd have picked differently |
| Non-technical founder | Founder-community spaces, indie-hacker circles | Same task, framed around "does the plain-language rationale make sense without a technical background" |
| Enterprise architect / TPM | Harder to reach cold — likely needs warm intros, not a cold post | Same task, framed around whether the KRA/KPI/governance output is usable as a real internal document |

I'm naming category types, not specific platforms/subreddits/Slacks — which exact communities
are appropriate is a judgment call about tone and rules-of-the-forum that depends on your own
standing there, not something to prescribe generically.

## Suggested cadence (adjust freely — this is pacing, not a commitment)

**Week 1** — Deploy (**Done**: live on GitHub Pages at `muneeb7860.github.io/ai-stack-advisor`), confirm `landing.html`'s CTA resolves to `index.html`, and do a final read-through of the landing copy.

**Weeks 2-3** — Direct, warm outreach only: people you already know across the three segments.
Goal: 10-15 real analyses run, each followed up with "did anything feel wrong or generic?" —
this is where "Challenge This Pick" earns its keep; every disagreement is a concrete, checkable
signal about the rule engine, not vague sentiment.

**Weeks 4-6** — Wider, colder outreach into the community types above, still manually tracking
segment via direct follow-up rather than inference. Review the accumulating disagreement log
(query the `disagreements` table / aggregate `stack_challenges` exports manually — no dashboard
exists yet; building one is a real, separate follow-up if this scales past what manual review
can handle).

**Weeks 7-9** — With real disagreement data in hand, this is the actual decision point for
BR-8: which segment produced the most engaged usage, and does the recommendation logic need a
real fix (not just a UI tweak) based on what people actually disagreed about. This is where
the plan hands back a real decision to you, grounded in data this session couldn't have
generated on its own.

**Weeks 10-12** — Only if the above shows real signal: broader public posting (technical
teardown / "show and tell" framing, on whichever platform fits the winning segment) — a public
launch aimed at an audience you now have actual evidence for, not a guess made in week 1.

## What this plan deliberately does not include

- **No fabricated launch copy or platform-specific post drafts** — writing "Show HN" copy
  before knowing which segment resonates would be optimizing for a guess, and copying the
  earlier GTM report's specific post titles/community names risks repeating claims about how
  those communities would react that nobody has actually tested.
- **No aggregate disagreements dashboard build** — real, useful, but its own scoped feature
  (flagged already in `docs/challenge-this-pick-spec.md`), not bundled into this plan.
- **No committed BR-8 answer** — that's the output of running this plan, not an input to it.
