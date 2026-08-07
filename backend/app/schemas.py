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
