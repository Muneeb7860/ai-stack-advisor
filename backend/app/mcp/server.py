"""Model Context Protocol (MCP) server for ai-stack-advisor.

Exposes recommend_stack as an MCP tool (decision #4 in KICKOFF_BRIEF.md — "reusable by
agents and developer tooling, not trapped behind a UI").

Decisions & architecture:
- Reuses the deterministic rule engine (app/rule_engine.py) directly — no second
  implementation of the recommendations, zero divergence between web app and MCP tool.
- Reuses the shared Analysis model/table: every MCP invocation persists an Analysis row
  (with the detected signals and recommendations JSON), identical to how the web app's
  guided-mode/freetext inputs persist analyses. A tool call via Claude Desktop or an agent
  framework is a first-class analysis, visible to /api/share and /api/refine just like a UI
  session.
- Protocol layer: built on Python's official mcp SDK. Provides cross-compatibility across
  both mcp>=2.0 (MCPServer) in the container environment and local FastMCP SDK variants.
- Tool input schema: mirrors the free-text input of index.html. A single `requirement_text`
  string is enough for the rule engine to detect 45+ architectural dimensions. We
  deliberately avoid forcing callers to pass 10 separate arguments (cloud preference, team
  size, etc.) — the tool's whole value proposition is that it infers those signals from
  natural-language prose, exactly like a human Solution Architect would. Callers CAN include
  specific constraints ("must use GCP", "team of 3") directly in the text.
- Tool return value: returns the full recommendation payload as structured JSON matching
  the API schema. The MCP client formats it for the user or downstream agent.
- Error handling: if the rule engine raises (e.g. empty input), the exception propagates as
  an MCP tool error with the message intact. We do NOT catch and return a fake success dict —
  MCP clients handle tool failures natively.
- Testing: tests/test_mcp_server.py tests the MCP server logic directly without needing a
  live stdio connection or a running Claude Desktop instance.

Zero divergence: this file imports recommend_stack from app.rule_engine — it does NOT
re-implement any recommendation logic. If a recommendation changes, it changes in
rule_engine.py and is immediately live in both the web app and the MCP server.

FastAPI decoupled: this server does NOT import or mount into app.main. It's a standalone
entry point (run with `python -m app.mcp.server`) designed for stdio transport. It shares
the database (app.db, app.models) and configuration (app.config) with the API, but has no
HTTP routes of its own. This keeps the MCP server lightweight and runnable in environments
where FastAPI is not needed (e.g., local CLI tools, Claude Desktop config).

Clean separation: app/rule_engine.py has no dependency on mcp. It remains a pure-Python
domain module. The MCP server is a thin adapter on top of it. This satisfies DDD layer
isolation — the domain (rule_engine) knows nothing about the delivery mechanism (MCP,
FastAPI, CLI). You can use rule_engine.py anywhere without pulling in MCP dependencies.

Single tool: we expose ONE tool (`recommend_stack`), not 10 fine-grained tools (`pick_cloud`,
`pick_database`, etc.). Why:
1. The 45+ architectural decisions are interdependent — pick_database depends on cloud,
   throughput, AND team size. Calling them independently loses the cross-cutting synthesis
   that makes the advisor valuable.
2. An agent calling this tool wants the full architecture in one turn, not 10 round-trips.
3. The web app generates all categories in a single pass; the MCP tool should match that
   behavior.
4. Callers that only care about one category can read that specific key from the returned
   JSON dict.

Client-name logging: extracts client metadata from the MCP handshake (e.g. "Claude Desktop",
"Cursor", "custom-agent") when available, for analytics on which tools/environments are
driving usage. Best-effort — if the client doesn't provide it, we log None without altering
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

try:
    from mcp.server.mcpserver import Context, MCPServer
    mcp = MCPServer(
        name="ai-stack-advisor",
        version="0.1.0",
        instructions=(
            "Recommends a full technology + AI architecture (cloud, database, LLM strategy, "
            "RAG, guardrails, cost/throughput, governance, and more) from a free-text business "
            "or product requirement. This is the same deterministic rule engine that powers the "
            "AI Stack Advisor web app (index.html) — not an LLM call, so it's instant and its "
            "reasoning is fully auditable back to specific keywords/phrases in the input."
        ),
    )
except ImportError:
    from mcp.server.fastmcp import Context, FastMCP  # type: ignore[no-redef]
    mcp = FastMCP(  # type: ignore[assignment]
        "ai-stack-advisor",
        instructions=(
            "Recommends a full technology + AI architecture (cloud, database, LLM strategy, "
            "RAG, guardrails, cost/throughput, governance, and more) from a free-text business "
            "or product requirement. This is the same deterministic rule engine that powers the "
            "AI Stack Advisor web app (index.html) — not an LLM call, so it's instant and its "
            "reasoning is fully auditable back to specific keywords/phrases in the input."
        ),
    )

from sqlalchemy import text

from .. import models
from ..config import settings
from ..db import SessionLocal, engine
from ..rule_engine import recommend_stack as _recommend_stack


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

    NOTE the attribute is client_info (snake_case), not clientInfo — this got it wrong once
    already: mcp.types.InitializeRequestParams uses Python attribute names in snake_case
    (client_info) and camelCase only as its JSON serialization alias (clientInfo). The
    original version of this function used .clientInfo, which silently returned None via the
    except-Exception below instead of erroring — confirmed broken by driving a REAL stdio
    JSON-RPC session end-to-end (initialize → tools/call) and checking the persisted
    McpInvocation.client_name in Postgres, not just calling this function in-process. Calling
    the underlying function directly, or even mcp.call_tool() without a live client, would
    never have caught this — there was no live client_params to read the wrong attribute name
    from either way. See tests/test_mcp_server.py::test_client_name_from_context_uses_correct_attribute_name
    for the regression test this bug earned.
    """
    try:
        return ctx.session.client_params.client_info.name  # type: ignore[union-attr]
    except Exception:
        try:
            return ctx.session.client_params.clientInfo.name  # type: ignore[union-attr]
        except Exception:
            # Deliberately broad: ctx.session raises ValueError (not AttributeError) outside a
            # live request context, and client_params/client_info can plausibly be None depending
            # on the client's handshake (DDD 4.4: this is nullable/best-effort, not a verified
            # identity). This metadata must never be able to break the actual tool call — but a
            # broad catch is also exactly why the .clientInfo typo went unnoticed until end-to-end
            # testing, so it stays paired with a real regression test, not just "trust the catch."
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
