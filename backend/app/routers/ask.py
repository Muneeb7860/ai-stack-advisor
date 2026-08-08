"""POST /api/ask — v2 milestone 3 (see backend/KICKOFF_BRIEF.md, docs/design-doc-v2.md
Section 3.3 "Follow-up Q&A", and PRD Section 9.2 / FR-27's companion user story).

Doc-citation fix: the original stub cited "design-doc-v2.md Section 9.2" — that section
doesn't exist in that file (design-doc-v2.md only goes to Section 7). Section 9.2 is
actually in the PRD ("9.2 v2 — Designed, Pending Backend Access"); the /api/ask-specific
design detail lives in design-doc-v2.md Section 3.3. Corrected here so the next reader isn't
sent looking for a section that isn't there. (Same mislabel existed on RefineResponse's
docstring in schemas.py — fixed there too; the correct cite for /api/refine is Section 3.2.)

Grounded follow-up Q&A, scoped STRICTLY to one Analysis (DDD 4.3 invariant): the system
prompt restricts the model to reasoning about the existing recommendation, never re-deriving
a new one — and unlike a prompt-only restriction, every DB query in this handler filters by
analysis_id structurally (fetching the Analysis row, fetching prior ConversationMessage rows),
so scoping doesn't depend on the model choosing to respect it.

Conversation history: every prior ConversationMessage for this analysis_id is replayed to the
model in request order, so a multi-turn follow-up conversation has real context, not just the
latest question in isolation. Both the new question and the model's answer are persisted as
ConversationMessage rows (role="user" / role="assistant") only AFTER a successful model call —
a failed call persists nothing, so there's never an orphaned question-with-no-answer row.

Model choice: design-doc-v2.md Section 4 lists Sonnet for refine/ask, with "Haiku as a
cheaper fallback for simple follow-up questions." Defaulting to Sonnet here, matching
/api/refine, for consistency and because grounded-Q&A correctness matters more than the
marginal cost saving at this scale. Complexity-based routing to Haiku is a real future
optimization, not implemented in this milestone — flagging it rather than silently deciding
it's out of scope forever.

API key handling: identical to /api/refine — request-scoped, never logged, never persisted.

RAG grounding (KICKOFF_BRIEF.md decision #6): retrieved from docs/use-case-knowledge-base/
(app/retrieval.py) using the user's QUESTION as the query, not the original requirement text —
per 00-INDEX-AND-INGESTION-GUIDE.md §2, "Anti-patterns sections are high-value retrieval
targets for /api/ask... a large share of real follow-up questions are 'is X okay?'" — that
phrasing is exactly what the question text itself carries, and exactly what the corpus's
anti-patterns sections were written to answer. Same best-effort framing as /api/refine: no
match found is a normal outcome, not an error, and /api/ask's core grounding (the existing
Analysis's own requirement_text and recommendations, scoped structurally by analysis_id) is
unaffected either way.
"""
import json

from anthropic import Anthropic, APIError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..retrieval import format_citation, retrieve

GROUNDING_SCORE_THRESHOLD = 0.03  # see refine.py's identical constant for the full rationale
GROUNDING_TOP_K = 2

router = APIRouter(prefix="/api", tags=["ask"])

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT_TEMPLATE = """You are answering a follow-up question about an existing \
technology/AI architecture recommendation. You are NOT generating a new recommendation, and \
you are NOT reasoning about any product other than the one described below.

Original requirement text:
{requirement_text}

Full recommendation set (JSON):
{recommendations}
{grounding}
Ground every answer in the requirement text and the recommendation above. If grounding context \
from the architecture knowledge base is provided, you may cite it using its bracketed source \
name — never cite a source that wasn't actually shown to you. If the question asks you to \
reconsider a pick, you may explain the trade-off, but do not silently declare a new official \
recommendation — that only happens through the separate refine flow (POST /api/refine). If the \
user's question relies on information not present in the requirement text, the recommendation, \
or the grounding context, say so explicitly rather than inventing details.
"""


def _build_grounding_context(question: str) -> str:
    """Best-effort RAG grounding keyed on the follow-up question — see module docstring for
    why the question, not the original requirement text, is the retrieval query here."""
    results = [r for r in retrieve(question, top_k=GROUNDING_TOP_K) if r["score"] >= GROUNDING_SCORE_THRESHOLD]
    if not results:
        return ""
    sections = [f"[{format_citation(r)}]\n{r['chunk_text']}" for r in results]
    return (
        "\nGrounding context retrieved from the architecture knowledge base for this "
        "question:\n\n" + "\n\n---\n\n".join(sections) + "\n"
    )


def _run_ask(api_key: str, system_prompt: str, history: list[dict]) -> str:
    """Isolated into its own function so tests can monkeypatch it instead of hitting the real
    Anthropic API — mirrors refine.py's _run_refinement for the same reason."""
    client = Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=history,
        )
    except APIError as exc:
        raise HTTPException(status_code=502, detail=f"Anthropic API error: {exc}") from exc

    for block in message.content:
        if block.type == "text":
            return block.text
    raise HTTPException(status_code=502, detail="Model did not return a text answer.")


@router.post("/ask", response_model=schemas.AskResponse)
def ask(payload: schemas.AskRequest, db: Session = Depends(get_db)):
    analysis = db.query(models.Analysis).filter_by(id=payload.analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Structural scoping (DDD 4.3): filtered by analysis_id, not left to prompt wording alone.
    prior_messages = (
        db.query(models.ConversationMessage)
        .filter_by(analysis_id=payload.analysis_id)
        .order_by(models.ConversationMessage.created_at.asc())
        .all()
    )

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        requirement_text=analysis.requirement_text,
        recommendations=json.dumps(analysis.recommendations),
        grounding=_build_grounding_context(payload.question),
    )
    history = [{"role": m.role, "content": m.content} for m in prior_messages]
    history.append({"role": "user", "content": payload.question})

    answer = _run_ask(payload.anthropic_api_key, system_prompt, history)

    # Persisted only now that the model call actually succeeded — see module docstring.
    user_row = models.ConversationMessage(
        analysis_id=analysis.id, role="user", content=payload.question
    )
    assistant_row = models.ConversationMessage(
        analysis_id=analysis.id, role="assistant", content=answer
    )
    db.add(user_row)
    db.add(assistant_row)
    db.commit()

    all_messages = prior_messages + [user_row, assistant_row]
    return schemas.AskResponse(
        analysis_id=analysis.id,
        answer=answer,
        llm_model_used=MODEL,
        conversation=[schemas.ConversationMessageOut.model_validate(m) for m in all_messages],
    )
