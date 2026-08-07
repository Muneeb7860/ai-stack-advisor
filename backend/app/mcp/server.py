"""STUB — build order milestone 3 (see backend/KICKOFF_BRIEF.md).

Spec (from docs/AI-Stack-Advisor-DDD.docx Section 3.4 "Integration Context" + PRD FR-29):
  A single MCP tool: recommend_stack(requirement_text: str) -> full recommendation object.

  Conformist relationship to the Analysis Context (DDD 3.4) — this wraps the EXISTING v1
  rule-engine logic, it does not reimplement it and does not ask Analysis Context to change
  anything for its benefit. Concretely: the v1 rule engine is JavaScript embedded in
  index.html. Before building this, decide (and document the decision as an ADR):
    (a) port detectSignals()/pickX() to Python so this server can call it directly, or
    (b) shell out to Node to run the existing JS unmodified, or
    (c) run a small internal HTTP call to a deployed copy of the frontend's logic.
  (a) is very likely the right call — it's the only option that doesn't create a second
  network hop or a language-bridging dependency for a "thinnest layer, not a source of
  business rules" component (DDD 3.4). If you port to Python, port it faithfully: the
  recursive audit already found and fixed several signal-detection bugs in the JS version
  (see the chat history / commit log around index.html) — don't reintroduce them in a Python
  rewrite by re-deriving the logic from first principles instead of transliterating it.

  McpInvocation logging: log the call the INSTANT recommend_stack() is invoked, before
  Analysis Context has necessarily produced a persisted Analysis row — analysis_id on the
  McpInvocation row is nullable specifically for this reason (DDD 4.4). Don't make logging
  conditional on the call succeeding.

  Use the official MCP Python SDK (`mcp` package) for the actual protocol wiring — this file
  is a placeholder, not a working server.
"""

raise NotImplementedError(
    "MCP server not built yet — see this file's module docstring and "
    "docs/AI-Stack-Advisor-DDD.docx Section 3.4 for the full spec."
)
