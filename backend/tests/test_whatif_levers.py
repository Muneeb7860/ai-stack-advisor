"""What-if levers — Phase 1 of docs/design/WHATIF_LEVERS_SCOPE.md.

Named stops, not sliders. 146 of the engine's 152 signals are boolean, so a continuous control
would move nothing across most of its travel and then flip the whole stack in a single step — a
control that lies about its own resolution. The scope measured this before any code was written.

No engine change and no dual-engine parity surface: levers override signals on the way into
`computeRecommendations`, and both engines are untouched.

The failure this feature most invites is a control that does nothing. A lever whose stops move no
recommendation is decoration that implies the tool models something it does not, so the central
test here is not "does the control render" but "does each stop change the answer". Measured while
building, on a plain e-commerce requirement: team 3-5 picks, scale 8, compliance 7, stage 10-15.
Those numbers are not asserted directly — they would rot — but the property they demonstrate is.

Deliberately not built: a budget lever. No cost-sensitivity signal exists to drive one, and adding
it means deciding whether this product will claim a single cost figure, which it currently refuses
to do (`test_hero_does_not_invent_a_single_cost_figure`). That is a product decision, not an
implementation one.
"""
import json
import re
import shutil
from pathlib import Path

import pytest

from tests.node_harness import run_node_json

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

_STUBS = r"""
const d={style:{},classList:{add(){},remove(){},toggle(){},contains:()=>false},addEventListener(){},
  setAttribute(){},getAttribute:()=>null,querySelector:()=>d,querySelectorAll:()=>[],innerHTML:'',textContent:''};
global.window={innerWidth:1280,location:{search:''},addEventListener(){},matchMedia:()=>({matches:false,addEventListener(){}})};
global.document={documentElement:d,body:d,querySelector:()=>d,querySelectorAll:()=>[],
  getElementById:()=>d,createElement:()=>d,addEventListener(){}};
global.navigator={clipboard:{}};global.localStorage={getItem:()=>null,setItem(){},removeItem(){}};
global.fetch=()=>Promise.resolve({ok:false});global.URL={createObjectURL:()=>'',revokeObjectURL(){}};
global.requestAnimationFrame=(fn)=>fn();
"""

BASE = "An e-commerce API for a retail company."

_SETUP = """
lastRequirementText = %s;
lastRawSignals = detectSignals(lastRequirementText);
setAnalysis = () => {};
resetWhatIf();
""" % json.dumps(BASE)


def _text() -> str:
    return INDEX.read_text(encoding="utf-8")


def _js(body: str):
    return run_node_json(_STUBS + _text().split("<script>")[2].split("</script>")[0] + "\n" + _SETUP + body)


# ------------------------------------------------ the failure this feature most invites

@requires_node
def test_every_lever_has_a_stop_that_changes_the_recommendation():
    """A lever whose stops move nothing is decoration that implies the tool models something it
    does not. Asserted per lever rather than in aggregate, so one dead control cannot hide behind
    three live ones."""
    out = _js("""
      const res = {};
      WHATIF_LEVERS.forEach(l => {
        let best = 0;
        l.stops.forEach((s, i) => {
          if (i === 1) return;                       // the middle stop is "as written" by design
          resetWhatIf(); setWhatIfLever(l.id, i);
          best = Math.max(best, whatIfLastChanges.length);
        });
        res[l.id] = best;
      });
      console.log(JSON.stringify(res));
    """)
    dead = [k for k, v in out.items() if v == 0]
    assert not dead, f"these levers move no recommendation at any stop: {dead}"


@requires_node
def test_the_middle_stop_applies_no_override():
    """"As written" must mean exactly that — the requirement's own answer, not a third opinion."""
    out = _js("""
      setWhatIfLever('scale', 2);
      const forced = Object.keys(signalOverrides.levers).length;
      setWhatIfLever('scale', 1);
      console.log(JSON.stringify({forced, afterMiddle: Object.keys(signalOverrides.levers)}));
    """)
    assert out["forced"] > 0
    assert out["afterMiddle"] == [], "the middle stop left an override behind"


@requires_node
def test_moving_within_a_lever_clears_the_previous_stop():
    """Team Large sets largeTeam:true, smallTeam:false. Moving to Small must not leave a stale
    pairing from the other stop — the signals a lever owns are cleared before the new stop is
    applied."""
    out = _js("""
      setWhatIfLever('team', 2); const large = Object.assign({}, signalOverrides.levers);
      setWhatIfLever('team', 0); const small = Object.assign({}, signalOverrides.levers);
      console.log(JSON.stringify({large, small}));
    """)
    assert out["large"] == {"smallTeam": False, "largeTeam": True}
    assert out["small"] == {"smallTeam": True, "largeTeam": False}


@requires_node
def test_levers_compose_rather_than_replace_each_other():
    """Two levers set at once must both apply — otherwise this is a radio button, not a set of
    independent questions."""
    out = _js("""
      setWhatIfLever('scale', 2);
      setWhatIfLever('compliance', 2);
      console.log(JSON.stringify(signalOverrides.levers));
    """)
    assert out == {"highScale": True, "compliance": True}


