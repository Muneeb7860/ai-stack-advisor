# AI Stack Advisor — eval harness + constraint classifier

Two changes, in the order they should be done.

**First, measurement.** Right now every KB edit, retrieval change and prompt tweak
is unverifiable drift — there is no way to know whether moving to ChromaDB
embeddings improved the advisor or merely changed its outputs. This package makes
the advisor's quality a number that moves.

**Second, the constraint classifier.** A stage that runs before any recommendation
and decides whether a technology answer is the useful output at all. Roughly a
third of real requests are gated by regulation, contracts, team capacity or missing
data, and for those a confident stack recommendation looks identical to a
well-grounded one. The harness exists first so the classifier's effect is provable
rather than asserted.

---

## Quick start

```bash
pip install -r requirements.txt

# 1. Smoke-test the harness itself against the built-in mediocre advisor.
python -m evalkit.runner --adapter mock

# 2. Wire your advisor (edit adapter.py, or just set the env var).
ASA_ADAPTER=http ASA_ADVISOR_URL=http://localhost:8000/advise \
  python -m evalkit.runner --adapter http --out runs/first.json

# 3. Later, after changing the KB or a prompt — diff against that run.
python -m evalkit.runner --adapter http \
  --baseline runs/first.json --fail-on-regression
```

The mock advisor is deliberately mediocre: it always answers with a stack, never
states a binding constraint, never rules anything out, and is confident regardless.
It scores about **0.02**. A perfect advisor scores **1.00**. That spread is the
room you have to work in.

---

## The review gate — read this before trusting any number

Every golden answer in `cases/` ships as `status: DRAFT`. **Draft cases run and are
reported, but are excluded from the headline score.**

This is not bureaucracy. A benchmark whose answers were drafted by a model measures
agreement with that model, not architectural correctness. The corrections you make
during review are the only point at which your judgment actually enters the system —
they *are* the ground truth, and the drafts are just a way of saving you the typing.

**Review workflow, one case at a time:**

1. Read the PRD in `input.text`. Answer it yourself before reading the golden.
2. Correct `binding_constraint` and `scope_verdict` — these are the highest-weight
   rules and the ones I'm most likely to have drafted wrong.
3. Correct `domains.*.acceptable`. Be generous here. A narrow acceptable set trains
   the advisor to memorise the eval rather than reason; if a competent architect
   wouldn't object, it belongs in the set. `preferred` is where your opinion goes.
4. Check `forbidden` and `unacceptable` are genuinely defects, not just second-best.
5. Rewrite `reasoning_rubric` in your own words — it is what the LLM judge grades
   against, so my phrasing there directly shapes the judge's behaviour.
6. Set `status: REVIEWED`, and fill `reviewer` and `reviewed_at`.

Expect to substantially rewrite several. That is the process working, not failing.
Ten reviewed cases beat fifteen drafted ones.

---

## What's in the corpus

15 cases, chosen to span the constraint taxonomy rather than to hit a round number —
a bigger corpus of similar cases would inflate the count without testing anything new.

| Constraint | Cases | Scope verdicts |
|---|---|---|
| technology | 5 | all `full` |
| regulatory | 3 | all `partial` |
| commercial | 2 | 1 `wrong_question`, 1 `partial` |
| organizational | 2 | 1 `wrong_question`, 1 `partial` |
| data | 2 | 1 `wrong_question`, 1 `partial` |
| product | 1 | `wrong_question` |

The four `wrong_question` cases are load-bearing. They are the ones a
stack-recommender-shaped system fails silently, and they are why the corpus isn't
just fifteen variations on "which database".

Add cases as you hit real failures. The cheapest source of good eval cases is a
recommendation that turned out wrong in practice — write it up the day it happens.

---

## Scoring

