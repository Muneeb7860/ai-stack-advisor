import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AnalysisCreate(BaseModel):
    """What the v1 frontend sends: its own already-computed rule-engine output. The backend
    does not re-run detectSignals()/pickX() — v1 stays the source of truth for the recommendation
    logic (DDD Section 1); the backend's job here is persistence only."""

    requirement_text: str = Field(..., min_length=1)
    signals: dict
    recommendations: dict


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requirement_text: str
    signals: dict
    recommendations: dict
    share_slug: str | None
    created_at: datetime
    updated_at: datetime


class ShareLinkOut(BaseModel):
    share_slug: str
    share_path: str  # relative path — frontend prefixes with its own origin


class RefineRequest(BaseModel):
    """POST /api/refine body. Matches the spec in routers/refine.py's docstring, plus one
    addition (analysis_id, optional) — see that docstring for why: RefinementResult requires
    a non-null analysis_id, but the original spec's body doesn't include one, so this endpoint
    creates a new Analysis when the caller omits it (same as POST /api/analyses) rather than
    silently failing or inventing an untracked orphan RefinementResult."""

    requirement_text: str = Field(..., min_length=1, max_length=10_000)
    recommendations: dict
    anthropic_api_key: str = Field(..., min_length=1)
    analysis_id: uuid.UUID | None = None


class AdjustedPick(BaseModel):
    category: str
    pick: str
    reason: str = Field(..., description="Must cite something specific in requirement_text.")
    changed_from_tier1: bool = True


class UsageInfo(BaseModel):
    """Real token counts straight from the Anthropic response (message.usage) — not an
    estimate. Not persisted to any table (RefinementResult/ConversationMessage have no usage
    column); this is response-only, computed fresh from whatever the SDK returned for that one
    call. Added so the frontend can show real cost next to the existing directional cost
    estimate in the Cost section, instead of only ever guessing."""

    input_tokens: int
    output_tokens: int


class RefineResponse(BaseModel):
    """Returns adjusted picks AND the untouched original recommendations side by side
    (design-doc-v2.md Section 3.2 "Reasoning API") so the frontend can render 'AI suggested
    changing X because Y' without losing the original rule-engine reasoning."""

    analysis_id: uuid.UUID
    original_recommendations: dict
    adjusted_picks: list[AdjustedPick]
    rationale: str
    open_questions: list[str]
    llm_model_used: str
    usage: UsageInfo


class AskRequest(BaseModel):
    """POST /api/ask body, per routers/ask.py's docstring."""

    analysis_id: uuid.UUID
    question: str = Field(..., min_length=1, max_length=4_000)
    anthropic_api_key: str = Field(..., min_length=1)


class ConversationMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    content: str
    created_at: datetime


class AskResponse(BaseModel):
    analysis_id: uuid.UUID
    answer: str
    llm_model_used: str
    conversation: list[ConversationMessageOut]
    usage: UsageInfo