@requires_node
def test_reset_returns_exactly_to_what_the_user_wrote():
    out = _js("""
      setWhatIfLever('scale', 2); setWhatIfLever('stage', 0);
      const beforeReset = computeRecommendations(applySignalOverrides(lastRawSignals));
      resetWhatIf();
      const afterReset = computeRecommendations(applySignalOverrides(lastRawSignals));
      const plain = computeRecommendations(lastRawSignals);
      const same = (x,y) => Object.keys(x).every(k => !x[k] || !x[k].v || x[k].v === (y[k]||{}).v);
      console.log(JSON.stringify({
        leversCleared: Object.keys(signalOverrides.levers).length,
        active: whatIfIsActive(),
        matchesPlain: same(afterReset, plain),
        actuallyDifferedBefore: !same(beforeReset, plain)
      }));
    """)
    assert out["leversCleared"] == 0 and out["active"] is False
    assert out["matchesPlain"], "reset did not restore the original recommendation"
    assert out["actuallyDifferedBefore"], "the levers under test changed nothing, so reset proves nothing"


# ------------------------------------------------------- not breaking what was already there

@requires_node
def test_levers_do_not_disturb_the_existing_exclusion_and_known_overrides():
    """`signalOverrides` already carried {excluded, known} for the inference toggles. Levers are a
    third key, not a replacement."""
    out = _js("""
      signalOverrides.excluded = {mysql: false};
      signalOverrides.known = {react: false};
      setWhatIfLever('scale', 2);
      console.log(JSON.stringify({
        excluded: signalOverrides.excluded, known: signalOverrides.known,
        levers: signalOverrides.levers
      }));
    """)
    assert out["excluded"] == {"mysql": False}
    assert out["known"] == {"react": False}
    assert out["levers"] == {"highScale": True}


@requires_node
def test_applysignaloverrides_applies_levers_by_assignment():
    """Exclusions are withdrawn by deletion; a lever STATES what the signal is for this
    exploration, which is a different act and needs assignment — including assigning false, which
    deletion cannot express."""
    out = _js("""
      setWhatIfLever('scale', 0);            // force highScale FALSE
      const s = applySignalOverrides(Object.assign({}, lastRawSignals, {highScale: true}));
      console.log(JSON.stringify(s.highScale));
    """)
    assert out is False, "a lever must be able to force a signal off, not only on"


def test_a_new_analysis_clears_the_levers():
    """Otherwise a lever set while exploring one requirement silently shapes the next one."""
    text = _text()
    # Matched to end-of-line rather than to the first "}" — the first brace belongs to
    # `excluded: {}`, so a lazy match captures almost nothing and reports a failure that is the
    # test's own, not the code's.
    m = re.search(r"if \(resetOverrides\) signalOverrides = (\{.*\});", text)
    assert m, "the reset site was not found"
    for key in ("excluded", "known", "levers"):
        assert key in m.group(1), f"resetOverrides does not clear {key}"


# ------------------------------------------------------------------------------- the UI

def test_the_controls_are_named_stops_not_sliders():
    """The scope's central design decision. 146 of 152 signals are boolean, so a slider would move
    nothing across most of its travel and then flip the stack in one step."""
    text = _text()
    m = re.search(r"const WHATIF_LEVERS = \[(.*?)\n\];", text, re.S)
    assert m, "WHATIF_LEVERS not found"
    block = m.group(1)
    assert 'type="range"' not in text, "a range input is a slider"
    for lever in re.findall(r"stops:\[(.*?)\] \}", block, re.S):
        assert lever.count("label:") >= 2, "a lever needs at least two named stops"


def test_every_lever_offers_an_as_written_stop_in_the_middle():
    out = re.findall(r"\{label:'As written', set:null\}", _text())
    levers = re.findall(r"\{ id:'\w+', label:", _text())
    assert len(out) == len(levers), "every lever needs an untouched 'as written' position"


def test_exploring_does_not_open_a_confirmation_dialog():
    """toggleInference's confirm() is right for permanently withdrawing an inference and wrong for
    a control someone is sweeping. Exploration and revision are different acts, and a modal per
    step is how a what-if tool becomes annoying enough to ignore."""
    m = re.search(r"function setWhatIfLever\(leverId, stopIndex\)\{(.*?)\n\}", _text(), re.S)
    assert m, "setWhatIfLever not found"
    assert "confirm(" not in m.group(1)


@requires_node
def test_a_lever_that_changes_nothing_says_so():
    """Silence would leave the reader hunting the page for a difference that is not there, and
    quietly teaches them the control is broken."""
    out = _js("""
      setWhatIfLever('scale', 0);      // already false for this requirement — a real no-op
      const html = renderWhatIfLeversHtml();
      console.log(JSON.stringify({
        changes: whatIfLastChanges.length,
        saysNothingChanged: html.includes('changed nothing')
      }));
    """)
    assert out["changes"] == 0
    assert out["saysNothingChanged"], "a no-op lever move must be reported, not left silent"


@requires_node
def test_the_effect_summary_names_the_cards_that_moved():
    out = _js("""
      setWhatIfLever('stage', 2);
      const html = renderWhatIfLeversHtml();
      console.log(JSON.stringify({
        count: whatIfLastChanges.length,
        namesACard: whatIfLastChanges.some(c => html.includes(c.card))
      }));
    """)
    assert out["count"] > 0 and out["namesACard"]


def test_the_panel_escapes_its_own_labels():
    m = re.search(r"function renderWhatIfLeversHtml\(\)\{(.*?)\n\}", _text(), re.S)
    assert m and "&amp;" in m.group(1), "no escaping in the lever renderer"
