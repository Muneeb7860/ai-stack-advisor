"""New vendor category: LLM Observability (Langfuse / Braintrust).

Genuinely missing before this PR: general infra observability (Datadog/Grafana, the existing
OBSERVABILITY_VENDORS category) was covered, but nothing traced or evaluated LLM calls
specifically — no coverage anywhere for prompt tracing, eval, or LLM-specific observability.
Same shape as Agent Framework (PR #45): NOT a "stack" card, a bespoke AI-layer section (same
family as RAG/Vector DB/Guardrails/MCP Servers/Agent Framework), so it deliberately does NOT get
STACK_CARD_CATEGORY/VALID_CATEGORIES wiring — those sections don't render Refine/Ask/Challenge
buttons at all (attachRefineUI() only targets `#stack .stack-card` and `#tradeoffs .tradeoff-card`).

Gated on `minimalProject` (not `agentic` like Agent Framework) — unlike an agent-orchestration
framework, LLM tracing/eval is relevant to any real LLM usage, not just agentic workflows; a
learning/portfolio project is the one case where dedicated tracing genuinely isn't worth it yet,
mirroring this file's existing minimalProject gating used elsewhere.

Facts (Langfuse's open-source/self-hostable posture and Jan-2026 ClickHouse acquisition;
Braintrust's CI/CD-gated eval workflow and free-tier shape; both platforms' pricing) verified
live via web search against langfuse.com/pricing, braintrust.dev/articles/langfuse-vs-braintrust,
and clickhouse.com/blog (the acquisition announcement) before being written into either engine.

Asserted against BOTH engines (rule_engine.py and index.html's JS twin).
"""
import shutil
from pathlib import Path

import pytest

from app.rule_engine import LLM_OBSERVABILITY_VENDORS, detect_signals, recommend_stack
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


REAL_TEXT = "A SaaS product with an AI chatbot answering customer questions using an LLM."
MINIMAL_TEXT = "A college capstone project — a simple chatbot for a class assignment."
ENTERPRISE_TEXT = "A large enterprise platform with an AI assistant, many engineers on the team."
NO_LLM_TEXT = "A simple e-commerce website with a product catalog, shopping cart and Stripe checkout."


# ------------------------------------------------------------------------- explicit mentions

def test_langfuse_mention_is_detected_and_recommended():
    s = detect_signals("We already use Langfuse. " + REAL_TEXT)
    assert s["langfuseMentioned"] is True
    rec = recommend_stack("We already use Langfuse. " + REAL_TEXT)["recommendations"]
    assert rec["llm_observability_vendor"]["v"] == "Langfuse"


def test_braintrust_mention_is_detected_and_recommended():
    s = detect_signals("We already use Braintrust. " + REAL_TEXT)
    assert s["braintrustMentioned"] is True
    rec = recommend_stack("We already use Braintrust. " + REAL_TEXT)["recommendations"]
    assert rec["llm_observability_vendor"]["v"] == "Braintrust"


# ------------------------------------------------------------------------ gating on LLM usage

def test_requirement_with_no_llm_signals_gets_not_applicable():
    """Found in post-merge review of PR #51 — the bug this test locks out: the pick originally
    gated ONLY on minimalProject, so a plain CRUD app with zero AI signals was told to adopt
    Langfuse to trace LLM calls it never makes, while the Cost section of the very same report
    said "No significant LLM/chatbot/RAG/voice signal detected." Uses the same usesLLM definition
    the cost estimate uses (now the shared llm_usage_detected helper), not a second copy."""
    s = detect_signals(NO_LLM_TEXT)
    assert not (s["chatbot"] or s["agentic"] or s["knowledgeBase"] or s["voice"])
    rec = recommend_stack(NO_LLM_TEXT)["recommendations"]
    assert rec["llm_observability_vendor"]["v"] == "Not applicable — no LLM/AI feature detected in this stack"
    assert rec["llm_observability_vendor"]["primaryId"] is None


def test_no_llm_gate_is_checked_before_the_minimal_project_gate():
    """Ordering matters for the message the user actually reads: a learning project that also has
    no AI feature should be told the more fundamental thing (no LLM to trace), not the narrower
    "you're just a learning project" reason."""
    rec = recommend_stack("A college capstone project — a static personal portfolio website.")["recommendations"]
    assert rec["llm_observability_vendor"]["v"] == "Not applicable — no LLM/AI feature detected in this stack"


def test_llm_usage_detected_helper_is_shared_with_the_cost_estimate():
    """Regression lock for the root cause: the condition existed twice (cost estimate + this
    pick) and the second copy omitted it entirely. One helper, both consumers."""
    from app.rule_engine import llm_usage_detected
    assert llm_usage_detected(detect_signals(REAL_TEXT)) is True
    assert llm_usage_detected(detect_signals(NO_LLM_TEXT)) is False
    # The cost estimate must report the same answer for the same input, from the same helper.
    rec = recommend_stack(NO_LLM_TEXT)["recommendations"]
    assert rec["cost_estimate"]["usesLLM"] is False


# ------------------------------------------------------------------- gating on minimalProject

def test_minimal_project_gets_not_applicable():
    rec = recommend_stack(MINIMAL_TEXT)["recommendations"]
    assert rec["llm_observability_vendor"]["v"] == "Not applicable — a learning/portfolio project doesn't need dedicated LLM tracing yet"
    assert rec["llm_observability_vendor"]["primaryId"] is None


