"""Regression fix found during a comprehensive live-QA testing pass across the whole session's
work (not from any pasted report or automated test — found by combining on-prem + Neon/Turso
mentions in the actual browser and noticing the tool still recommended a cloud-only product).

Neon and Turso are both fully-managed cloud services with no air-gapped/on-prem deployment
option — unlike MySQL/SQL Server/Oracle Database (all genuinely self-hostable), recommending
either for an on-prem/air-gapped requirement steers the user toward a product that structurally
cannot satisfy their own hard constraint. pick_database's team-skill RDBMS chain (added in the
Neon/Turso pilot, PR #42) never checked onPrem before this fix.

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


NEON_ONPREM_TEXT = "This must run fully on-premises, air-gapped, no public cloud. We already use Neon for our database."
TURSO_ONPREM_TEXT = "This must run fully on-premises, air-gapped, no public cloud. We already use Turso for our database."


def test_neon_mention_does_not_win_over_onprem():
    # The "why" explanation deliberately NAMES Neon/Turso to explain the override — a bare
    # "Neon" not in v would wrongly fail on the correct answer (same substring trap flagged
    # elsewhere this session). Check the pick STARTS WITH PostgreSQL instead.
    s = detect_signals(NEON_ONPREM_TEXT)
    assert s["onPrem"] is True
    assert s["neonMentioned"] is True
    rec = recommend_stack(NEON_ONPREM_TEXT)["recommendations"]
    assert rec["database"]["v"].startswith("PostgreSQL")


def test_turso_mention_does_not_win_over_onprem():
    rec = recommend_stack(TURSO_ONPREM_TEXT)["recommendations"]
    assert rec["database"]["v"].startswith("PostgreSQL")


def test_onprem_fallback_explains_why_neon_was_overridden():
    rec = recommend_stack(NEON_ONPREM_TEXT)["recommendations"]
    assert "no air-gapped deployment option" in rec["database"]["v"]


def test_neon_mention_still_wins_when_not_onprem():
    """Regression guard the other direction — this fix must not disable Neon/Turso mention
    detection generally, only when onPrem is also true."""
    rec = recommend_stack("We already use Neon for our database.")["recommendations"]
    assert "Neon" in rec["database"]["v"]


@requires_node
def test_js_neon_mention_does_not_win_over_onprem():
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({NEON_ONPREM_TEXT!r}));
      console.log(JSON.stringify({{ v: rec.db.v }}));
    """)
    assert out["v"].startswith("PostgreSQL")


@requires_node
def test_js_turso_mention_does_not_win_over_onprem():
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({TURSO_ONPREM_TEXT!r}));
      console.log(JSON.stringify({{ v: rec.db.v }}));
    """)
    assert out["v"].startswith("PostgreSQL")
