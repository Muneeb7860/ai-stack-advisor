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

Local-model fallback: identical opt-in contract to /api/refine (provider="ollama" on the
request body + LLM_PROVIDER=ollama on this deployment) — see app/llm_providers.py. Ask's local
path is plain-prose chat completion (no tool-calling schema to satisfy), which is why it was a
safe fallback to ship even before /api/refine's stricter structured-output reliability was
separately verified.

RAG grounding (KICKOFF_BRIEF.md decision #6): retrieved from docs/use-case-knowledge-base/
(app/retrieval.py) using the user's QUESTION as the query, not the original requirement text —
per 00-INDEX-AND-INGESTION-GUIDE.md §2, "Anti-patterns sections are high-value retrieval
targets for /api/ask... a large share of real follow-up questions are 'is X okay?'" — that
phrasing is exactly what the question text itself carries, and exactly what the corpus's
anti-patterns sections were written to answer. Same best-effort framing as /api/refine: no
match found is a normal outcome, not an error, and /api/ask's core grounding (the existing
Analysis's own requirement_text and recommendations, scoped structurally by analysis_id) is
unaffected either way.

Scale-aware retrieval query (Step 2 of the RAG-derivation-engine plan — see
app/retrieval.py's build_scale_aware_query()): the question text alone doesn't say whether
"what audit logging do I need?" is being asked about a college project or a regulated bank,
even though the corpus's own prose answers that differently within the same chunk. This
Analysis's stored `signals` (real when created via POST /api/analyses first, which is the
frontend's actual flow — see index.html's ensureAnalysisId(); {} for an analysis refine.py
created on the fly with no prior /api/analyses call) get folded into the retrieval query text,
not into retrieve()'s ranking logic itself.
"""
import json

from anthropic import Anthropic, APIError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..db import get_db
from ..llm_providers import run_ollama_ask
from ..retrieval import build_scale_aware_query, format_citation, retrieve

GROUNDING_SCORE_THRESHOLD = 0.55  # see refine.py's identical constant for the full rationale
# (re-tuned for the embeddings scale, not the old TF-IDF-era 0.03)
# Raised again from 3 to 5 after the communications domain (doc 19) landed. A requirement that
# names a market ("for Indian businesses", "launching in the EU") carries its binding constraint
# in the regulatory section, but states it as an ordinary business fact while stating its
# technology in jargon — so the technical sections legitimately out-rank it whenever the
# requirement is technically dense. Measured on the India-OTP case: the regulatory chunk ranked
# 4th (0.63) behind the verification ladder (0.722), anti-patterns (0.662) and sender strategy
# (0.658), so top_k=3 handed the model three true-but-secondary chunks and cut the one that
# changes the answer. The chunks are ~1 section each and GROUNDING_SCORE_THRESHOLD still gates
# them, so this widens the window rather than lowering the bar — but it is not free: measured
# across four queries the grounding block grows by ~340-1,030 tokens per call (3,495 -> 7,619
# chars on the India case, 3,194 -> 4,569 on an off-domain control). That is the price of the
# constraint chunk surviving. It does NOT fix the related
# routing-abstention case (a plain-language US-market query is refused by MIN_CONFIDENT_RRF
# before ranking happens) — that one is un-fixed and documented in doc 19's own retrieval notes.
GROUNDING_TOP_K = 5  # see refine.py's identical constant for why (raised from 2, then 3)

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


def _build_grounding_context(question: str, signals: dict | None = None) -> str:
    """Best-effort RAG grounding keyed on the follow-up question — see module docstring for
    why the question, not the original requirement text, is the retrieval query here.

    `signals` (the analysis this question is scoped to — see retrieval.build_scale_aware_query)
    nudges retrieval toward whichever scale-conditioned framing in a matched chunk actually
    applies, without changing which chunk gets matched by topic. None/{} (an analysis created
    via a direct /api/refine call with no prior /api/analyses — see refine.py's docstring) is a
    real, expected case, not an error — degrades to the unmodified question, same as before this
    existed."""
    query = build_scale_aware_query(question, signals)
    results = [r for r in retrieve(query, top_k=GROUNDING_TOP_K) if r["score"] >= GROUNDING_SCORE_THRESHOLD]
    if not results:
        return ""
    sections = [f"[{format_citation(r)}]\n{r['chunk_text']}" for r in results]
    return (
        "\nGrounding context retrieved from the architecture knowledge base for this "
        "question:\n\n" + "\n\n---\n\n".join(sections) + "\n"
    )


def _run_ask(api_key: str, system_prompt: str, history: list[dict]) -> tuple[str, dict]:
    """Isolated into its own function so tests can monkeypatch it instead of hitting the real
    Anthropic API — mirrors refine.py's _run_refinement for the same reason.

    Returns (answer, usage) — usage is {"input_tokens": int, "output_tokens": int} read
    straight from message.usage, the real count for this one call, not an estimate."""
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

    usage = {"input_tokens": message.usage.input_tokens, "output_tokens": message.usage.output_tokens}
    for block in message.content:
        if block.type == "text":
            return block.text, usage
    raise HTTPException(status_code=502, detail="Model did not return a text answer.")


@router.post("/ask", response_model=schemas.AskResponse)
def ask(payload: schemas.AskRequest, db: Session = Depends(get_db)):
    if payload.provider == "ollama" and settings.llm_provider != "ollama":
        raise HTTPException(
            status_code=400,
            detail="Local model fallback (provider='ollama') is not enabled on this deployment "
            "(set LLM_PROVIDER=ollama).",
        )

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
        grounding=_build_grounding_context(payload.question, analysis.signals),
    )
    history = [{"role": m.role, "content": m.content} for m in prior_messages]
    history.append({"role": "user", "content": payload.question})

    if payload.provider == "ollama":
        answer, usage = run_ollama_ask(settings.ollama_base_url, settings.ollama_model, system_prompt, history)
        model_used = settings.ollama_model
    else:
        answer, usage = _run_ask(payload.anthropic_api_key, system_prompt, history)
        model_used = MODEL

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
        usage=schemas.UsageInfo(**usage),
        llm_model_used=model_used,
        conversation=[schemas.ConversationMessageOut.model_validate(m) for m in all_messages],
        provider=payload.provider,
    )
