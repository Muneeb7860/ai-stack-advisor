"""POST /api/refine — v2 milestone 2 (see backend/KICKOFF_BRIEF.md, docs/design-doc-v2.md
Section 7/9.2, and PRD FR-27).

LLM-assisted second pass over an existing v1 rule-engine result. Constrained by design: the
model may only ADJUST specific category picks, each with a reason it can cite back to
requirement_text — it never re-derives a full recommendation set from scratch (DDD 4.3
"Refinement Context ... cannot override [Analysis Context's] structure, only annotate/adjust
specific picks with cited reasons"). If the model can't cite a specific reason for a category
it's unsure about, that goes into open_questions instead of a silent override — see
SYSTEM_PROMPT below.

API key handling (locked decision — see .env.example and README "API key handling"):
anthropic_api_key comes from the REQUEST BODY, never server env. It's passed straight to the
Anthropic SDK for this one call and allowed to go out of scope at the end of the request —
never logged, never persisted (it is NOT one of RefinementResult's columns in models.py).

Local-model fallback (opt-in, NOT the default — see app/llm_providers.py's module docstring
for the real measured reliability numbers): passing `provider: "ollama"` on the request body
routes this call to a local Ollama model instead of Claude, IF this deployment has also set
LLM_PROVIDER=ollama (config.py) — both sides must opt in. Claude remains the default/primary
path for every caller that doesn't explicitly ask for the local one. The local path's
rationale is prefixed with a visible disclaimer and the response's `provider` field is set to
"ollama" so callers can render it with visibly lower confidence, never with the same authority
as a Claude-backed result.

Design gap resolved here, not silently: the docstring this file originally shipped with
specified a request body of { requirement_text, recommendations, anthropic_api_key } with no
analysis_id, but RefinementResult.analysis_id is a non-null FK. Resolution (see
schemas.RefineRequest): analysis_id is optional on the request — omitted means "create a new
Analysis from this text+recommendations first," matching the ERD's own framing that "an
Analysis is created the moment a v1 result is first sent to the backend for refinement OR
sharing." Provided means "attach this refinement to an already-persisted Analysis." Flagging
this so it's revisited deliberately if it turns out to be wrong, not discovered as a surprise.

Guardrails per design-doc-v2 Section 3.2 ("the tool practicing what it recommends"):
- Input length cap: enforced in schemas.RefineRequest (max_length=10_000 on requirement_text).
- Output schema validation: enforced by requiring the model to call a tool with a fixed
  input_schema (REFINEMENT_TOOL) rather than parsing free-form prose.
- No execution of anything the model returns: adjusted_picks/rationale/open_questions are
  stored and displayed as data, never interpreted as instructions or code.
- Rate limiting per session: NOT implemented in this milestone — there is no session/user
  concept yet in this schema (no accounts, by design). Flagging as a real gap rather than
  claiming it's covered; revisit if abuse becomes a concern before accounts ever exist.

RAG grounding (KICKOFF_BRIEF.md decision #6, added when the frontend-expansion session's
docs/use-case-knowledge-base/ corpus landed): grounding context is retrieved from that corpus
(app/retrieval.py's two-stage design — see RETRIEVAL-PROTOTYPE-FINDINGS.md) and injected into
the prompt so the model reasons from sourced, citable material for any of the 8 newer use-case
domains, rather than free-associating from parametric memory — consistent with why the v1 rule
engine is transparent/rule-based in the first place. Grounding is best-effort: if retrieval
returns nothing relevant (e.g. the requirement doesn't touch any of the 11 covered domains),
refine proceeds without it exactly as it did before this corpus existed — RAG augments the
existing rule-engine-critique flow, it doesn't gate it.
"""
import json

from anthropic import Anthropic, APIError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..db import get_db
from ..llm_providers import run_ollama_refinement
from ..retrieval import format_citation, retrieve

