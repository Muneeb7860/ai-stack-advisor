# ai-stack-advisor — agent contract

Workspace-wide rules live in `../AGENTS.md`. This file carries only what binds *this* repo.

Every rule below answers two questions: **why does it exist**, and **what would you observe if it
were violated**. A rule with no answer to the second is not enforceable and does not belong here.

---

## The invariants

**Single file, no build step, no dependencies, works offline.** `index.html` is the whole
frontend. No React, no `.tsx`, no bundler, no npm package for the frontend, no CDN script. This is
the product's own promise, not a preference: the README says "no build step, no dependencies, no
server, works offline", and NFR-1/NFR-5 require the core analysis to run with zero network calls.
A single dependency breaks all of it — the file stops opening from `file://`, and the offline
claim on the landing page becomes false.
*Violation looks like*: a `package.json` appearing at the repo root, or a `<script src="http…">`.

**Two engines, one behaviour.** `index.html` and `backend/app/rule_engine.py` are independent
implementations of the same rules — v1 must run fully client-side, so neither can import the
other. Any change to one is a change to both, in the same commit.
*Violation looks like*: `test_engine_differential.py` failing, or a user getting different picks in
the browser than from `/api/refine` and the MCP tool. Both have happened — `strong_on_prem` was
missing six keywords on the Python side, and the Huawei Cloud branches existed only in the browser.

**The engine never invents a single cost figure.** Costs are per-category bands, some of which
read "Not applicable — capex, not opex". Summing them claims precision the product refuses to
claim. Locked by `test_hero_does_not_invent_a_single_cost_figure`.

**Entry-mode parsing is frontend-only.** `parseDiagramInput`, `parseManifest`,
`ingestDocument` and `synthesizeRequirementText` have no Python twin by design, so they carry no
parity surface. Don't port them; don't add parity tests for them.

---

## Adding a recommendation category

Four separate bugs came from adding a category and missing one of the places that enumerate them.
Each was invisible in the card itself and only surfaced one interaction deeper. Wire all of these,
or the tests below will tell you which you missed:

| Wire it into | Missing it looks like |
|---|---|
| both engines | the browser and the API disagree |
| `KEYMAP` in `test_engine_differential.py` | parity is never actually compared — six categories shipped this way |
| `STACK_CARD_CATEGORY` | the card renders but Refine/Ask/Challenge can't find it |
| `VALID_CATEGORIES` (`routers/refine.py`) | the one card the backend silently refuses to refine |
| `CATEGORY_VENDORS` | "Challenge this pick" shows an empty box instead of the real alternatives |
| `OVERRIDE_EFFECT_CARDS` | the override dialog states "no recommendation changes" when there are some |
| the domain floors (`browserExtension` / `cliTool` / `staticSite`) | a hosted SaaS recommended to a stack with nothing to host it on |

`test_category_wiring.py` derives the required set from the code rather than listing it, so it
catches the next one too.

---

## Testing

**Run it, don't cite it.** `cd backend && python3 -m pytest`. Report the number *that run*
produced, never one copied from a document. A pass count in a file is a claim about the past that
looks identical to a claim about the present, and this repo has had a stale one used to assert a
green baseline that was not real.

**Mutation-test every new assertion.** Revert the thing the test is meant to catch, watch the test
fail, restore. A test that has never failed has not been shown to test anything.
*Violation looks like*: a test that stays green while the code it guards is broken. This has
happened repeatedly here — a contrast test that read the token instead of the selector, an
Escape-handler test that matched a commented-out call, a provenance test that matched the word
"provenance" in the function's own source.

**Check the baseline is green before reading a mutation result.** A mutation "passing" is
meaningless if the suite was already failing, and that reading looks like good news.

**Strip comments before asserting on source text.** Several tests here have matched their own
explanatory prose — including comments that exist specifically to say why a value was *not* used.

**Landing-page numbers are asserted, not decorative.** `landing.html` says of itself that every
number on it is a real, currently-shipping count — so a stale one there is worse than anywhere
else on the site. Two had drifted before the guard existed (933 tests against 1,005; 53 pick
functions against 58). `test_landing_claims_are_current.py` now derives both from the code; update
the page when the suite grows past the band.

---

## Docs

`docs/*.docx` are generated from `docs/*_gen.js` — edit the generator, then `npm run gen:brd` /
`gen:prd`, and verify by extracting `word/document.xml`. "Written" is not "correct".

The DDD covers backend aggregates only. If a change doesn't touch `backend/app/models.py`, it
needs no DDD update — check the diff rather than assuming.