**Rules (deterministic, 70% weight when the judge is on, 100% when it's off):**

| Rule | Weight | Checks |
|---|---|---|
| R1 binding_constraint | 3.0 | Did it identify what actually gates the project |
| R2 scope_verdict | 2.0 | Did it know how much of the problem it addresses |
| R3 required_flags | 4.0 | Recall on preconditions that must be surfaced |
| R4 no_forbidden | 5.0 | Did it recommend something disqualified (hard fail) |
| R5 domain_acceptable | 3.0 | Per-domain choice within the acceptable set |
| R6 domain_preferred | 1.0 | Bonus for the preferred option |
| R7 wellformed | 1.0 | Structural sanity |
| R8 ruled_out_present | 1.5 | Did it show what it rejected |

Weights encode what being wrong costs. Recommending a disqualified option (R4)
outweighs picking the second-best database (R5), because one wastes a month and the
other wastes an afternoon. Tune them — they are your opinion, not a constant.

R4 matches against recommendation fields only, never the full text, so an advisor
that correctly names a bad option in `ruled_out` isn't punished for mentioning it.

**Judge (LLM, 30% weight):** grades reasoning quality on grounding, trade-offs,
alternatives and honesty. It does *not* decide correctness — the rules already did
that against a human-reviewed golden. Judge scores are reported separately from rule
scores so a drifting judge model can never silently move your headline number.

Backends: `--judge anthropic` (needs `ANTHROPIC_API_KEY`) or `--judge ollama`
(uses your existing local setup, noisier, free). Default is `none`.

**Calibration penalty:** up to −0.25, proportional to how much of the rule score was
missed times how loudly the advisor asserted itself. This is the metric behind
improvement #2 on the list. The report prints accuracy at each confidence level; a
flat row means the badge carries no information and is transferring unearned trust.
The mock scores 60 high-confidence cards at 0.0 accuracy, which is exactly the
shape of the problem.

---

## The constraint classifier

`classifier/PROMPT.md` is the specification — taxonomy, seven decision rules, output
schema. `classifier/classifier.py` runs it. It reads the request and nothing else:
no retrieval, no KB. It is answering a question about the shape of the problem, and
handing it the KB would only tempt it to reach for a stack.

Wire it in ahead of card generation:

```python
from classifier.classifier import classify, apply_to_cards

verdict = classify(prd_text)
cards   = generate_cards(prd_text)           # existing pipeline, unchanged
cards   = apply_to_cards(verdict, cards)     # caps confidence, adds context
return {**verdict.to_payload(), "cards": cards}
```

`apply_to_cards` is the part that changes behaviour rather than adding a field: on a
`wrong_question` verdict it caps every card at low confidence and marks it
low-impact. A high-confidence database recommendation on a problem gated by a
carrier contract is the exact failure this stage exists to stop.

Iterate on the prompt with the fast loop — no retrieval, no cards, runs in under a
minute:

```bash
python tools/eval_classifier.py --backend anthropic
```

It prints a confusion matrix. **Watch the `wrong_question` row.** A classifier that
never returns it hasn't learned to say no, which is the entire capability being
added. If you find yourself softening decision rule 7 to make the numbers look
better, you are removing the feature.

---

## CI

```bash
python -m evalkit.runner --adapter http \
  --baseline runs/last-good.json \
  --fail-on-regression --fail-under 0.65
```

Use both flags. `--fail-under` catches the floor falling out; `--fail-on-regression`
catches the more common and more dangerous case — a change that raises the mean
while quietly breaking three cases. The mean alone will never show you that.

---

## Layout

```
adapter.py                  the only file you must edit — mock/http/import
requirements.txt
cases/*.yaml                15 golden cases, all DRAFT until reviewed
evalkit/schema.py           case + advisor output + result contracts
evalkit/loader.py           YAML -> EvalCase
evalkit/rules.py            deterministic scoring + calibration
evalkit/judge.py            LLM judge (anthropic | ollama | none)
evalkit/runner.py           CLI entry point, baseline diffing
evalkit/report.py           markdown report rendering
classifier/PROMPT.md        constraint taxonomy + decision rules (the spec)
classifier/classifier.py    classifier + apply_to_cards integration
tools/make_cases.py         regenerates the starter corpus (run once)
tools/eval_classifier.py    fast classifier-only loop with confusion matrix
runs/                       run records (JSON) and reports (markdown)
```

---

## Order of work

1. Review the 15 goldens. Nothing below this line means anything until that's done.
2. Wire `adapter.py` to the current advisor. Record the run as your baseline —
   including whatever embarrassing number it produces. That number is the point.
3. Build the classifier into the pipeline. Re-run. R1 and R2 should move first,
   and the calibration table should stop being flat.
4. Only then start changing the KB, with `--fail-on-regression` in CI.

Doing 3 before 2 is the tempting mistake: you'll have no evidence the classifier
helped, which puts you back where you started.
