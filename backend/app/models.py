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

from sqlalchemy import Boolean, ForeignKey, Integer, Text, String, DateTime, func
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
    Wired to POST /api/refine (see app/routers/refine.py). Predates that endpoint on purpose:
    this table was added when share-link persistence (built first) shipped, so /api/refine
    (built second) wouldn't need a schema migration of its own when it landed.
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
    Wired to POST /api/ask (see app/routers/ask.py).
    """

    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Disagreement(Base):
    """Captures BRD Section 7's "disagreement rate" success metric — see
    docs/challenge-this-pick-spec.md for the full feature spec. Append-only, same rationale as
    RefinementResult above: a disagreement is a fact about a moment, editing it later would
    corrupt the rate calculation, not just the record. No update/delete route exists or should.
    Wired to POST /api/analyses/{analysis_id}/disagreements (see app/routers/disagreements.py).
    """

    __tablename__ = "disagreements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    current_pick: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_alternative: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class McpInvocation(Base):
    """analysis_id is nullable on purpose (DDD 4.4) — an MCP-originated call is logged the
    instant the tool is called, before Analysis Context has necessarily produced a row yet.
    Wired to the recommend_stack() MCP tool (see app/mcp/server.py's _log_and_recommend()).
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


class HarnessFeedback(Base):
    """Feedback on a completed Harness Readiness self-audit — see
    docs/harness-engineering/HARNESS_FEEDBACK_SCOPE.md.

    Standalone by design: NO foreign key to analyses, unlike Disagreement. A harness audit has no
    Analysis row and must not create one — an Analysis is a product requirement (input text +
    detected signals), which a self-audit of a team's own process definitionally is not. Forcing
    one into existence just to hang feedback off it would corrupt that table's meaning and every
    metric derived from it. Closest precedent for a standalone record is McpInvocation above,
    whose analysis_id is nullable for the same class of reason.

    Append-only, same rationale as Disagreement/RefinementResult: feedback is a fact about a
    moment. No update/delete route exists or should.

    `answers` carries the per-component scores because the comment is nearly useless without
    them — "this wasn't useful" from a team scoring 14/15 means something completely different
    than from a team scoring 2/15.
    """

    __tablename__ = "harness_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    band: Mapped[str] = mapped_column(String(64), nullable=False)
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Deliberately separate from `comment`: response rate on a one-click binary is far higher
    # than on free text, so this is the field that will actually have an n worth reading.
    helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
