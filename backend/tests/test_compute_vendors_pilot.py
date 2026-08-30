"""Pilot vendor-catalog expansion #4: adds Coolify and Dokploy to the compute-platform
category, following the same scoped pattern as the IAM (PR #38), observability (PR #40), and
database (PR #42) pilots — one category, a handful of vendors, verified pricing, fully tested.

Sourced from the pasted "2026 SaaS Architectural Decision Playbook" (Coolify was named there;
Dokploy added as its most direct, comparably-positioned open-source alternative, so a reader
comparing self-hosted PaaS options sees more than one name).

This pilot also improves a real, pre-existing gap found while scoping it: pick_compute_platform
used to return a bare "N/A — self-hosted only" non-answer for on-prem/air-gapped requirements,
even though Coolify/Dokploy are genuinely self-hostable PaaS layers that DO work air-gapped
(unlike every other vendor in this comparison, which are public-cloud SaaS). On-prem now gets a
real, useful recommendation instead of a dead end.

Pricing verified live against coolify.io/pricing and dokploy.com/pricing before being written
into either engine — not copied from the pasted playbook or invented.

Asserted against BOTH engines (rule_engine.py and index.html's JS twin).
"""
import shutil
from pathlib import Path

import pytest

from app.rule_engine import COMPUTE_VENDORS, detect_signals, recommend_stack
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

def test_coolify_mention_is_detected_and_recommended():
    s = detect_signals("We're already using Coolify to deploy our apps.")
    assert s["coolifyMentioned"] is True
    rec = recommend_stack("We're already using Coolify to deploy our apps.")["recommendations"]
    assert rec["compute_platform_vendor"]["v"] == "Coolify"


def test_dokploy_mention_is_detected_and_recommended():
    s = detect_signals("We use Dokploy for deployments.")
    assert s["dokployMentioned"] is True
    rec = recommend_stack("We use Dokploy for deployments.")["recommendations"]
    assert rec["compute_platform_vendor"]["v"] == "Dokploy"


# ------------------------------------------------------------------- on-prem gap improvement

def test_onprem_no_longer_gets_a_bare_na_stub():
    """The real gap this pilot closes: on-prem used to get a dead-end 'N/A' non-answer even
    though Coolify/Dokploy are genuinely self-hostable and DO work air-gapped."""
    rec = recommend_stack("This must run fully on-premises, air-gapped, no public cloud.")["recommendations"]
    v = rec["compute_platform_vendor"]["v"]
    assert v != "N/A — self-hosted only, see Compute Model card above"
    assert "Coolify" in v


def test_onprem_pick_explains_why_this_differs_from_every_other_vendor_in_the_comparison():
    rec = recommend_stack("This must run fully on-premises, air-gapped, no public cloud.")["recommendations"]
    why = rec["compute_platform_vendor"]["why"].lower()
    assert "air-gapped" in why
    assert "self-host" in why


def test_onprem_explicit_coolify_mention_still_wins_over_the_generic_onprem_branch():
    rec = recommend_stack("Fully on-premises, air-gapped. We already run Coolify.")["recommendations"]
    assert rec["compute_platform_vendor"]["v"] == "Coolify"


# ------------------------------------------------------------------------- vendor catalog data

def test_coolify_and_dokploy_are_in_the_compute_vendor_catalog_with_real_pricing():
    ids = {v["id"] for v in COMPUTE_VENDORS}
    assert "coolify" in ids
    assert "dokploy" in ids

    coolify = next(v for v in COMPUTE_VENDORS if v["id"] == "coolify")
    dokploy = next(v for v in COMPUTE_VENDORS if v["id"] == "dokploy")

    # Not fabricated placeholder pricing — real, verified figures.
    assert "free forever" in coolify["pricing"].lower()
    assert "$5/mo" in coolify["pricing"]
    assert "$4.50/mo/server" in dokploy["pricing"]
    assert "$15/mo" in dokploy["pricing"]


def test_compute_vendor_catalog_still_has_no_duplicate_ids():
    ids = [v["id"] for v in COMPUTE_VENDORS]
    assert len(ids) == len(set(ids))


# ------------------------------------------------------------------------------------ JS parity

@requires_node
def test_js_coolify_mention_is_detected_and_recommended():
    text = "We're already using Coolify to deploy our apps."
    out = _js(f"""
      const s = detectSignals({text!r});
      const compute = pickCompute(s);
      const pick = pickComputePlatform(s, compute);
      console.log(JSON.stringify({{ v: pick.v }}));
    """)
    assert out["v"] == "Coolify"


@requires_node
def test_js_onprem_no_longer_gets_a_bare_na_stub():
    text = "This must run fully on-premises, air-gapped, no public cloud."
    out = _js(f"""
      const s = detectSignals({text!r});
      const compute = pickCompute(s);
      const pick = pickComputePlatform(s, compute);
      console.log(JSON.stringify({{ v: pick.v, why: pick.why }}));
    """)
    assert out["v"] != "N/A — self-hosted only, see Compute Model card above"
    assert "Coolify" in out["v"]
    assert "air-gapped" in out["why"].lower()


@requires_node
def test_js_and_python_compute_vendor_ids_match():
    py_ids = sorted(v["id"] for v in COMPUTE_VENDORS)
    js_ids = sorted(_js("console.log(JSON.stringify(COMPUTE_VENDORS.map(v => v.id)));"))
    assert py_ids == js_ids