# Re-tuned when app/retrieval.py moved from TF-IDF to embeddings (ChromaDB + Ollama
# nomic-embed-text) — the old value (0.03) was calibrated to TF-IDF's sparse lexical scoring
# scale, where a truly unrelated query scores ~0.0. Embedding cosine similarity does not have
# that property (a well-known embedding-space characteristic: even semantically unrelated text
# pairs tend to score 0.4-0.55+), so 0.03 stopped doing any filtering at all post-migration —
# verified empirically, not assumed: "Tell me a joke about cats." (zero legitimate overlap
# with this corpus) now scores ~0.54 under embeddings. Re-measured the actual score bands
# post-migration: several genuinely irrelevant queries ("What is the capital of France?", "How
# do I bake sourdough bread?", "Recommend a good sci-fi movie.") top out at ~0.49-0.54, while
# the WEAKEST genuine hit across the full eval suite's direct-retrieval cases scores ~0.594.
# 0.55 sits in that empirically-measured gap. Same trade-off as before still applies at the
# new number: an irrelevant-but-plausible-sounding technical query can still slip through
# (costs prompt space, not correctness — the system prompt instructs the model to only cite
# what it can actually justify), while true off-topic queries are filtered.
GROUNDING_SCORE_THRESHOLD = 0.55
GROUNDING_TOP_K = 3
# Raised from 2 when GROUNDING_SCORE_THRESHOLD was re-tuned for embeddings (see that
# constant's comment): embeddings' narrower score band means a document's own most-useful
# chunk (e.g. an anti-patterns section) can land 3rd rather than in the top 2 by a fraction of
# a point — verified against eval case 12's query, where the anti-patterns chunk scored 0.613
# vs. 0.627/0.616 for two less-directly-useful chunks from the same document. 3 catches it
# without materially growing prompt size.


def _build_grounding_context(requirement_text: str) -> str:
    """Best-effort RAG grounding — returns '' if nothing scores above threshold, which is a
    valid, expected outcome (see module docstring), not an error."""
    results = [r for r in retrieve(requirement_text, top_k=GROUNDING_TOP_K) if r["score"] >= GROUNDING_SCORE_THRESHOLD]
    if not results:
        return ""
    sections = [
        f"[{format_citation(r)}]\n{r['chunk_text']}" for r in results
    ]
    return (
        "\n\nGrounding context retrieved from the architecture knowledge base (cite these "
        "using the bracketed source name if you use them; do not cite anything not shown "
        "here):\n\n" + "\n\n---\n\n".join(sections)
    )

router = APIRouter(prefix="/api", tags=["refine"])

# Sonnet tier per design-doc-v2.md Section 4's own self-recommendation ("strong
# instruction-following for the 'only override with a cited reason' constraint").
MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """You are reviewing an existing technology/AI architecture recommendation \
that was produced by a deterministic rule engine. You are NOT generating a new \
recommendation from scratch.

You will be given:
1. The original free-text business/product requirement.
2. The rule engine's full set of category recommendations, as JSON.

Your job is narrow: identify ONLY the categories where the rule engine's pick is contradicted \
or clearly under-supported by the requirement text, and propose a specific replacement pick \
for that category alone.

Hard constraints:
- Do not propose a change unless you can cite the specific phrase or fact in the requirement \
text that justifies it. A generic stylistic preference is not a valid reason.
- Do not touch categories the rule engine got right — leave them out of adjusted_picks \
entirely. An empty adjusted_picks list is a valid, good answer if nothing is wrong.
- If a category seems debatable but you cannot point to a specific textual reason, raise it \
as an open question instead of silently overriding it.
- Never invent a new category that was not present in the original recommendation set.
- If grounding context from the architecture knowledge base is provided below, you may use it \
to justify a change, but only by citing the bracketed source name shown with it (e.g. \
"[02-video-audio-conferencing.md § A. Media topology]") — never cite a source that wasn't \
actually shown to you, and never treat the absence of grounding context as license to \
free-associate from general knowledge instead of the requirement text itself.
- Call the submit_refinement tool exactly once with your findings. Do not respond in prose.
"""

REFINEMENT_TOOL = {
    "name": "submit_refinement",
    "description": "Submit the results of this refinement pass over the rule engine's output.",
    "input_schema": {
        "type": "object",
        "properties": {
            "adjusted_picks": {
                "type": "array",
                "description": "Only categories actually changed. Empty array if none.",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "pick": {"type": "string"},
                        "reason": {
                            "type": "string",
                            "description": "Must cite specific text from the requirement.",
                        },
                    },
                    "required": ["category", "pick", "reason"],
                },
            },
            "rationale": {
                "type": "string",
                "description": "One-paragraph summary of this refinement pass overall.",
            },
            "open_questions": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["adjusted_picks", "rationale", "open_questions"],
    },
}


