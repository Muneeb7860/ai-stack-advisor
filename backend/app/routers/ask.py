"""STUB — build after /api/refine (both are "milestone 2" — refine first, ask second, since
ask's grounded-follow-up prompt design builds on refine's constrained-reasoning prompt).

Spec (from docs/design-doc-v2.md Section 9.2 + PRD user story "AI product builder"):
  POST /api/ask
  Body: { analysis_id: uuid, question: str, anthropic_api_key: str }
  - Scoped STRICTLY to the given analysis_id (DDD 4.3 invariant) — the system prompt must be
    restricted to reasoning about the existing recommendation, never re-deriving a new one.
    Enforce this structurally: every DB query in this handler filters by analysis_id, not
    just via prompt wording (a prompt-only restriction is not a real boundary).
  - Persist both the user's question and the assistant's answer as ConversationMessage rows
    (role="user" / role="assistant") so a follow-up conversation has real history, not just
    a single Q&A round-trip.
  - Same API-key handling as /api/refine — request-scoped, never stored server-side.
"""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["ask"])


@router.post("/ask")
def ask():
    raise HTTPException(
        status_code=501,
        detail="Not implemented yet — see backend/app/routers/ask.py docstring and "
        "docs/design-doc-v2.md Section 9.2 for the full spec.",
    )
