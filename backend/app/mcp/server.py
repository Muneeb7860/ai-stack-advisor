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
from mcp.server.mcpserver import Context, MCPServer

from .. import models
from ..db import SessionLocal
from ..rule_engine import recommend_stack as _recommend_stack

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
    client_name = None
    try:
        # Self-reported by the MCP client during its initialize handshake (e.g. "Claude
        # Desktop", "Claude Code") — DDD 4.4 documents this as nullable/best-effort, not a
        # verified identity, so absence here isn't an error condition. Deliberately broad
        # except: ctx.session raises ValueError (not AttributeError) outside a live request
        # context, and client_params/clientInfo can plausibly be None depending on the
        # client's handshake — a narrower catch here found exactly one of those the hard way
        # (ValueError slipping through an AttributeError-only catch during manual testing).
        # This metadata is nice-to-have; it must never be able to break the actual tool call.
        client_name = ctx.session.client_params.clientInfo.name  # type: ignore[union-attr]
    except Exception:
        pass
    return _log_and_recommend(requirement_text, client_name)


if __name__ == "__main__":
    mcp.run(transport="stdio")
