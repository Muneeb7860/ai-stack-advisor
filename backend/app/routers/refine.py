"""STUB — build order milestone 2 (see backend/KICKOFF_BRIEF.md).

Spec (from docs/design-doc-v2.md Section 7 + PRD FR-27):
  POST /api/refine
  Body: { requirement_text: str, recommendations: dict, anthropic_api_key: str }
  - anthropic_api_key comes from the REQUEST, not server env — see .env.example note.
    Never log it, never persist it, pass it straight to the Anthropic SDK client for this
    one call and let it go out of scope.
  - Send the v1 rule-engine output + original text to Claude. The system prompt must
    constrain the model to REASONING ABOUT the existing recommendation, not re-deriving a
    new one from scratch (DDD 4.3 invariant) — every adjustment the model proposes must
    cite a specific reason traceable back to requirement_text, not a generic preference.
  - Only override a v1 pick when the model can cite that specific reason (design doc
    Section 9.2). If it can't, leave the pick alone and surface it as an "open question"
    instead of a silent override.
  - Persist the result as a RefinementResult row (append-only — never update/overwrite a
    prior refinement pass; that history is what makes the "disagreement rate" success
    metric in BRD Section 7 measurable later).
  - Response should return both the adjusted picks AND the original v1 picks side by side,
    so the frontend can render "AI suggested changing X because Y" without losing the
    original rule-engine reasoning.

This file intentionally raises 501 so the endpoint fails loudly instead of silently doing
nothing if it's accidentally left unwired.
"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["refine"])


@router.post("/refine")
def refine():
    raise HTTPException(
        status_code=501,
        detail="Not implemented yet — see backend/app/routers/refine.py docstring and "
        "docs/design-doc-v2.md Section 7 for the full spec.",
    )
