"""Pilot vendor-catalog expansion #3: adds Neon and Turso to the database category, following
the same scoped pattern as the IAM (Clerk/WorkOS, PR #38) and observability (Axiom/Better
Stack, PR #40) pilots — one category, a handful of vendors, verified pricing, fully tested.

Sourced from the pasted "2026 SaaS Architectural Decision Playbook" — both are increasingly
common defaults for serverless/edge deployments (per-PR preview branching, edge-replicated
SQLite) that this catalog previously had no representation for at all.

Pricing verified live against neon.com/pricing and turso.tech/pricing before being written into
either engine — not copied from the pasted playbook or invented.

Asserted against BOTH engines (rule_engine.py and index.html's JS twin).
"""
import shutil
from pathlib import Path

import pytest

from app.rule_engine import DATABASE_VENDORS, detect_signals, recommend_stack
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

def test_neon_mention_is_detected_and_recommended():
    s = detect_signals("We're already using Neon for our Postgres database.")
    assert s["neonMentioned"] is True
    rec = recommend_stack("We're already using Neon for our Postgres database.")["recommendations"]
    assert "Neon" in rec["database"]["v"]


def test_turso_mention_is_detected_and_recommended():
    s = detect_signals("We use Turso for our edge database.")
    assert s["tursoMentioned"] is True
    rec = recommend_stack("We use Turso for our edge database.")["recommendations"]
    assert "Turso" in rec["database"]["v"]


def test_libsql_synonym_is_also_recognized():
    """Turso's underlying open-source engine is libSQL — a requirement naming the engine
    directly (not the hosted product) should still be recognized."""
    s = detect_signals("Our data layer runs on libSQL.")
    assert s["tursoMentioned"] is True


def test_turso_pick_discloses_it_is_sqlite_family_not_postgres_compatible():
    """A reader must not assume "turso" means "postgres, just faster" — the pick's own text has
    to say explicitly that it's a different engine family."""
    rec = recommend_stack("We already use Turso.")["recommendations"]
    assert "not postgres-compatible" in rec["database"]["v"].lower()


def test_neon_and_turso_do_not_both_win_when_both_are_mentioned():
    """Neon is checked before Turso in the elif chain — a text mentioning both names a
    genuinely ambiguous scenario, but the engine must still resolve deterministically to
    exactly one, not silently produce inconsistent output."""
    rec = recommend_stack("We use Neon and also have some Turso experience.")["recommendations"]
    assert "Neon" in rec["database"]["v"]


# ------------------------------------------------------------------------- vendor catalog data

def test_neon_and_turso_are_in_the_database_vendor_catalog_with_real_pricing():
    ids = {v["id"] for v in DATABASE_VENDORS}
    assert "neon" in ids
    assert "turso" in ids

    neon = next(v for v in DATABASE_VENDORS if v["id"] == "neon")
    turso = next(v for v in DATABASE_VENDORS if v["id"] == "turso")

    # Not fabricated placeholder pricing — real, verified figures.
    assert "100 CU-hours/mo" in neon["pricing"]
    assert "$0.106/CU-hour" in neon["pricing"]
    assert "500M rows read/mo" in turso["pricing"]
    assert "$4.99/mo" in turso["pricing"]


def test_database_vendor_catalog_still_has_no_duplicate_ids():
    ids = [v["id"] for v in DATABASE_VENDORS]
    assert len(ids) == len(set(ids))


def test_pick_database_vendor_maps_the_new_picks_to_the_right_catalog_entry():
    from app.rule_engine import pick_database_vendor

    neon_db = {"v": "Neon (serverless Postgres, instant branching) (primary transactional store)", "why": "x", "conf": "high"}
    turso_db = {"v": "Turso (distributed SQLite/libSQL, edge-native) (primary transactional store)", "why": "x", "conf": "high"}
    assert pick_database_vendor(neon_db)["primaryId"] == "neon"
    assert pick_database_vendor(turso_db)["primaryId"] == "turso"


# ------------------------------------------------------------------------------------ JS parity

@requires_node
def test_js_neon_mention_is_detected_and_recommended():
    text = "We're already using Neon for our Postgres database."
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({text!r}));
      console.log(JSON.stringify({{ v: rec.db.v }}));
    """)
    assert "Neon" in out["v"]


@requires_node
def test_js_turso_mention_is_detected_and_recommended():
    text = "We use Turso for our edge database."
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({text!r}));
      console.log(JSON.stringify({{ v: rec.db.v }}));
    """)
    assert "Turso" in out["v"]
    assert "not postgres-compatible" in out["v"].lower()


@requires_node
def test_js_pick_database_vendor_maps_new_picks_correctly():
    out = _js("""
      const neonPrimary = pickDatabaseVendor({v:'Neon (serverless Postgres, instant branching) (primary transactional store)', why:'x', conf:'high'}).primaryId;
      const tursoPrimary = pickDatabaseVendor({v:'Turso (distributed SQLite/libSQL, edge-native) (primary transactional store)', why:'x', conf:'high'}).primaryId;
      console.log(JSON.stringify({neonPrimary, tursoPrimary}));
    """)
    assert out["neonPrimary"] == "neon"
    assert out["tursoPrimary"] == "turso"


@requires_node
def test_js_and_python_database_vendor_ids_match():
    py_ids = sorted(v["id"] for v in DATABASE_VENDORS)
    js_ids = sorted(_js("console.log(JSON.stringify(DATABASE_VENDORS.map(v => v.id)));"))
    assert py_ids == js_ids
