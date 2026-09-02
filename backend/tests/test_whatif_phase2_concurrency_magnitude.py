"""What-if scope, Phase 2 — a stated concurrency figure's MAGNITUDE, not just its threshold.

The gap this closes. `CONCURRENCY_HIGH_SCALE_THRESHOLD` (10,000, added when the concurrency signal
itself was fixed) makes `highScale` true above that figure, and that boolean already reaches ~45
call sites. But nothing beyond it reads the actual number — so a requirement stating 50,000
concurrent and one stating 5,000,000 concurrent produced byte-identical output past that one
threshold. Verified before writing this change, and re-verified below as the test that would catch
a regression back to that state.

`CONCURRENCY_MASSIVE_MIN` (1,000,000) marks a genuinely different band, not a bigger version of
`highScale`. Below it, a well-run single-region deployment with read replicas and a cache tier
holds up under ordinary engineering practice. Above it, the standard playbook changes shape:
horizontal sharding of the primary datastore, a cache tier that is load-bearing rather than
optional, regional isolation. That is a different set of problems, not the same plan on bigger
boxes — which is why this landed as a new tradeoff-section entry rather than a third band bolted
onto the concurrency section's existing two-band lead item (itself already shipped and tested; this
change is purely additive alongside it, not a modification to it).

Deliberately NOT wired into a vendor pick's `v` field (e.g. `pick_cache`). Checked first: the
Caching card's alternatives widget stars a hardcoded `'redis'` id independent of what `cache.v`
says, so changing `cache.v` by scale would desync the headline pick from the vendor comparison it
sits next to — a new inconsistency, not a fix. `pick_tradeoffs` has no such coupling (no vendor
catalog, no alt-toggle), which is why it was the safe site for this.

The shared dual-engine comparison (`test_engine_differential.py`) does not compare `tradeoffs`
content at all — same gap the timeline change hit in the previous PR — so this file carries its own
dual-engine check, following that same precedent rather than expanding the shared harness.
"""
import json
import re
import shutil
from pathlib import Path

import pytest

from app.rule_engine import CONCURRENCY_HIGH_SCALE_THRESHOLD, CONCURRENCY_MASSIVE_MIN, recommend_stack
from tests.node_harness import run_node_json

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

BASE = "A social media platform for young professionals."


def _tradeoffs(extra: str):
    return recommend_stack(f"{BASE} {extra}")["recommendations"]["tradeoffs"]


def _has_posture_entry(tradeoffs):
    return any(x["d"].startswith("Architecture posture") for x in tradeoffs)


# --------------------------------------------------------------------------- the regression itself

def test_50k_and_5m_concurrent_no_longer_produce_identical_output():
    """The exact case measured before this change: both stated figures were above
    CONCURRENCY_HIGH_SCALE_THRESHOLD and therefore identical past that one boolean."""
    small = _tradeoffs("We expect 50,000 concurrent users.")
    huge = _tradeoffs("We expect 5,000,000 concurrent users.")
    assert not _has_posture_entry(small), "50,000 must not read as massive scale"
    assert _has_posture_entry(huge), "5,000,000 must be recognised as a genuinely different band"
    assert small != huge, "the two stated figures still produce identical tradeoffs"


@pytest.mark.parametrize("n,expect", [
    (CONCURRENCY_MASSIVE_MIN - 1, False),
    (CONCURRENCY_MASSIVE_MIN, True),
    (CONCURRENCY_MASSIVE_MIN * 5, True),
])
def test_the_threshold_is_applied_at_its_boundary(n, expect):
    assert _has_posture_entry(_tradeoffs(f"We expect {n:,} concurrent users.")) is expect


def test_the_two_thresholds_are_genuinely_different_values():
    """If these were ever equal, the "different band" framing in the docstring above would be
    false — highScale and this entry would fire at the same point."""
    assert CONCURRENCY_MASSIVE_MIN > CONCURRENCY_HIGH_SCALE_THRESHOLD * 10


def test_a_stated_figure_below_the_threshold_gives_no_posture_entry_at_all():
    assert not _has_posture_entry(_tradeoffs("We expect 900,000 concurrent users."))


def test_no_stated_figure_gives_no_posture_entry():
    assert not _has_posture_entry(recommend_stack(BASE)["recommendations"]["tradeoffs"])


# ---------------------------------------------------------------------------------- the content