def _run_refinement(api_key: str, requirement_text: str, recommendations: dict) -> tuple[dict, dict]:
    """Isolated into its own function so tests can monkeypatch it instead of hitting the real
    Anthropic API — no network calls, no real API key, needed to test this endpoint.

    Returns (result, usage) — usage is {"input_tokens": int, "output_tokens": int} read
    straight from message.usage, the real count for this one call, not an estimate."""
    grounding = _build_grounding_context(requirement_text)
    client = Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=[REFINEMENT_TOOL],
            tool_choice={"type": "tool", "name": "submit_refinement"},
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Requirement text:\n{requirement_text}\n\n"
                        f"Rule engine recommendations (JSON):\n{json.dumps(recommendations)}"
                        f"{grounding}"
                    ),
                }
            ],
        )
    except APIError as exc:
        # Surfaced as a 502 (upstream failure), not a 500 — this backend did nothing wrong,
        # the LLM call itself failed (bad key, rate limit, outage, etc).
        raise HTTPException(status_code=502, detail=f"Anthropic API error: {exc}") from exc

    usage = {"input_tokens": message.usage.input_tokens, "output_tokens": message.usage.output_tokens}
    for block in message.content:
        if block.type == "tool_use" and block.name == "submit_refinement":
            return block.input, usage
    raise HTTPException(status_code=502, detail="Model did not return a refinement result.")


def _run_ollama_refinement_call(requirement_text: str, recommendations: dict) -> tuple[dict, dict]:
    """Isolated the same way _run_refinement() is, for the same testing reason (monkeypatch
    instead of a real local Ollama call in unit tests) — see app/llm_providers.py for the real
    measured reliability numbers this local path is based on."""
    grounding = _build_grounding_context(requirement_text)
    return run_ollama_refinement(
        settings.ollama_base_url,
        settings.ollama_model,
        SYSTEM_PROMPT,
        REFINEMENT_TOOL,
        requirement_text,
        recommendations,
        grounding,
    )


@router.post("/refine", response_model=schemas.RefineResponse)
def refine(payload: schemas.RefineRequest, db: Session = Depends(get_db)):
    if payload.provider == "ollama" and settings.llm_provider != "ollama":
        # Opt-in on both sides, per app/llm_providers.py's module docstring — a caller asking
        # for the local path doesn't get it unless this deployment has also enabled it.
        raise HTTPException(
            status_code=400,
            detail="Local model fallback (provider='ollama') is not enabled on this deployment "
            "(set LLM_PROVIDER=ollama). Falling back silently to Claude would defeat the point "
            "of asking for the offline path explicitly, so this is a hard error, not a silent "
            "reroute.",
        )
    if payload.analysis_id:
        analysis = db.query(models.Analysis).filter_by(id=payload.analysis_id).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
    else:
        # No signals payload in the refine spec's request body — recorded as {} rather than
        # inventing signal data this endpoint was never given. If this Analysis is later
        # fetched via a share link, its `signals` field will legitimately be empty; that's a
        # real, documented gap, not a bug — signals only ever come from POST /api/analyses.
        analysis = models.Analysis(
            requirement_text=payload.requirement_text,
            signals={},
            recommendations=payload.recommendations,
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)

    if payload.provider == "ollama":
        result, usage = _run_ollama_refinement_call(payload.requirement_text, payload.recommendations)
        model_used = settings.ollama_model
    else:
        result, usage = _run_refinement(
            payload.anthropic_api_key, payload.requirement_text, payload.recommendations
        )
        model_used = MODEL

    refinement_row = models.RefinementResult(
        analysis_id=analysis.id,
        adjusted_picks=result["adjusted_picks"],
        rationale=result["rationale"],
        open_questions=result["open_questions"],
        llm_model_used=model_used,
    )
    db.add(refinement_row)
    db.commit()
    db.refresh(refinement_row)

    return schemas.RefineResponse(
        analysis_id=analysis.id,
        original_recommendations=payload.recommendations,
        adjusted_picks=result["adjusted_picks"],
        rationale=result["rationale"],
        open_questions=result["open_questions"],
        llm_model_used=model_used,
        usage=schemas.UsageInfo(**usage),
        provider=payload.provider,
    )
