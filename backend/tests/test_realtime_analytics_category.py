"""New vendor category: Real-Time Analytics (Tinybird / ClickHouse Cloud).

Fourth, and final planned, genuinely-new category this session, after GitOps CD (PR #44),
Agent Framework (PR #45), and Inference Serving Engine (PR #46). This one IS a "stack" card
(like GitOps, unlike Agent Framework/Inference Serving) — it's a real infra vendor decision, so
it gets full STACK_CARD_CATEGORY/VALID_CATEGORIES wiring for Refine/Ask/Challenge.

Architectural note: this is NOT a restatement of pick_database's existing generic
"warehouse_need" branch (BigQuery/Snowflake/Redshift). That branch fires on ANY analytics-heavy
workload regardless of latency; those three trade real-time freshness for a mature batch-ETL/
BI-tool ecosystem. This category only fires when the requirement is ALSO explicitly real-time/
streaming (dataHeavy AND realtime) — sub-second queries over continuously-arriving data is a
genuinely different tool category. Tinybird is itself built on managed ClickHouse (verified live
against tinybird.co/pricing and clickhouse.com — Tinybird's own docs describe it as "a managed
ClickHouse platform"), so the two are not fully independent competitors; the `cat`/drawback
fields disclose that explicitly.

Asserted against BOTH engines (rule_engine.py and index.html's JS twin).
"""
import shutil
from pathlib import Path

import pytest

from app.rule_engine import REALTIME_ANALYTICS_VENDORS, detect_signals, recommend_stack
from app.routers.refine import VALID_CATEGORIES
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


REALTIME_TEXT = "A real-time streaming analytics platform processing live event data, large team."
BATCH_ONLY_TEXT = "A big data ETL pipeline and data warehouse for quarterly reporting, no real-time need."
SMALL_TEAM_REALTIME_TEXT = "Early-stage MVP, small team, real-time analytics dashboard on streaming data."
NO_ANALYTICS_TEXT = "A simple marketing website with a contact form."


# ------------------------------------------------------------------------- explicit mentions

def test_tinybird_mention_is_detected_and_recommended():
    s = detect_signals("We already use Tinybird. " + REALTIME_TEXT)
    assert s["tinybirdMentioned"] is True
    rec = recommend_stack("We already use Tinybird. " + REALTIME_TEXT)["recommendations"]
    assert rec["realtime_analytics"]["v"] == "Tinybird"


def test_clickhouse_mention_is_detected_and_recommended():
    s = detect_signals("We already use ClickHouse. " + REALTIME_TEXT)
    assert s["clickhouseMentioned"] is True
    rec = recommend_stack("We already use ClickHouse. " + REALTIME_TEXT)["recommendations"]
    assert rec["realtime_analytics"]["v"] == "ClickHouse Cloud"


def test_clickhouse_pick_discloses_tinybird_is_built_on_it():
    rec = recommend_stack("We already use ClickHouse. " + REALTIME_TEXT)["recommendations"]
    assert "Tinybird is built on managed ClickHouse too" in rec["realtime_analytics"]["why"]


# ------------------------------------------------------------------------- gating: dataHeavy+realtime

def test_batch_only_analytics_gets_not_applicable():
    """dataHeavy fires here, but realtime does not — this must NOT get a Tinybird/ClickHouse
    recommendation; pick_database's own warehouse_need branch handles this case instead."""
    rec = recommend_stack(BATCH_ONLY_TEXT)["recommendations"]
    assert "Not applicable" in rec["realtime_analytics"]["v"]
    assert rec["realtime_analytics"]["primaryId"] is None


def test_no_analytics_need_gets_not_applicable():
    rec = recommend_stack(NO_ANALYTICS_TEXT)["recommendations"]
    assert "Not applicable" in rec["realtime_analytics"]["v"]