def test_the_stated_figure_is_quoted_back():
    entry = next(x for x in _tradeoffs("We expect 2,500,000 concurrent users.")
                 if x["d"].startswith("Architecture posture"))
    assert "2,500,000" in entry["d"] or "2500000" in entry["d"].replace(",", "")
    assert "2,500,000" in entry["why"] or "2500000" in entry["why"].replace(",", "")


def test_the_advice_names_the_actual_architectural_shift():
    """Not just "this is a lot of traffic" — the specific, checkable claims: sharding, a
    load-bearing cache tier, regional isolation. A generic restatement of the number would be
    exactly the kind of decoration this session has been removing elsewhere."""
    entry = next(x for x in _tradeoffs("We expect 3,000,000 concurrent users.")
                 if x["d"].startswith("Architecture posture"))
    for term in ("sharding", "cache", "region"):
        assert term in entry["why"].lower(), f"{term!r} missing from the advice"


# --------------------------------------------------------------------------- doesn't disturb Phase 1

def test_the_existing_highscale_threshold_and_its_45_call_sites_are_unaffected():
    """This change is additive. highScale's own behaviour, fixed in the previous change, must be
    untouched by adding a second, higher threshold."""
    s50k = recommend_stack(f"{BASE} We expect 50,000 concurrent users.")["signals"]
    assert s50k["highScale"] is True, "the original fix must still hold at 50,000"


def test_the_existing_two_band_concurrency_lead_item_is_unaffected():
    """pick_concurrency's own lead item (Phase 1) still leads with the quoted figure and its
    original two-band advice; this change did not touch that function."""
    items = recommend_stack(f"{BASE} We expect 5,000,000 concurrent users.")["recommendations"]["concurrency"]
    assert items[0]["t"].startswith("Design to your stated load")


# ------------------------------------------------------------------------------- not a vendor pick

def test_no_vendor_pick_v_field_changed_by_this():
    """Deliberately not wired into pick_cache: its alt-toggle stars a hardcoded vendor id
    independent of `.v`, so changing `.v` by scale would desync the headline from the comparison
    widget next to it. Guards against that coupling being reintroduced later."""
    small = recommend_stack(f"{BASE} We expect 50,000 concurrent users.")["recommendations"]
    huge = recommend_stack(f"{BASE} We expect 5,000,000 concurrent users.")["recommendations"]
    differing = [
        k for k in small
        if isinstance(small[k], dict) and "v" in small[k] and small[k]["v"] != huge[k].get("v")
    ]
    assert differing == [], f"a vendor pick's v changed by concurrency magnitude alone: {differing}"


# ----------------------------------------------------------------------------------- dual engine

@requires_node
def test_both_engines_agree():
    """test_engine_differential.py does not compare tradeoffs content at all (same gap the
    timeline change hit previously), so this file carries its own check rather than expanding the
    shared harness."""
    script = INDEX.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]
    cases = [
        BASE,
        f"{BASE} We expect 50,000 concurrent users.",
        f"{BASE} We expect 999,999 concurrent users.",
        f"{BASE} We expect 1,000,000 concurrent users.",
        f"{BASE} We expect 5,000,000 concurrent users.",
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
        "  const t = pickTradeoffs(detectSignals(c));"
        "  const e = t.find(x => x.d.startsWith('Architecture posture'));"
        "  return {present: !!e, d: e ? e.d : null};"
        "})));"
    )
    js = run_node_json(stubs + script + "\n" + body)
    for text, got in zip(cases, js):
        py_present = any(x["d"].startswith("Architecture posture") for x in recommend_stack(text)["recommendations"]["tradeoffs"])
        assert got["present"] == py_present, f"engines disagree on presence for {text!r}"
        if py_present:
            py_d = next(x["d"] for x in recommend_stack(text)["recommendations"]["tradeoffs"]
                        if x["d"].startswith("Architecture posture"))
            assert got["d"] == py_d, f"engines disagree on the entry text for {text!r}"


def test_the_threshold_is_a_named_constant_in_both_engines():
    m = re.search(r"const CONCURRENCY_MASSIVE_MIN = (\d+);", INDEX.read_text(encoding="utf-8"))
    assert m, "CONCURRENCY_MASSIVE_MIN is not a named constant in index.html"
    assert int(m.group(1)) == CONCURRENCY_MASSIVE_MIN
