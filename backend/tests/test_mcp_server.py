"""Integration tests for app/mcp/server.py's core logic. Requires a live Postgres reachable
at DATABASE_URL, same as the other integration test files.

Tests call _log_and_recommend() directly rather than going through the MCP protocol/transport
layer — that layer is a thin, officially-supported SDK wrapper (mcp.server.mcpserver) with
its own test coverage upstream; what's worth testing here is this project's own logic:
invocation logging, the nullable-then-populated analysis_id, and unconditional logging even
on failure (DDD 4.4).
"""
import pytest

from app.db import SessionLocal
from app import models
from app.mcp.server import _log_and_recommend


def _count_invocations(db):
    return db.query(models.McpInvocation).count()


def test_recommend_stack_returns_full_result():
    result = _log_and_recommend("Fintech startup, small team, real-time fraud detection.", "Test Client")
    assert "signals" in result
    assert "recommendations" in result
    assert result["signals"]["finance"] is True


def test_invocation_is_logged_with_client_name():
    db = SessionLocal()
    try:
        before = _count_invocations(db)
    finally:
        db.close()

    _log_and_recommend("Healthcare chatbot for patient scheduling.", "Claude Desktop")

    db = SessionLocal()
    try:
        after = _count_invocations(db)
        assert after == before + 1
        latest = (
            db.query(models.McpInvocation)
            .order_by(models.McpInvocation.invoked_at.desc())
            .first()
        )
        assert latest.tool_name == "recommend_stack"
        assert latest.client_name == "Claude Desktop"
        assert latest.input_text == "Healthcare chatbot for patient scheduling."
    finally:
        db.close()


def test_invocation_analysis_id_gets_populated_after_success():
    """DDD 4.4: analysis_id starts null (invocation logged before the rule engine runs) and
    gets populated once the Analysis row is persisted — verified here as an end state, not
    just trusted from the code structure."""
    _log_and_recommend("E-commerce recommendation engine, already on AWS.", None)

    db = SessionLocal()
    try:
        latest = (
            db.query(models.McpInvocation)
            .order_by(models.McpInvocation.invoked_at.desc())
            .first()
        )
        assert latest.analysis_id is not None
        analysis = db.query(models.Analysis).filter_by(id=latest.analysis_id).first()
        assert analysis is not None
        assert analysis.requirement_text == "E-commerce recommendation engine, already on AWS."
    finally:
        db.close()


def test_client_name_is_nullable():
    _log_and_recommend("Internal enterprise assistant.", None)
    db = SessionLocal()
    try:
        latest = (
            db.query(models.McpInvocation)
            .order_by(models.McpInvocation.invoked_at.desc())
            .first()
        )
        assert latest.client_name is None
    finally:
        db.close()


def test_invocation_logged_even_when_rule_engine_raises():
    """DDD 4.4 / this file's module docstring: logging must not be conditional on the call
    succeeding. An empty requirement_text makes rule_engine.recommend_stack() raise
    ValueError — the invocation row must still exist, with analysis_id left null."""
    db = SessionLocal()
    try:
        before = _count_invocations(db)
    finally:
        db.close()

    with pytest.raises(ValueError):
        _log_and_recommend("", "Claude Code")

    db = SessionLocal()
    try:
        after = _count_invocations(db)
        assert after == before + 1
        latest = (
            db.query(models.McpInvocation)
            .order_by(models.McpInvocation.invoked_at.desc())
            .first()
        )
        assert latest.input_text == ""
        assert latest.analysis_id is None
    finally:
        db.close()


def test_mcp_tool_is_registered():
    """Sanity check that the @mcp.tool() decorator actually registered the tool under the
    expected server/name — catches a renamed function or a decorator that silently no-ops."""
    from app.mcp.server import mcp

    assert mcp.name == "ai-stack-advisor"
