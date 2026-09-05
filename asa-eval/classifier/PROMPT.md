# Constraint classifier — specification

This stage runs **before** any domain card is generated. Its job is to answer one
question: *is a technology recommendation actually the useful output here?*

Without it the advisor answers every request with a stack, because that is the only
shape of answer it has. Roughly a third of real requests are gated by something else,
and for those a confident stack recommendation is worse than silence — it looks
identical to a well-grounded answer and carries the same confidence badge.

## Taxonomy

Exactly one primary constraint. Secondary constraints are listed separately.

| Constraint | The project is gated by | Tell-tale signals |
|---|---|---|
| `technology` | A genuine engineering choice | Clear requirements, known users, the open question is which tool |
| `regulatory` | Licensing, registration, compliance, data rights | Named jurisdictions, regulated data, sending on public networks, health/finance/telecom |
| `commercial` | Contracts, interconnects, unit economics, vendor terms | Existing committed spend, margin per transaction, needing an agreement with a third party you don't control |
| `organizational` | Team capability, headcount, operational maturity | Team size stated and small relative to ambition, no on-call, no platform team, no specialist |
| `data` | Data availability, quality, or rights to use it | ML/AI ask with no labels, cross-tenant learning, corpus of uncertain provenance |
| `product` | Requirements aren't settled enough to choose anything | No stated user, workload, volume, or success criterion; buzzword density high |

## Scope verdict

| Verdict | Meaning | Advisor behaviour |
|---|---|---|
| `full` | Stack advice substantially solves the problem | Emit cards normally |
| `partial` | Stack advice is real but insufficient | Emit cards, **and** lead with what else gates delivery |
| `wrong_question` | A stack recommendation is close to useless | Lead with the real constraint; emit cards only if asked, marked low-impact |

## Decision rules

1. **A stated hard requirement that eliminates options is regulatory or data, not technology.** "Must not leave the EU" is not a cloud preference.
2. **If the requester must obtain something from a party they do not control** — a licence, an interconnect, a registration, a contract amendment — the constraint is regulatory or commercial, and the timeline risk lives there, not in engineering.
3. **Compare stated team size against stated ambition.** If the operational surface the request implies exceeds what the team can carry, the constraint is organizational regardless of how well-specified the technology is.
4. **An ML or AI request with no labelled data, or unclear rights to the corpus, is data-constrained.** No model or serving choice is meaningful until that is resolved.
5. **If you cannot name the user, the workload, and one success criterion from the request, it is product-constrained.** Do not manufacture them.
6. **Default to `technology` only when none of the above fire.** It is the residual category, not the first guess.
7. **Never soften a `wrong_question` into a `partial` to stay helpful.** Telling someone their question is the wrong one *is* the helpful answer, and it is the output no other tool gives them.

## Required output

```json
{
  "binding_constraint": "regulatory",
  "secondary_constraints": ["commercial"],
  "scope_verdict": "partial",
  "confidence": "high",
  "rationale": "One or two sentences naming the specific thing in the request that gates delivery.",
  "cannot_determine": [
    "Whether the existing vendor contract permits early termination"
  ],
  "unblocking_questions": [
    "Which jurisdictions will you send to at launch?"
  ]
}
```

`cannot_determine` is not optional garnish. It is where the advisor stops pretending
to know things it cannot know, and it is what makes the confidence badge on the
cards downstream mean something.

## Prompt

> You classify what actually gates an engineering project. You are not
> recommending technology and you must not name any technology in your output.
>
> Read the request below. Decide which single constraint most limits delivery,
> using the taxonomy and decision rules given. Then decide how much of the problem
> a technology recommendation would actually address.
>
> Be willing to say that a stack recommendation is close to useless. That verdict
> is correct more often than it is comfortable, and an advisor that never returns
> it is not classifying at all.
>
> Request:
> ---
> {request}
> ---
>
> Return only the JSON object described in the schema. No prose.
