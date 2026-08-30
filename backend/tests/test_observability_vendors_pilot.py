"""Pilot vendor-catalog expansion #2: adds Axiom and Better Stack to the observability
category, following the same scoped pattern as the IAM/CIAM pilot (Clerk/WorkOS) — one
category, a handful of vendors, verified pricing, fully tested.

Sourced from the pasted "2026 SaaS Architectural Decision Playbook" (Axiom and Better Stack
were named there); SigNoz, also named in that document, was already in OBSERVABILITY_VENDORS
before this pilot and needed no new work.

Pricing verified live against axiom.co/pricing and betterstack.com/pricing before being
written into either engine — not copied from the pasted playbook or invented.

Asserted against BOTH engines (rule_engine.py and index.html's JS twin).
"""
import shutil
from pathlib import Path

import pytest

from app.rule_engine import OBSERVABILITY_VENDORS, detect_signals, recommend_stack
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


# ------------------------------------------------------------------------- explicit mentions

def test_axiom_mention_is_detected_and_recommended():
    s = detect_signals("We're already using Axiom for our logs.")
    assert s["axiomMentioned"] is True
    rec = recommend_stack("We're already using Axiom for our logs.")["recommendations"]
    assert "Axiom" in rec["observability"]["v"]


def test_better_stack_mention_is_detected_and_recommended():
    s = detect_signals("We use Better Stack for uptime monitoring and logs.")
    assert s["betterStackMentioned"] is True
    rec = recommend_stack("We use Better Stack for uptime monitoring and logs.")["recommendations"]
    assert "Better Stack" in rec["observability"]["v"]


def test_better_uptime_synonym_is_also_recognized():
    """Better Stack was formerly branded "Better Uptime" — a user citing the old name should
    still be recognized, not silently miss the mention."""
    s = detect_signals("Our on-call setup runs on Better Uptime.")
    assert s["betterStackMentioned"] is True


def test_axiom_pick_discloses_it_is_not_a_full_apm_suite():
    rec = recommend_stack("We already use Axiom.")["recommendations"]
    assert "not a full apm suite" in rec["observability"]["why"].lower()


# ------------------------------------------------------------------------- vendor catalog data

def test_axiom_and_better_stack_are_in_the_observability_vendor_catalog_with_real_pricing():
    ids = {v["id"] for v in OBSERVABILITY_VENDORS}
    assert "axiom" in ids
    assert "betterstack" in ids

    axiom = next(v for v in OBSERVABILITY_VENDORS if v["id"] == "axiom")
    betterstack = next(v for v in OBSERVABILITY_VENDORS if v["id"] == "betterstack")

    # Not fabricated placeholder pricing — real, verified figures.
    assert "500GB/mo" in axiom["pricing"]
    assert "$25/mo" in axiom["pricing"]
    assert "10 monitors" in betterstack["pricing"]
    assert "$9/responder/mo" in betterstack["pricing"]


def test_observability_vendor_catalog_still_has_no_duplicate_ids():
    ids = [v["id"] for v in OBSERVABILITY_VENDORS]
    assert len(ids) == len(set(ids))


def test_pick_observability_vendor_maps_the_new_picks_to_the_right_catalog_entry():
    from app.rule_engine import pick_observability_vendor

    axiom_obs = {"v": "OpenTelemetry (instrumentation standard) + Axiom", "why": "x", "conf": "high"}
    betterstack_obs = {"v": "OpenTelemetry (instrumentation standard) + Better Stack", "why": "x", "conf": "high"}
    assert pick_observability_vendor({}, axiom_obs)["primaryId"] == "axiom"
    assert pick_observability_vendor({}, betterstack_obs)["primaryId"] == "betterstack"


# ------------------------------------------------------------------------------------ JS parity

@requires_node
def test_js_axiom_mention_is_detected_and_recommended():
    text = "We're already using Axiom for our logs."
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({text!r}));
      console.log(JSON.stringify({{ v: rec.obs.v, why: rec.obs.why }}));
    """)
    assert "Axiom" in out["v"]
    assert "not a full apm suite" in out["why"].lower()


@requires_node
def test_js_better_stack_mention_is_detected_and_recommended():
    text = "We use Better Stack for uptime monitoring and logs."
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({text!r}));
      console.log(JSON.stringify({{ v: rec.obs.v }}));
    """)
    assert "Better Stack" in out["v"]


@requires_node
def test_js_pick_observability_vendor_maps_new_picks_correctly():
    out = _js("""
      const axiomPrimary = pickObservabilityVendor({}, {v:'OpenTelemetry (instrumentation standard) + Axiom', why:'x', conf:'high'}).primaryId;
      const betterstackPrimary = pickObservabilityVendor({}, {v:'OpenTelemetry (instrumentation standard) + Better Stack', why:'x', conf:'high'}).primaryId;
      console.log(JSON.stringify({axiomPrimary, betterstackPrimary}));
    """)
    assert out["axiomPrimary"] == "axiom"
    assert out["betterstackPrimary"] == "betterstack"


@requires_node
def test_js_and_python_observability_vendor_ids_match():
    py_ids = sorted(v["id"] for v in OBSERVABILITY_VENDORS)
    js_ids = sorted(_js("console.log(JSON.stringify(OBSERVABILITY_VENDORS.map(v => v.id)));"))
    assert py_ids == js_ids
