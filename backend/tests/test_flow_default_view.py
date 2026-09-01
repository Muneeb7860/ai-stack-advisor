"""Flow View becomes the default; Cards becomes the alternative.

Step two of the agreed sequence, after the narrow-screen layout landed. The reasoning that
changed the call: once the stack cards collapsed to one-line summaries, the comparison stopped
being "rich cards vs. sparse canvas" — both views are now scan-first with detail on demand, and
only one of them also shows how the pieces connect.

Gated on the mobile fix arriving first. Before that a 20-node graph auto-fit to scale 0.25 on a
phone and every label was unreadable, so defaulting to it would have been worse than the boring
option.

The interesting part of this change is the bug it surfaced rather than the switch itself — see
test_a_brownfield_analysis_does_not_overwrite_the_view_preference.
"""
import re
import shutil
from pathlib import Path

import pytest

from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)


def _text() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _main_script() -> str:
    return _text().split("<script>")[2].split("</script>")[0]


_STUBS = r"""
const els = {};
function el(id){
  if(!els[id]) els[id] = { id, style:{display:''}, classList:{
      _s:new Set(), add(c){this._s.add(c);}, remove(c){this._s.delete(c);},
      toggle(c,f){ f===undefined ? (this._s.has(c)?this._s.delete(c):this._s.add(c)) : (f?this._s.add(c):this._s.delete(c)); },
      contains(c){return this._s.has(c);} },
    addEventListener(){}, setAttribute(){}, getAttribute:()=>null, appendChild(){}, removeChild(){},
    click(){}, focus(){}, querySelector:()=>null, querySelectorAll:()=>[], innerHTML:'', textContent:'', value:'' };
  return els[id];
}
global.window = { innerWidth:1280, location:{search:''}, addEventListener(){}, matchMedia:()=>({matches:false,addEventListener(){}}) };
global.document = { documentElement:el('html'), body:el('body'), querySelector:()=>el('q'),
  querySelectorAll:()=>[], getElementById:(id)=>el(id), createElement:()=>el('new'), addEventListener(){} };
global.navigator = { clipboard:{} };
global.localStorage = { getItem:()=>null, setItem(){}, removeItem(){} };
global.fetch = () => Promise.resolve({ ok:false });
global.URL = { createObjectURL:()=>'', revokeObjectURL(){} };
global.requestAnimationFrame = (fn) => fn();
"""


def _js(body: str):
    return run_node_json(_STUBS + _main_script() + "\n" + body)


# ------------------------------------------------------------------------------ the switch

def test_flow_is_the_default_view():
    assert "let currentView = 'flow';" in _text()


def test_the_toggle_buttons_start_in_a_state_that_matches_the_default():
    """If the buttons don't match, the control lies about which view is showing before the user
    has touched anything."""
    text = _text()
    assert 'id="viewFlowBtn" class="active icon-btn"' in text
    assert 'id="viewCardsBtn" class="icon-btn"' in text


# ------------------------- the bug the switch surfaced: a forced view overwrote the preference

@requires_node
def test_a_brownfield_analysis_does_not_overwrite_the_view_preference():
    """brownfieldAiOnly forces Cards because Flow renders infra topology that mode deliberately
    suppresses. That force used to go through setView('cards'), which assigns currentView — so a
    single brownfield analysis permanently stranded the user on Cards for every later analysis.

    Invisible while Cards was the default; a real leak the moment it wasn't. Found by running the
    two analyses back to back in a browser, not by reading the code."""
    out = _js("""
      const before = currentView;
      setView('cards', false);          // the per-analysis force
      const during = currentView;       // preference must be untouched
      setView('flow');                  // a real user choice
      console.log(JSON.stringify({before, during, after: currentView}));
    """)
    assert out["before"] == "flow"
    assert out["during"] == "flow", "a forced view must not overwrite the standing preference"
    assert out["after"] == "flow"


@requires_node
def test_an_explicit_user_choice_is_remembered():
    """The flag must not disable the normal path — clicking Cards has to stick."""
    out = _js("""
      setView('cards');
      console.log(JSON.stringify(currentView));
    """)
    assert out == "cards"


def test_the_forced_view_call_passes_the_no_remember_flag():
    assert "if (s.brownfieldAiOnly) setView('cards', false);" in _text()


def test_the_render_honours_the_force_without_persisting_it():
    text = _text()
    assert "setView(s.brownfieldAiOnly ? 'cards' : currentView, !s.brownfieldAiOnly);" in text


def test_resize_reacts_to_the_displayed_view_not_the_stored_preference():
    """Those two can now differ (brownfield displays Cards while the preference stays Flow), so
    keying the resize re-fit off currentView would run flowFit against a hidden canvas."""
    text = _text()
    m = re.search(r"window\.addEventListener\('resize', \(\) => \{(.*?)\n  \}\);", text, re.S)
    assert m, "resize handler not found"
    body = m.group(1)
    assert "currentView === 'flow'" not in body
    assert "flowWrap" in body and "display === 'block'" in body


# --------------------------------------------------------------------------- unchanged paths

def test_the_view_toggle_is_still_hidden_for_brownfield_ai_only():
    """Offering a toggle to a view that mode suppresses would be offering a view of exactly the
    thing it removed."""
    assert "document.getElementById('viewToggle').style.display = s.brownfieldAiOnly ? 'none' : 'flex';" in _text()


def test_cards_remain_reachable_as_the_alternative():
    text = _text()
    assert "onclick=\"setView('cards')\"" in text
    assert "onclick=\"setView('flow')\"" in text