def test_realtime_and_data_heavy_together_gets_a_real_recommendation():
    rec = recommend_stack(REALTIME_TEXT)["recommendations"]
    assert rec["realtime_analytics"]["v"] in (
        "ClickHouse Cloud (or Tinybird if you want a developer-first API layer built on top of it)",
        "ClickHouse Cloud",
    )
    assert rec["realtime_analytics"]["primaryId"] == "clickhouse"


def test_small_team_realtime_defaults_to_tinybird():
    rec = recommend_stack(SMALL_TEAM_REALTIME_TEXT)["recommendations"]
    assert rec["realtime_analytics"]["v"] == "Tinybird"
    assert rec["realtime_analytics"]["primaryId"] == "tinybird"


# -------------------------------------------------------------------------- exclusion handling

def test_excluding_databases_replaces_the_primary_realtime_analytics_text_too():
    """Regression lock mirroring the exact bug found while wiring GitOps: this category has no
    separate underlying pick, so merely suppressing the vendor comparison would leave the
    PRIMARY text still recommending ClickHouse/Tinybird after databases were excluded."""
    text = "We don't want any database at all, pure client-side app. " + REALTIME_TEXT
    rec = recommend_stack(text)["recommendations"]
    assert "excluded databases" in rec["realtime_analytics"]["v"]
    assert rec["realtime_analytics_vendor"].get("suppressed") is True
    assert rec["realtime_analytics_vendor"].get("primaryId") is None


# ------------------------------------------------------------------------- vendor catalog data

def test_clickhouse_and_tinybird_are_in_the_catalog_with_correct_relationship_disclosed():
    ids = {v["id"] for v in REALTIME_ANALYTICS_VENDORS}
    assert ids == {"clickhouse", "tinybird"}

    tinybird = next(v for v in REALTIME_ANALYTICS_VENDORS if v["id"] == "tinybird")
    assert "Managed ClickHouse" in tinybird["cat"]


def test_realtime_analytics_vendor_catalog_has_no_duplicate_ids():
    ids = [v["id"] for v in REALTIME_ANALYTICS_VENDORS]
    assert len(ids) == len(set(ids))


# -------------------------------------------------------------------- refine/ask/challenge wiring

def test_realtime_analytics_is_reachable_from_refine():
    """Unlike Agent Framework/Inference Serving (bespoke AI-layer sections), this IS a real
    stack card — regression lock for the same defect test_kb_promoted_categories.py documents
    fixing for six earlier cards."""
    assert "realtimeanalytics" in VALID_CATEGORIES


# ------------------------------------------------------------------------------------ JS parity

@requires_node
def test_js_tinybird_mention_is_detected_and_recommended():
    text = "We already use Tinybird. " + REALTIME_TEXT
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({text!r}));
      console.log(JSON.stringify({{ v: rec.realtimeAnalytics.v }}));
    """)
    assert out["v"] == "Tinybird"


@requires_node
def test_js_batch_only_gets_not_applicable():
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({BATCH_ONLY_TEXT!r}));
      console.log(JSON.stringify({{ v: rec.realtimeAnalytics.v }}));
    """)
    assert "Not applicable" in out["v"]


@requires_node
def test_js_excluding_databases_replaces_the_primary_text_too():
    text = "We don't want any database at all, pure client-side app. " + REALTIME_TEXT
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({text!r}));
      console.log(JSON.stringify({{ v: rec.realtimeAnalytics.v, suppressed: rec.realtimeAnalyticsVendorPick.suppressed }}));
    """)
    assert "excluded databases" in out["v"]
    assert out["suppressed"] is True


@requires_node
def test_js_and_python_realtime_analytics_vendor_ids_match():
    py_ids = sorted(v["id"] for v in REALTIME_ANALYTICS_VENDORS)
    js_ids = sorted(_js("console.log(JSON.stringify(REALTIME_ANALYTICS_VENDORS.map(v => v.id)));"))
    assert py_ids == js_ids


@requires_node
def test_js_stack_card_category_includes_realtime_analytics():
    out = _js("console.log(JSON.stringify(STACK_CARD_CATEGORY['Real-Time Analytics']));")
    assert out == "realtimeanalytics"
