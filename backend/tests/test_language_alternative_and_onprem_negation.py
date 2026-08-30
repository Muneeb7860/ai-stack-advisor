"""Regression tests for two follow-up fixes requested directly by the user after the market-
scenario sweep (test_negation_v2_market_scenarios.py):

1. "not on-prem" (negating on-prem itself) used to be detected as ON-PREM anyway — soft on-prem
   detection read the bare substring "on-prem"/"on premises" with zero awareness that the
   phrase could itself be negated, recommending on-prem hosting for a requirement that
   explicitly ruled it out.
2. When a language exclusion fires ("neither Java nor Python"), a bare "not recommended" stub
   isn't what a human architect would say — they'd name a real, context-appropriate
   alternative. This is exactly what the user asked for directly, with a worked example.

Asserted against BOTH engines.
"""
import shutil
from pathlib import Path

import pytest

from app.rule_engine import detect_signals, recommend_stack
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


COMPOUND_NEGATION_TEXT = (
    "We need a backend that isn't microservices, doesn't use SQL, won't run on AWS, "
    "without Docker, but also not on-prem."
)
WEB_ONLY_NEITHER_TEXT = "We need a web application. Neither Java nor Python should be used for the backend — browser-based only."


# ------------------------------------------------------------------ on-prem negation

@pytest.mark.parametrize("text,expected", [
    (COMPOUND_NEGATION_TEXT, False),
    ("Our infrastructure will not be on-premises, we want to stay fully cloud.", False),
    ("We do not want on-premises hosting.", False),
    ("Avoid on-prem entirely, go full cloud.", False),
    ("This must run on-premises, not in the cloud.", True),
    ("We need on-prem deployment for compliance.", True),
])
def test_negated_on_prem_phrasings_do_not_set_onprem(text, expected):
    assert detect_signals(text)["onPrem"] is expected, text


def test_compound_negation_no_longer_recommends_on_prem_hosting():
    rec = recommend_stack(COMPOUND_NEGATION_TEXT)["recommendations"]
    assert "on-prem" not in rec["cloud"]["v"].lower()


def test_hybrid_on_prem_and_cloud_still_correctly_suppressed_by_the_hybrid_guard():
    """Regression guard: the new negation-awareness check must not interfere with the
    pre-existing "hybrid on-prem and cloud" carve-out, which is a real, different signal
    (hybridConnectivity), not a negation of on-prem itself."""
    s = detect_signals("Hybrid on-prem and cloud with a dedicated link to AWS.")
    assert s["onPrem"] is False
    assert s["hybridConnectivity"] is True


# --------------------------------------------------------------- language alternatives

def test_language_exclusion_recommends_a_real_alternative_not_a_bare_stub():
    rec = recommend_stack(WEB_ONLY_NEITHER_TEXT)["recommendations"]
    assert rec["languages"]["excluded"] is True
    assert "not recommended" not in rec["languages"]["v"].lower()
    assert "JavaScript" in rec["languages"]["v"]


@pytest.mark.parametrize("text,expected_substring", [
    ("We need a mobile app backend. Neither Java nor Python for the backend.", "Swift"),
    ("Large enterprise platform. We must not use Java or Python.", "C#"),
    ("A real-time trading platform with high scale. Avoid Java and Python entirely.", "Go"),
])
def test_alternative_is_context_appropriate(text, expected_substring):
    rec = recommend_stack(text)["recommendations"]
    assert expected_substring in rec["languages"]["v"]


def test_alternative_never_recommends_a_language_also_explicitly_excluded():
    # "web application" is the literal EXCLUSION_TERMS/web-signal phrase that reliably drives
    # the alternative picker toward JavaScript first (see WEB_ONLY_NEITHER_TEXT above) — this
    # test specifically needs that branch to be LIVE so excluding JavaScript too actually
    # exercises the avoidance guard, not just coincidentally never reaching it.
    text = "We need a web application. Neither Java, Python, nor JavaScript should be used for the backend."
    rec = recommend_stack(text)["recommendations"]
    assert "JavaScript" not in rec["languages"]["v"]


def test_go_is_always_the_last_resort_since_it_can_never_be_tracked_as_excluded():
    """Documents a real, deliberate trade-off rather than hiding it: bare "go" is absent from
    EXCLUSION_TERMS["languages"] (too common a word in ordinary English to safely detect as an
    exclusion — see that table's own comment), which means it can never be excluded either, by
    construction. Excluding every OTHER alternative this tool knows still falls back to Go, not
    the "every alternative was excluded" message — there is currently no real user phrasing that
    can reach that message, which is itself worth knowing rather than assuming untested."""
    from app.rule_engine import _pick_language_alternative

    all_non_go_terms = {"javascript", "typescript", "node.js", "nodejs", "c#", ".net",
                         "kotlin", "swift", "rust", "ruby", "php"}
    result = _pick_language_alternative({}, all_non_go_terms)
    assert result["v"].startswith("Go")


# --------------------------------------------------------------------------- JS parity

@requires_node
@pytest.mark.parametrize("text,expected", [
    (COMPOUND_NEGATION_TEXT, False),
    ("We do not want on-premises hosting.", False),
    ("We need on-prem deployment for compliance.", True),
])
def test_js_negated_on_prem_phrasings_match_python(text, expected):
    out = _js(f"console.log(JSON.stringify(detectSignals({text!r}).onPrem));")
    assert out is expected


@requires_node
def test_js_language_exclusion_recommends_the_same_alternative_as_python():
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({WEB_ONLY_NEITHER_TEXT!r}));
      console.log(JSON.stringify({{ v: rec.lang.v, excluded: rec.lang.excluded }}));
    """)
    assert out["excluded"] is True
    assert "JavaScript" in out["v"]


@requires_node
def test_js_alternative_never_recommends_a_language_also_explicitly_excluded():
    text = "We need a web application. Neither Java, Python, nor JavaScript should be used for the backend."
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({text!r}));
      console.log(JSON.stringify({{ v: rec.lang.v }}));
    """)
    assert "JavaScript" not in out["v"]