def test_real_requirement_gets_langfuse_by_default():
    rec = recommend_stack(REAL_TEXT)["recommendations"]
    assert rec["llm_observability_vendor"]["v"] == "Langfuse"
    assert rec["llm_observability_vendor"]["primaryId"] == "langfuse"


def test_enterprise_requirement_defaults_to_braintrust():
    rec = recommend_stack(ENTERPRISE_TEXT)["recommendations"]
    assert rec["llm_observability_vendor"]["v"] == "Braintrust"
    assert rec["llm_observability_vendor"]["primaryId"] == "braintrust"


# ------------------------------------------------------------------------- vendor catalog data

def test_both_vendors_are_in_the_catalog():
    ids = {v["id"] for v in LLM_OBSERVABILITY_VENDORS}
    assert ids == {"langfuse", "braintrust"}


def test_llm_observability_vendor_catalog_has_no_duplicate_ids():
    ids = [v["id"] for v in LLM_OBSERVABILITY_VENDORS]
    assert len(ids) == len(set(ids))


def test_langfuse_pricing_discloses_it_is_genuinely_free_and_self_hostable():
    langfuse = next(v for v in LLM_OBSERVABILITY_VENDORS if v["id"] == "langfuse")
    assert "Free (OSS, self-hosted)" in langfuse["pricing"]


def test_braintrust_pricing_discloses_it_has_no_self_hosted_option():
    braintrust = next(v for v in LLM_OBSERVABILITY_VENDORS if v["id"] == "braintrust")
    assert "no self-hosted OSS option" in braintrust["drawback"]


# ---------------------------------------------------------- NOT wired into refine (by design)

def test_llm_observability_is_not_a_stack_card_category():
    """Regression guard for the same design decision Agent Framework locked in: this category
    has no STACK_CARD_CATEGORY/VALID_CATEGORIES entry, matching the existing vectordb/
    guardrails/mcpservers/agentframework precedent (bespoke AI-layer sections don't get
    Refine/Ask/Challenge)."""
    from app.routers.refine import VALID_CATEGORIES
    assert "llmobservability" not in VALID_CATEGORIES
    assert "llm_observability" not in VALID_CATEGORIES


# ------------------------------------------------------------------------------------ JS parity

@requires_node
def test_js_langfuse_mention_is_detected_and_recommended():
    text = "We already use Langfuse. " + REAL_TEXT
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({text!r}));
      console.log(JSON.stringify({{ v: rec.llmObservabilityVendorPick.v }}));
    """)
    assert out["v"] == "Langfuse"


@requires_node
def test_js_minimal_project_gets_not_applicable():
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({MINIMAL_TEXT!r}));
      console.log(JSON.stringify({{ v: rec.llmObservabilityVendorPick.v }}));
    """)
    assert out["v"] == "Not applicable — a learning/portfolio project doesn't need dedicated LLM tracing yet"


@requires_node
def test_js_enterprise_defaults_to_braintrust():
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({ENTERPRISE_TEXT!r}));
      console.log(JSON.stringify({{ v: rec.llmObservabilityVendorPick.v }}));
    """)
    assert out["v"] == "Braintrust"


@requires_node
def test_js_and_python_llm_observability_vendor_ids_match():
    py_ids = sorted(v["id"] for v in LLM_OBSERVABILITY_VENDORS)
    js_ids = sorted(_js("console.log(JSON.stringify(LLM_OBSERVABILITY_VENDORS.map(v => v.id)));"))
    assert py_ids == js_ids


@requires_node
def test_js_requirement_with_no_llm_signals_gets_not_applicable():
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({NO_LLM_TEXT!r}));
      console.log(JSON.stringify({{ v: rec.llmObservabilityVendorPick.v, primaryId: rec.llmObservabilityVendorPick.primaryId }}));
    """)
    assert out["v"] == "Not applicable — no LLM/AI feature detected in this stack"
    assert out["primaryId"] is None


@requires_node
def test_js_alt_toggle_is_suppressed_whenever_the_pick_is_not_applicable():
    """The render gate derives from the pick's own primaryId rather than duplicating its internal
    condition — otherwise a no-LLM report would show "Not applicable" as the headline and still
    render the full Langfuse-vs-Braintrust comparison directly underneath it."""
    text = INDEX_HTML.read_text(encoding="utf-8")
    start = text.index("sec('llmobservability'")
    section = text[start:start + 900]
    assert "llmObservabilityVendorPick.primaryId ? altToggle(" in section
    assert "!s.minimalProject ? altToggle" not in section


@requires_node
def test_js_and_python_vendor_cat_fields_match_exactly():
    """Locks the HTML-entity divergence found in review: index.html used `&amp;` in two cat
    fields while the Python twin used a raw `&`, diverging from each other and from this file's
    own convention for vendor-catalog prose."""
    py = {v["id"]: v["cat"] for v in LLM_OBSERVABILITY_VENDORS}
    js = _js("console.log(JSON.stringify(LLM_OBSERVABILITY_VENDORS.map(v => [v.id, v.cat])));")
    assert {k: v for k, v in js} == py


@requires_node
def test_js_llmobservability_section_id_is_registered():
    out = _js("console.log(JSON.stringify(ALL_SECTION_IDS.includes('llmobservability')));")
    assert out is True
