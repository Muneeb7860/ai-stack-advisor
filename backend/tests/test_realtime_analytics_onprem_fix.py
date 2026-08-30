"""Regression fix found during the same comprehensive live-QA pass as the Neon/Turso on-prem
fix (test_neon_turso_onprem_fix.py) — same class of bug, second instance found by systematically
checking every category added this session against on-prem for the "recommends a cloud-only
product for an air-gapped requirement" failure mode.

ClickHouse Cloud and Tinybird are both fully-managed SaaS products with no air-gapped deployment
option — unlike the underlying open-source ClickHouse engine itself, which IS self-hostable.
pick_realtime_analytics_vendor (PR #47) never checked onPrem before this fix.

Asserted against BOTH engines (rule_engine.py and index.html's JS twin).
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


ONPREM_REALTIME_TEXT = "This must run fully on-premises, air-gapped, no public cloud. A real-time streaming analytics platform processing live event data."
ONPREM_REALTIME_CLICKHOUSE_TEXT = ONPREM_REALTIME_TEXT + " We already use ClickHouse."


def test_onprem_realtime_analytics_recommends_self_hosted_not_cloud():
    s = detect_signals(ONPREM_REALTIME_TEXT)
    assert s["onPrem"] is True
    rec = recommend_stack(ONPREM_REALTIME_TEXT)["recommendations"]
    v = rec["realtime_analytics"]["v"]
    assert v.startswith("Self-hosted ClickHouse")
    assert rec["realtime_analytics"]["primaryId"] is None


def test_onprem_beats_even_an_explicit_clickhouse_mention():
    """Explicit ClickHouse mention alone (not on-prem) would normally win — but 'ClickHouse
    Cloud' specifically still can't run air-gapped, so on-prem must still redirect to the
    self-hosted OSS engine rather than the managed product."""
    rec = recommend_stack(ONPREM_REALTIME_CLICKHOUSE_TEXT)["recommendations"]
    assert rec["realtime_analytics"]["v"].startswith("Self-hosted ClickHouse")
    assert "ClickHouse Cloud" not in rec["realtime_analytics"]["v"].split(" — ")[0]


def test_clickhouse_cloud_still_recommended_when_not_onprem():
    """Regression guard the other direction — this fix must not disable the normal
    ClickHouse Cloud/Tinybird recommendation generally, only when onPrem is also true."""
    text = "A real-time streaming analytics platform processing live event data, large team."
    rec = recommend_stack(text)["recommendations"]
    assert "ClickHouse Cloud" in rec["realtime_analytics"]["v"]


@requires_node
def test_js_onprem_realtime_analytics_recommends_self_hosted_not_cloud():
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({ONPREM_REALTIME_TEXT!r}));
      console.log(JSON.stringify({{ v: rec.realtimeAnalytics.v, primaryId: rec.realtimeAnalytics.primaryId }}));
    """)
    assert out["v"].startswith("Self-hosted ClickHouse")
    assert out["primaryId"] is None
