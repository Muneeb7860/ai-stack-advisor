"""New vendor category: Agent Framework (LangGraph / Pydantic AI / FastMCP).

Second genuinely-new category this session, after GitOps CD (PR #44). Unlike GitOps, this one
is NOT a "stack" card — it's a bespoke AI-layer section (same shape as RAG/Vector DB/Guardrails/
MCP Servers), so it does NOT need STACK_CARD_CATEGORY/VALID_CATEGORIES wiring: those sections
don't get Refine/Ask/Challenge buttons at all (attachRefineUI() only targets
`#stack .stack-card` and `#tradeoffs .tradeoff-card`).

Architectural note this test suite locks in: LangGraph and Pydantic AI genuinely compete (both
orchestrate an agent's own reasoning/tool-use loop); FastMCP solves a different job entirely
(exposing tools via the MCP protocol so an agent built with either — or neither — can call them).
All three are grouped in one category anyway (same pattern as GATEWAY_VENDORS mixing open-
source/commercial, or CACHE_VENDORS mixing single/multi-threaded stores), with the `cat` field
and FastMCP's own drawback text saying so explicitly. The category is gated on the `agentic`
signal — a non-agentic requirement has no agent loop for any of these to structure.

Facts (FastMCP's high-level API being incorporated into the official MCP Python SDK in 2024;
LangGraph/Pydantic AI's respective feature sets) verified live against docs.langchain.com,
pydantic.dev, and gofastmcp.com before being written into either engine.

Asserted against BOTH engines (rule_engine.py and index.html's JS twin).
"""
import shutil
from pathlib import Path

import pytest

from app.rule_engine import AGENT_FRAMEWORK_VENDORS, detect_signals, recommend_stack
from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)


def _main_script() -> str:
    return INDEX_HTML.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]


_STUBS = r"""
const dummyEl = { style:{}, classList:{add(){},remove(){},toggle(){}}, addEventListener(){},
  setAttribute(){}, getAttribute:()=>null, appendChild(){}, removeChild(){}, click(){}, focus(){},
  querySelector:()=>null, querySelectorAll:()=>[], innerHTML:'', textContent:'', value:'' };
global.window = { location:{search:''}, addEventListener(){}, matchMedia:()=>({matches:false,addEventListener(){}}) };
global.document = { documentElement:dummyEl, body:dummyEl, querySelector:()=>dummyEl,
  querySelectorAll:()=>[], getElementById:()=>dummyEl, createElement:()=>dummyEl, addEventListener(){} };
global.navigator = { clipboard:{} };
global.localStorage = { getItem:()=>null, setItem(){}, removeItem(){} };
global.fetch = () => Promise.resolve({ ok:false });
global.URL = { createObjectURL:()=>'', revokeObjectURL(){} };
"""


def _js(expr_body: str):
    return run_node_json(_STUBS + _main_script() + "\n" + expr_body)


AGENTIC_TEXT = "We need an agentic system that takes autonomous actions across multiple tools."
NON_AGENTIC_TEXT = "A simple marketing website with a contact form."
ENTERPRISE_AGENTIC_TEXT = "A large enterprise platform with an agentic workflow taking autonomous actions."


# ------------------------------------------------------------------------- explicit mentions

def test_langgraph_mention_is_detected_and_recommended():
    s = detect_signals("We already use LangGraph. " + AGENTIC_TEXT)
    assert s["langgraphMentioned"] is True
    rec = recommend_stack("We already use LangGraph. " + AGENTIC_TEXT)["recommendations"]
    assert rec["agent_framework_vendor"]["v"] == "LangGraph"


def test_pydantic_ai_mention_is_detected_and_recommended():
    s = detect_signals("We already use Pydantic AI. " + AGENTIC_TEXT)
    assert s["pydanticAiMentioned"] is True
    rec = recommend_stack("We already use Pydantic AI. " + AGENTIC_TEXT)["recommendations"]
    assert rec["agent_framework_vendor"]["v"] == "Pydantic AI"


def test_fastmcp_mention_is_detected_and_recommended():
    s = detect_signals("We already use FastMCP. " + AGENTIC_TEXT)
    assert s["fastmcpMentioned"] is True
    rec = recommend_stack("We already use FastMCP. " + AGENTIC_TEXT)["recommendations"]
    assert rec["agent_framework_vendor"]["v"] == "FastMCP"


def test_fastmcp_pick_discloses_it_is_not_an_agent_orchestration_framework():
    rec = recommend_stack("We already use FastMCP. " + AGENTIC_TEXT)["recommendations"]
    assert "doesn't orchestrate the agent's own reasoning loop" in rec["agent_framework_vendor"]["why"]


