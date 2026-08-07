"""SQLAlchemy models — deliberately a 1:1 match with docs/AI-Stack-Advisor-DDD.docx (Section 4,
Aggregates & Entities) and diagrams/erd.html. If you need to change a field, change the ERD/DDD
first and keep this file in sync — don't let them drift, that was an explicit audit finding
against the *previous* set of docs (they'd drifted from the shipped app once already).

Aggregate boundaries (DDD Section 4, repeated here because it matters for how you extend this):
- Analysis is the aggregate root. RefinementResult, ConversationMessage, and McpInvocation
  reference it by analysis_id but are NOT children Analysis owns internally — don't add
  back-references or cascade deletes that couple them tighter than the DDD intends.
"""
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Analysis(Base):
    """Aggregate root. Created the moment a v1 client-side result is first sent to the backend
    (for refinement or sharing) — v1 alone, with no backend call, never creates a row here.
    """

    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    signals: Mapped[dict] = mapped_column(JSONB, nullable=False)
    recommendations: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Nullable = "never shared", not "not yet shared" — sharing is opt-in per analysis.
    # NOTE (ERD "Deliberately Excluded"): there is no revoke/un-share mechanism yet — that
    # was never a stated v2 requirement. If you add one, it's a real schema change, not a
    # UI-only feature — flag it back against the PRD before building it silently.
    share_slug: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RefinementResult(Base):
    """Append-only by design (DDD 4.2) — a new refinement pass never overwrites a prior one.
    NOT YET WIRED TO AN ENDPOINT. This table exists so share-link persistence (built first)
    doesn't need a schema migration later when /api/refine (built second) lands.
    """

    __tablename__ = "refinement_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.id"), nullable=False, index=True)
    adjusted_picks: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    open_questions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    llm_model_used: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConversationMessage(Base):
    """Scoped to exactly one Analysis, never shared across analyses (DDD 4.3) — /api/ask must
    enforce this structurally (filter every query by analysis_id), not just via prompt wording.
    NOT YET WIRED TO AN ENDPOINT.
    """

    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class McpInvocation(Base):
    """analysis_id is nullable on purpose (DDD 4.4) — an MCP-originated call is logged the
    instant the tool is called, before Analysis Context has necessarily produced a row yet.
    NOT YET WIRED TO AN ENDPOINT.
    """

    __tablename__ = "mcp_invocations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analyses.id"), nullable=True, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(120), nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    client_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    invoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
