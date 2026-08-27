"""
JS <-> Python rule-engine parity gate.

index.html and app/rule_engine.py are two independent implementations of the same rule
engine (v1 must stay fully client-side per PRD NFR-1/NFR-5, so neither can import the
other — see rule_engine.py's module docstring). Nothing structurally stopped a new
category function from landing in one language and not the other: that is exactly what
happened with pickHybridConnectivity/pickIntegrationGuidance, which shipped in index.html
while /api/refine, /api/ask and the recommend_stack MCP tool silently returned two fewer
categories than the browser did for the same input, with a fully green suite.

This test is that missing gate. It compares the SET of category functions in both engines,
so adding pickFooBar() to index.html without pick_foo_bar() in rule_engine.py (or the
reverse) fails CI immediately, and also asserts every Python pick function is actually
reachable from recommend_stack()'s output rather than merely defined.
"""
import re
from pathlib import Path

from app import rule_engine

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
RULE_ENGINE_PY = Path(rule_engine.__file__)


def _normalize(name: str) -> str:
    """pickCICDVendor -> 'cicdvendor', pick_cicd_vendor -> 'cicdvendor'.

    Case- and separator-insensitive on purpose: the two engines use different conventions
    for acronyms (pickMCPvsAPI vs pick_mcp_vs_api, pickVectorDBPlacement vs
    pick_vector_db_placement), and any camelCase->snake_case converter has to special-case
    those. Collapsing both sides to letters-only sidesteps that entirely.
    """
    return name.replace("pick", "", 1).replace("_", "").lower()


def _js_pick_functions() -> set[str]:
    source = INDEX_HTML.read_text(encoding="utf-8")
    return {_normalize(m.group(1)) for m in re.finditer(r"function\s+(pick[A-Za-z0-9_]+)\s*\(", source)}


def _py_pick_functions() -> set[str]:
    source = RULE_ENGINE_PY.read_text(encoding="utf-8")
    return {_normalize(m.group(1)) for m in re.finditer(r"^def\s+(pick_[a-z0-9_]+)\s*\(", source, re.M)}


def test_index_html_is_readable():
    assert INDEX_HTML.exists(), f"index.html not found at {INDEX_HTML}"
    assert _js_pick_functions(), "no pickX() functions found in index.html — extraction regex is broken"


def test_no_category_function_exists_in_only_one_engine():
    js = _js_pick_functions()
    py = _py_pick_functions()

    js_only = sorted(js - py)
    py_only = sorted(py - js)

    assert not js_only, (
        f"{len(js_only)} category function(s) exist in index.html but not in rule_engine.py: {js_only}. "
        "The browser returns categories the backend (/api/refine, /api/ask, recommend_stack MCP tool) "
        "does not. Port them, following rule_engine.py's PORT DISCIPLINE docstring."
    )
    assert not py_only, (
        f"{len(py_only)} category function(s) exist in rule_engine.py but not in index.html: {py_only}. "
        "The backend returns categories the zero-backend v1 product does not."
    )


def test_every_python_pick_function_is_wired_into_recommend_stack():
    """A ported function nobody calls is the same silent gap as a missing one."""
    source = RULE_ENGINE_PY.read_text(encoding="utf-8")
    body = source[source.index("def recommend_stack("):]
    called = {_normalize(m.group(1)) for m in re.finditer(r"\b(pick_[a-z0-9_]+)\s*\(", body)}

    unreachable = sorted(_py_pick_functions() - called)
    assert not unreachable, (
        f"defined but never called from recommend_stack(): {unreachable} — "
        "these never reach an API or MCP response."
    )


def test_ported_categories_appear_in_recommend_stack_output():
    """Regression lock for the two categories this gate was added after."""
    recs = rule_engine.recommend_stack(
        "We need to connect our on-prem datacenter to AWS over a dedicated link for a "
        "customer support chatbot bolted onto our existing billing application."
    )["recommendations"]

    assert "hybrid_connectivity" in recs
    assert "integration_guidance" in recs
    assert recs["hybrid_connectivity"]["needed"] is True
    assert "Direct Connect" in recs["hybrid_connectivity"]["v"]
    assert recs["integration_guidance"]["patternLabel"] == "chatbot / conversational assistant"


def test_hybrid_connectivity_matches_js_branches():
    """Mirrors index.html's pickHybridConnectivity() branch table, including the air-gapped
    short-circuit that fires BEFORE the hybridConnectivity check."""
    air_gapped = {**rule_engine.detect_signals("x"), "onPrem": True, "hybridConnectivity": True}
    assert rule_engine.pick_hybrid_connectivity(air_gapped, {"v": "AWS"})["needed"] is False

    none_needed = {**rule_engine.detect_signals("x"), "onPrem": False, "hybridConnectivity": False}
    assert rule_engine.pick_hybrid_connectivity(none_needed, {"v": "AWS"})["needed"] is False

    hybrid = {**rule_engine.detect_signals("x"), "onPrem": False, "hybridConnectivity": True}
    for vendor, expected in [
        ("AWS", "AWS Direct Connect"),
        ("Azure", "Azure ExpressRoute"),
        ("Google Cloud", "GCP Cloud Interconnect"),
        ("Huawei Cloud", "Huawei Cloud Direct Connect"),
        ("", "dedicated-interconnect service"),
    ]:
        assert expected in rule_engine.pick_hybrid_connectivity(hybrid, {"v": vendor})["v"], vendor


def test_integration_guidance_branches_on_omnichannel_and_onprem():
    base = rule_engine.detect_signals("x")

    omni = {**base, "brownfieldOmnichannel": True, "onPrem": False}
    assert rule_engine.pick_integration_guidance(omni)["patternLabel"] == "omnichannel AI support"
    assert "channel-routing" in rule_engine.pick_integration_guidance(omni)["integrationPath"]["v"]

    omni_onprem = {**omni, "onPrem": True}
    assert "no public webhooks" in rule_engine.pick_integration_guidance(omni_onprem)["integrationPath"]["v"]

    chatbot_onprem = {**base, "brownfieldOmnichannel": False, "onPrem": True}
    assert "no public webhook" in rule_engine.pick_integration_guidance(chatbot_onprem)["integrationPath"]["v"]


def test_brownfield_omnichannel_signal_is_detected():
    assert rule_engine.detect_signals("omnichannel AI support across web and WhatsApp")["brownfieldOmnichannel"]
    assert not rule_engine.detect_signals("a simple internal dashboard")["brownfieldOmnichannel"]
