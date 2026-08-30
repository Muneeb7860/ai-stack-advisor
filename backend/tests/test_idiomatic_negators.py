"""Regression tests for the two idiomatic-negator gaps logged as "Failed - Known Gap (not
fixed this pass)" in docs/market-scenario-test-log.csv rows A6/A7, and independently confirmed
against a pasted external technical proposal that also named them as a real weakness in the
regex-only negation engine:

1. "X is off the table" — the excluded subject sits BEFORE the idiom (same grammar as the
   existing passive-negation phrases: "must not be used", "is ruled out", ...).
2. "skip X" / "ditch X" / "steer clear of X" — active-voice idioms where the excluded subject
   follows the negator word, same grammar as the existing "avoid X" (added in an earlier pass).

Scope, per explicit user decision: fix ONLY the idiomatic negators — no LLM/semantic layer, no
architecture change. Purely additive regex entries in the existing deterministic engine.

Asserted against BOTH engines (rule_engine.py and index.html's JS twin).
"""
import shutil
from pathlib import Path

import pytest

from app.rule_engine import detect_exclusions, recommend_stack
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


OFF_THE_TABLE_TEXT = "Kubernetes is off the table for this project — the team can't operate it."
SKIP_TEXT = "Please skip Kubernetes entirely, we want something simpler."
DITCH_TEXT = "We want to ditch MongoDB for our next project."
STEER_CLEAR_TEXT = "We should steer clear of AWS for this one, cost is a concern."


# ------------------------------------------------------------------------ "off the table"

def test_off_the_table_excludes_the_named_technology():
    assert detect_exclusions(OFF_THE_TABLE_TEXT).get("kubernetes") is True


def test_off_the_table_flows_through_to_the_final_recommendation():
    # The pick's own wording deliberately says "not Kubernetes" as an explicit callout — a
    # naive "kubernetes" not in v would wrongly fail on the CORRECT answer (same substring
    # trap as "Java" vs "JavaScript" caught earlier this session). Check for the real
    # replacement pick instead of a bare substring absence.
    rec = recommend_stack(OFF_THE_TABLE_TEXT)["recommendations"]
    v = rec["containers"]["v"].lower()
    assert "serverless containers" in v
    assert "self-managed kubernetes" not in v


# ---------------------------------------------------------------------------------- "skip X"

def test_skip_excludes_the_named_technology():
    assert detect_exclusions(SKIP_TEXT).get("kubernetes") is True


def test_skip_flows_through_to_the_final_recommendation():
    rec = recommend_stack(SKIP_TEXT)["recommendations"]
    v = rec["containers"]["v"].lower()
    assert "serverless containers" in v
    assert "self-managed kubernetes" not in v


# --------------------------------------------------------------------------------- "ditch X"

def test_ditch_excludes_the_named_technology():
    assert detect_exclusions(DITCH_TEXT).get("database") is True


# ------------------------------------------------------------------------ "steer clear of X"

def test_steer_clear_of_excludes_the_named_technology():
    assert detect_exclusions(STEER_CLEAR_TEXT).get("cloud") is True


# ------------------------------------------------------------------------------- safety net

def test_skip_alone_with_nothing_excludable_records_nothing():
    """Mirrors the existing "avoid" safety-net test: an idiom firing with no recognized
    EXCLUSION_TERMS match in its clause must not fabricate an exclusion out of thin air."""
    assert detect_exclusions("Let's skip the small talk and get started.") == {}


def test_ditch_alone_with_nothing_excludable_records_nothing():
    assert detect_exclusions("We want to ditch our old process and move faster.") == {}


# --------------------------------------------------------------------------------- JS parity

@requires_node
@pytest.mark.parametrize("text,key", [
    (OFF_THE_TABLE_TEXT, "kubernetes"),
    (SKIP_TEXT, "kubernetes"),
    (DITCH_TEXT, "database"),
    (STEER_CLEAR_TEXT, "cloud"),
])
def test_js_idiomatic_negators_match_python(text, key):
    out = _js(f"console.log(JSON.stringify(detectExclusions({text!r})));")
    assert out.get(key) is True


@requires_node
def test_js_off_the_table_flows_through_to_the_final_recommendation():
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({OFF_THE_TABLE_TEXT!r}));
      console.log(JSON.stringify({{ v: rec.containers.v }}));
    """)
    v = out["v"].lower()
    assert "serverless containers" in v
    assert "self-managed kubernetes" not in v
