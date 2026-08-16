"""MCP tool wrapper — v2 milestone 4 (see backend/KICKOFF_BRIEF.md,
docs/AI-Stack-Advisor-DDD.docx Section 3.4 "Integration Context", and PRD FR-29).

Port decision (was an open question in this file's original stub — now decided and recorded
as docs/adr/0001-mcp-rule-engine-port.md): detectSignals()/pickX() are ported to Python in
app/rule_engine.py, option (a) from the original docstring, not shelled out to Node or proxied
over HTTP. That port was verified byte-for-byte against index.html's actual JavaScript across
13 scenarios — the 5 built-in examples plus 8 covering every bug validation-report.md found
and fixed (negation handling, on-prem override, warehouse detection, team-size conflicts,
the small-team regex fallback) — with zero diffs, before this file was written. See the ADR
for the verification method; see app/rule_engine.py's own docstring for the port-discipline
rule going forward (transliterate index.html's current source, don't re-derive from the
PRD/BRD's description of what it "should" do).

This module is a thin wrapper — a Conformist relationship to the Analysis Context (DDD 3.4):
it adapts the MCP protocol onto rule_engine.recommend_stack() without changing that function's
behavior or asking it to accommodate MCP-specific concerns.

McpInvocation logging (DDD 4.4): logged the INSTANT the tool is invoked, before the rule
engine has necessarily run to completion — analysis_id is nullable specifically for this
reason (see models.py) and gets populated after the fact once the Analysis row exists.
Logging happens unconditionally, even if the rule engine goes on to raise — see
_log_and_recommend()'s structure below (invocation is committed before the recommend_stack()
call, not after).

Running this server: `python -m app.mcp.server` (stdio transport) — add it to Claude
Desktop's/Code's MCP config pointing at this command. Needs the same DATABASE_URL as the
FastAPI app (same models/db module, same Postgres instance) — this is a SEPARATE PROCESS,
not mounted into the FastAPI app, matching design-doc-v2.md's C4 diagram (the MCP Server is
its own container/component, not a route on the API).
"""
import sys

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy import text

from .. import models
from ..config import settings
from ..db import SessionLocal, engine
from ..rule_engine import recommend_stack as _recommend_stack

mcp = FastMCP(
    "ai-stack-advisor",
    instructions=(
        "Recommends a full technology + AI architecture (cloud, database, LLM strategy, "
        "RAG, guardrails, cost/throughput, governance, and more) from a free-text business "
        "or product requirement. This is the same deterministic rule engine that powers the "
        "AI Stack Advisor web app (index.html) — not an LLM call, so it's instant and its "
        "reasoning is fully auditable back to specific keywords/phrases in the input."
    ),
)


def _log_and_recommend(requirement_text: str, client_name: str | None) -> dict:
    """Core logic, decoupled from the MCP protocol layer (mcp.tool()-decorated functions are
    awkward to unit test directly against a real DB) — see tests/test_mcp_server.py, which
    calls this directly rather than going through the MCP transport."""
    db = SessionLocal()
    try:
        # Logged before recommend_stack() runs, and committed immediately — see module
        # docstring. If recommend_stack() raises below, this row still exists with
        # analysis_id left null, which is exactly the DDD 4.4 invariant this structure exists
        # to satisfy: the invocation happened regardless of what happened next.
        invocation = models.McpInvocation(
            tool_name="recommend_stack",
            input_text=requirement_text,
            client_name=client_name,
            analysis_id=None,
        )
        db.add(invocation)
        db.commit()

        result = _recommend_stack(requirement_text)

        analysis = models.Analysis(
            requirement_text=requirement_text,
            signals=result["signals"],
            recommendations=result["recommendations"],
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        invocation.analysis_id = analysis.id
        db.commit()

        return result
    finally:
        db.close()


def _client_name_from_context(ctx: Context) -> str | None:
    """Isolated specifically so this can be unit-tested against a mock shaped like the real
    mcp.types.InitializeRequestParams pydantic model, without needing a live stdio session.
    Supports both clientInfo (camelCase) and client_info (snake_case) across SDK versions.
    """
    try:
        session = getattr(ctx, "session", None)
        if session is None:
            return None
        client_params = getattr(session, "client_params", None)
        if client_params is None:
            return None
        info = getattr(client_params, "clientInfo", None) or getattr(client_params, "client_info", None)
        if info is not None:
            return getattr(info, "name", None)
        return None
    except Exception:
        return None


@mcp.tool()
def recommend_stack(requirement_text: str, ctx: Context) -> dict:
    """Analyze a free-text business/product requirement and return a full architecture
    recommendation: detected signals plus picks (each with a plain-language rationale and a
    High/Medium/Low confidence rating) across cloud, database, LLM strategy, RAG, guardrails,
    cost/throughput optimization, and governance (KRA/KPI/SLA targets).

    Args:
        requirement_text: Plain-language description of the business or product requirement —
            the same free-text input the AI Stack Advisor web app takes. No required
            structured fields; more detail (industry, scale, compliance needs, team size,
            existing vendor commitments) produces more confident, specific recommendations.
    """
    client_name = _client_name_from_context(ctx)
    return _log_and_recommend(requirement_text, client_name)


def _validate_startup_config() -> None:
    """Fail fast at launch rather than on the first real tool call. Real finding from driving
    this server over actual stdio JSON-RPC (not just in-process unit tests): mcp's
    stdio_client does not inherit the parent process's full environment by default (only a
    small allowlist like PATH/HOME) — so a launcher config missing an explicit DATABASE_URL
    silently falls back to config.py's default rather than erroring. tools/list still succeeds
    either way (it doesn't touch the DB), which makes a broken config invisible right up until
    someone depends on it — exactly the "server that answers but can't actually do anything"
    failure mode. A real connectivity check here turns that into a one-line error at launch,
    before any client ever gets a chance to call recommend_stack() against a DB that isn't
    reachable. Checks connectivity, not just "is the env var non-empty" — the default value is
    itself a syntactically valid URL that simply doesn't resolve outside its intended
    environment, which is the actual failure mode this exists to catch."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — deliberately broad: any DB-unreachable cause
        # should produce the same clear, actionable exit, not a stack trace from whichever
        # specific driver exception happened to be raised.
        print(
            f"ai-stack-advisor MCP server: cannot reach the database at "
            f"DATABASE_URL={settings.database_url!r} ({exc.__class__.__name__}: {exc}). "
            f"If you're launching this via a client config (Claude Desktop/Code), make sure "
            f"its `env` block explicitly sets DATABASE_URL — stdio_client does not inherit "
            f"your shell's environment by default, so an unset DATABASE_URL silently falls "
            f"back to this module's default instead of erroring where you'd notice it.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    _validate_startup_config()
    mcp.run(transport="stdio")
