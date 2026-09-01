"""A stated concurrency figure has to change the answer.

The defect. `detect_concurrency_target` parsed "500,000 concurrent users" into a structured
`{count: 500000}`, that value was returned in the signals, and **nothing read it**. A requirement
naming half a million concurrent users produced a byte-identical stack to one naming a thousand.
The function's own docstring recorded the gap — "it does not even trip highScale, whose keywords
are 'high traffic'/'millions of users'" — so it was known and left.

This is worse than an unused variable. Concurrency is the single most load-bearing number in a
capacity decision, the product visibly extracted it, and then answered as though it had not been
said. A reader who states their scale precisely and gets generic output has been given evidence
that the tool understood them, which it had not acted on.

The fix routes through `highScale` rather than threading the number into individual picks.
`highScale` is read in roughly 45 places, so one honest signal change reaches every one of them,
and no pick function needs to learn about concurrency parsing. Measured effect on an e-commerce
API at 1,000 vs 500,000 concurrent: 8 picks differ where 0 did before — Go over Python,
Kubernetes over Lambda, Kafka over RabbitMQ, load/soak testing added to the strategy.

Strictly additive, and that matters: the number is OR'd with the existing keywords, never
substituted for them, so "High traffic. About 500 concurrent users at launch." stays high-scale.
A stated low number must not be able to cancel an explicit claim made in the same sentence.

Not fixed here: `timeline` is parsed and unread in exactly the same way. It is a separate signal
with separate consequences and belongs in its own change, not folded into this one.
"""
import json
import re
import shutil
from pathlib import Path

import pytest

from app.rule_engine import CONCURRENCY_HIGH_SCALE_THRESHOLD, recommend_stack
from tests.node_harness import run_node_json

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

BASE = "An e-commerce API for a retail company."


def _signals(text):
    return recommend_stack(text)["signals"]


def _recs(text):
    return recommend_stack(text)["recommendations"]


# --------------------------------------------------------------- the defect, behaviourally

def test_a_large_stated_load_changes_the_recommendation():
    """The whole point. Before this, these two produced identical output."""
    small = _recs(f"{BASE} We expect 1,000 concurrent users.")
    large = _recs(f"{BASE} We expect 500,000 concurrent users.")
    differing = [
        k for k in small
        if isinstance(small[k], dict) and "v" in small[k] and small[k]["v"] != large[k].get("v")
    ]
    assert differing, (
        "a requirement naming 500,000 concurrent users produces the same stack as one naming "
        "1,000 — the number is parsed and then ignored"
    )
    # The picks where load is most obviously binding.
    assert "compute" in differing or "messaging" in differing, (
        f"neither compute nor messaging responded to a 500x load difference; changed: {differing}"
    )


def test_the_stated_number_is_quoted_back_in_the_concurrency_section():
    """Parsing a number and never showing it is how the reader learns the tool ignored them."""
    items = _recs(f"{BASE} We expect 500,000 concurrent users.")["concurrency"]
    assert items and "500,000 concurrent users" in items[0]["t"], (
        f"the concurrency section does not lead with the stated figure: {items[0]['t']!r}"
    )
    assert "500,000 concurrent users" in items[0]["w"]


def test_a_modest_number_is_still_quoted_but_advised_differently():
    """Quoting the figure is not the same as treating every figure as large."""
    items = _recs(f"{BASE} About 800 concurrent users.")["concurrency"]
    assert "800 concurrent users" in items[0]["t"]
    assert "load-bearing" not in items[0]["w"], "modest load should not get the high-scale framing"


def test_no_stated_number_leaves_the_section_unchanged():
    """The lead item must not appear out of nowhere for requirements that state no figure."""
    items = _recs(BASE)["concurrency"]
    assert "Design to your stated load" not in items[0]["t"]


# ------------------------------------------------------------------------- the threshold

@pytest.mark.parametrize("n,expected", [
    (500, False), (1_000, False), (9_999, False),
    (10_000, True), (50_000, True), (500_000, True),
])
def test_the_threshold_is_applied_at_its_boundary(n, expected):
    assert _signals(f"{BASE} We expect {n:,} concurrent users.")["highScale"] is expected