# --------------------------------------------------------------------- gating on agentic signal

def test_non_agentic_requirement_gets_not_applicable():
    rec = recommend_stack(NON_AGENTIC_TEXT)["recommendations"]
    assert rec["agent_framework_vendor"]["v"] == "Not applicable — no agentic/multi-step tool-use workflow in this stack"
    assert rec["agent_framework_vendor"]["primaryId"] is None


def test_agentic_requirement_gets_a_real_recommendation():
    rec = recommend_stack(AGENTIC_TEXT)["recommendations"]
    assert rec["agent_framework_vendor"]["v"] == "Pydantic AI"
    assert rec["agent_framework_vendor"]["primaryId"] == "pydanticai"


def test_enterprise_agentic_requirement_defaults_to_langgraph():
    rec = recommend_stack(ENTERPRISE_AGENTIC_TEXT)["recommendations"]
    assert "LangGraph" in rec["agent_framework_vendor"]["v"]
    assert rec["agent_framework_vendor"]["primaryId"] == "langgraph"


def test_fastmcp_note_appears_when_mcp_is_also_relevant():
    """Enterprise scale should also fire pick_mcp's own enterprise branch — the two are
    independently gated (agentic vs enterprise), so an enterprise+agentic requirement should
    surface the complementary FastMCP note alongside the primary LangGraph pick."""
    rec = recommend_stack(ENTERPRISE_AGENTIC_TEXT)["recommendations"]
    assert "FastMCP" in rec["agent_framework_vendor"]["v"]


# ------------------------------------------------------------------------- vendor catalog data

def test_all_three_vendors_are_in_the_catalog_with_correct_categorization():
    ids = {v["id"] for v in AGENT_FRAMEWORK_VENDORS}
    assert ids == {"langgraph", "pydanticai", "fastmcp"}

    fastmcp = next(v for v in AGENT_FRAMEWORK_VENDORS if v["id"] == "fastmcp")
    # The category label itself must disclose FastMCP isn't a competing orchestration framework —
    # a reader skimming just the `cat` column must not be misled.
    assert "not an agent-orchestration framework" in fastmcp["cat"]


def test_agent_framework_vendor_catalog_has_no_duplicate_ids():
    ids = [v["id"] for v in AGENT_FRAMEWORK_VENDORS]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------- NOT wired into refine (by design)

def test_agent_framework_is_not_a_stack_card_category():
    """Regression guard for a specific design decision: unlike gitops (a real stack card), this
    category has no STACK_CARD_CATEGORY/VALID_CATEGORIES entry, matching the existing vectordb/
    guardrails/mcpservers precedent (bespoke AI-layer sections don't get Refine/Ask/Challenge)."""
    from app.routers.refine import VALID_CATEGORIES
    assert "agentframework" not in VALID_CATEGORIES
    assert "agent_framework" not in VALID_CATEGORIES


# ------------------------------------------------------------------------------------ JS parity

@requires_node
def test_js_langgraph_mention_is_detected_and_recommended():
    text = "We already use LangGraph. " + AGENTIC_TEXT
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({text!r}));
      console.log(JSON.stringify({{ v: rec.agentFrameworkVendorPick.v }}));
    """)
    assert out["v"] == "LangGraph"


@requires_node
def test_js_non_agentic_requirement_gets_not_applicable():
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({NON_AGENTIC_TEXT!r}));
      console.log(JSON.stringify({{ v: rec.agentFrameworkVendorPick.v }}));
    """)
    assert out["v"] == "Not applicable — no agentic/multi-step tool-use workflow in this stack"


@requires_node
def test_js_enterprise_agentic_defaults_to_langgraph_with_fastmcp_note():
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({ENTERPRISE_AGENTIC_TEXT!r}));
      console.log(JSON.stringify({{ v: rec.agentFrameworkVendorPick.v }}));
    """)
    assert "LangGraph" in out["v"]
    assert "FastMCP" in out["v"]


@requires_node
def test_js_and_python_agent_framework_vendor_ids_match():
    py_ids = sorted(v["id"] for v in AGENT_FRAMEWORK_VENDORS)
    js_ids = sorted(_js("console.log(JSON.stringify(AGENT_FRAMEWORK_VENDORS.map(v => v.id)));"))
    assert py_ids == js_ids


@requires_node
def test_js_agentframework_section_id_is_registered():
    out = _js("console.log(JSON.stringify(ALL_SECTION_IDS.includes('agentframework')));")
    assert out is True