def test_the_threshold_is_a_named_constant_in_both_engines():
    """A literal in one engine and a constant in the other is how they drift apart on every
    requirement stating a number between the two values."""
    m = re.search(r"const CONCURRENCY_HIGH_SCALE_THRESHOLD = (\d+);", INDEX.read_text(encoding="utf-8"))
    assert m, "the JS threshold constant was not found"
    assert int(m.group(1)) == CONCURRENCY_HIGH_SCALE_THRESHOLD, (
        f"JS threshold {m.group(1)} != Python {CONCURRENCY_HIGH_SCALE_THRESHOLD}"
    )


# --------------------------------------------------------------------- additive, not replacing

def test_a_low_stated_number_cannot_cancel_an_explicit_high_traffic_claim():
    """The subtractive failure this guards against: someone writes "High traffic. About 500
    concurrent users at launch." — the launch figure is a starting point, not a ceiling, and must
    not overrule what they said outright."""
    s = _signals(f"{BASE} High traffic. About 500 concurrent users at launch.")
    assert s["highScale"] is True


@pytest.mark.parametrize("phrase", ["high traffic", "millions of users", "peak load", "black friday"])
def test_every_existing_keyword_still_fires_on_its_own(phrase):
    """The keywords predate the number and must keep working without one."""
    assert _signals(f"{BASE} {phrase}.")["highScale"] is True


def test_the_parsed_value_is_still_exposed_unchanged():
    """highScale consuming it must not replace the structured signal other code may read."""
    ct = _signals(f"{BASE} We expect 250,000 concurrent users.")["concurrencyTarget"]
    assert ct and ct["count"] == 250_000
    assert "250,000 concurrent users" in ct["text"]


# ------------------------------------------------------------------------------ dual engine

@requires_node
def test_both_engines_agree_on_scale_and_the_section_lead():
    script = INDEX.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]
    cases = [
        BASE,
        f"{BASE} We expect 1,000 concurrent users.",
        f"{BASE} We expect 10,000 concurrent users.",
        f"{BASE} We expect 500,000 concurrent users.",
        f"{BASE} High traffic. About 500 concurrent users at launch.",
    ]
    stubs = """
const d={style:{},classList:{add(){},remove(){},toggle(){},contains:()=>false},addEventListener(){},
  setAttribute(){},getAttribute:()=>null,querySelector:()=>d,querySelectorAll:()=>[],innerHTML:'',textContent:''};
global.window={innerWidth:1280,location:{search:''},addEventListener(){},matchMedia:()=>({matches:false,addEventListener(){}})};
global.document={documentElement:d,body:d,querySelector:()=>d,querySelectorAll:()=>[],
  getElementById:()=>d,createElement:()=>d,addEventListener(){}};
global.navigator={clipboard:{}};global.localStorage={getItem:()=>null,setItem(){},removeItem(){}};
global.fetch=()=>Promise.resolve({ok:false});global.URL={createObjectURL:()=>'',revokeObjectURL(){}};
global.requestAnimationFrame=(fn)=>fn();
"""
    body = (
        "const cases = " + json.dumps(cases) + ";\n"
        "console.log(JSON.stringify(cases.map(c => {"
        "  const s = detectSignals(c);"
        "  const items = pickConcurrency(s);"
        "  return {highScale: s.highScale, lead: items[0].t,"
        "          count: s.concurrencyTarget ? s.concurrencyTarget.count : null};"
        "})));"
    )
    js = run_node_json(stubs + script + "\n" + body)
    for text, got in zip(cases, js):
        py_s = _signals(text)
        py_items = _recs(text)["concurrency"]
        assert got["highScale"] == py_s["highScale"], f"highScale differs on {text!r}"
        assert got["lead"] == py_items[0]["t"], f"concurrency lead differs on {text!r}"
        py_count = (py_s["concurrencyTarget"] or {}).get("count")
        assert got["count"] == py_count, f"parsed count differs on {text!r}"
