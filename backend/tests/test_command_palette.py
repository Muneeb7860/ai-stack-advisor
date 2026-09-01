"""Command palette (⌘K) and keyboard-first navigation.

The interface audit scored keyboard 3/10 — the weakest dimension by a wide margin, with only
Enter, Space and Escape handled anywhere and zero meta/ctrl shortcuts. This closes that gap.

Scope note, stated because it was a deliberate cut: the plan this came from also proposed chord
sequences (G→F to toggle view, J→D to jump to Database). Those are a second interaction model to
learn, teach and test, and every action they'd reach is already one ⌘K away. Skipped on purpose,
not overlooked — if chords are wanted later they should be their own change with their own
timeout/abort semantics.

Commands are built from the LIVE DOM on every open rather than a static list, so the palette
always reflects the current analysis: sections suppressed for a given scope
(see computeVisibleSections) are absent for free, and picks come from the cards that actually
rendered.
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
const dummyEl = { style:{}, classList:{add(){},remove(){},toggle(){},contains:()=>false}, addEventListener(){},
  setAttribute(){}, getAttribute:()=>null, appendChild(){}, removeChild(){}, click(){}, focus(){},
  querySelector:()=>null, querySelectorAll:()=>[], innerHTML:'', textContent:'', value:'' };
global.window = { innerWidth:1280, location:{search:''}, addEventListener(){}, matchMedia:()=>({matches:false,addEventListener(){}}) };
global.document = { documentElement:dummyEl, body:dummyEl, querySelector:()=>null,
  querySelectorAll:()=>[], getElementById:()=>dummyEl, createElement:()=>dummyEl, addEventListener(){} };
global.navigator = { clipboard:{} };
global.localStorage = { getItem:()=>null, setItem(){}, removeItem(){} };
global.fetch = () => Promise.resolve({ ok:false });
global.URL = { createObjectURL:()=>'', revokeObjectURL(){} };
global.requestAnimationFrame = (fn) => fn();
"""


def _js(body: str):
    return run_node_json(_STUBS + _main_script() + "\n" + body)


# ------------------------------------------------------------------------ matching behaviour

@requires_node
def test_search_is_subsequence_not_substring():
    """What makes a palette feel keyboard-first: you type what you remember, not an exact
    prefix. "expsvg" has to find "Export diagram as SVG"."""
    out = _js("""
      console.log(JSON.stringify([
        cmdkMatches('Export diagram as SVG', 'expsvg'),
        cmdkMatches('Export diagram as SVG', 'svg'),
        cmdkMatches('Export diagram as SVG', 'EXPORT'),
        cmdkMatches('Export diagram as SVG', 'zzz'),
        cmdkMatches('anything', '')
      ]));
    """)
    assert out == [True, True, True, False, True]


@requires_node
def test_subsequence_respects_character_order():
    """A plain "contains every character" check would match nonsense — order is what keeps the
    results relevant."""
    out = _js("console.log(JSON.stringify([cmdkMatches('Export SVG','gvs'), cmdkMatches('Export SVG','svg')]));")
    assert out == [False, True]


# ---------------------------------------------------------------------- keyboard navigation

@requires_node
def test_arrow_navigation_wraps_in_both_directions():
    """A palette you can only walk one way is a palette you overshoot and have to reopen."""
    out = _js("""
      cmdkFiltered = [{label:'a'},{label:'b'},{label:'c'}];
      cmdkIndex = 0;
      cmdkRender = () => {};                 // DOM-free: this test is about the cursor maths
      cmdkMove(-1); const wrappedUp = cmdkIndex;
      cmdkMove(1);  const backToZero = cmdkIndex;
      cmdkMove(1); cmdkMove(1); cmdkMove(1); const wrappedDown = cmdkIndex;
      console.log(JSON.stringify({wrappedUp, backToZero, wrappedDown}));
    """)
    assert out["wrappedUp"] == 2, "up from the first item must wrap to the last"
    assert out["backToZero"] == 0
    assert out["wrappedDown"] == 0, "down from the last item must wrap to the first"


@requires_node
def test_move_is_safe_with_no_matches():
    """Typing a query that matches nothing must not throw on the next arrow key."""
    out = _js("""
      cmdkFiltered = []; cmdkIndex = 0; cmdkRender = () => {};
      cmdkMove(1); cmdkMove(-1);
      console.log(JSON.stringify(cmdkIndex));
    """)
    assert out == 0


@requires_node
def test_running_a_command_closes_the_palette_before_the_action():
    """Order matters: an action that moves focus or scrolls must not be fighting a modal that is
    still open on top of it."""
    out = _js("""
      const order = [];
      cmdkFiltered = [{label:'x', run:() => order.push('ran')}];
      cmdkIndex = 0;
      closeCommandPalette = () => order.push('closed');
      cmdkRun(0);
      console.log(JSON.stringify(order));
    """)
    assert out == ["closed", "ran"]


@requires_node
def test_a_failing_command_does_not_break_the_palette():
    """A single broken action shouldn't take down the whole keyboard path."""
    out = _js("""
      cmdkFiltered = [{label:'boom', run:() => { throw new Error('nope'); }}];
      cmdkIndex = 0;
      closeCommandPalette = () => {};
      global.console.error = () => {};
      let threw = false;
      try { cmdkRun(0); } catch (e) { threw = true; }
      console.log(JSON.stringify(threw));
    """)
    assert out is False


@requires_node
def test_running_an_out_of_range_index_is_a_no_op():
    out = _js("""
      cmdkFiltered = []; closeCommandPalette = () => { throw new Error('should not close'); };
      let threw = false;
      try { cmdkRun(5); } catch (e) { threw = true; }
      console.log(JSON.stringify(threw));
    """)
    assert out is False


# ------------------------------------------------------------------------------ DOM wiring

def test_the_palette_binds_meta_and_ctrl_k():
    """The audit's specific finding was zero meta/ctrl handlers anywhere in the file."""
    text = _text()
    assert "(e.metaKey || e.ctrlKey) && k === 'k'" in text
    assert "openCommandPalette()" in text


def test_escape_closes_only_the_palette_when_it_is_open():
    """The pre-existing global Escape tears down every drawer, modal and popover. With the
    palette open, Escape should close the palette and stop there — not also dismiss whatever the
    user had open behind it."""
    text = _text()
    m = re.search(r"if \(isCommandPaletteOpen\(\)\) \{(.*?)\n    return;", text, re.S)
    assert m, "the palette's own key-handling block was not found"
    body = m.group(1)
    assert "e.stopPropagation()" in body, "must not fall through to the global Escape teardown"
    assert "closeCommandPalette()" in body


def test_slash_switches_to_the_requirement_screen_not_just_focus():
    """The textarea exists in the DOM at all times but is hidden unless its screen is active, so
    a bare focus() silently did nothing from anywhere else — which is most of the time. Found by
    pressing the key from the mode screen rather than assuming presence meant focusable."""
    text = _text()
    m = re.search(r"if \(e\.key === '/'.*?\n  \}", text, re.S)
    assert m, "the slash handler was not found"
    body = m.group(0)
    assert "offsetParent === null" in body, "must detect the hidden case"
    assert "startFreetext()" in body


def test_slash_is_inert_while_the_user_is_typing():
    """Otherwise it swallows a literal slash in a URL, a path or a regex."""
    text = _text()
    m = re.search(r"if \(e\.key === '/'.*?\n  \}", text, re.S)
    body = m.group(0)
    assert "'input'" in body and "'textarea'" in body and "isContentEditable" in body


def test_commands_are_built_from_the_live_dom():
    """A hardcoded list would drift the moment a section is suppressed for a given scope or a new
    card is added."""
    text = _text()
    m = re.search(r"function cmdkBuildItems\(\)\{(.*?)\n\}", text, re.S)
    assert m, "cmdkBuildItems not found"
    body = m.group(1)
    assert "#sideNav a" in body, "sections must come from the rendered nav"
    assert "#stack .stack-card" in body, "picks must come from the rendered cards"


def test_analysis_only_commands_are_hidden_before_an_analysis_exists():
    """Offering "Export diagram as SVG" on the landing screen is offering a command that can only
    fail."""
    text = _text()
    m = re.search(r"function cmdkBuildItems\(\)\{(.*?)\n\}", text, re.S)
    body = m.group(1)
    assert "analysisOnScreen" in body
    assert "if (analysisOnScreen) {" in body


def test_the_palette_is_an_accessible_dialog():
    text = _text()
    assert 'role="dialog"' in text and 'aria-modal="true"' in text
    assert 'role="listbox"' in text and 'role="option"' in text
    assert "aria-activedescendant" in text, "screen readers need the active option announced"


def test_focus_is_restored_when_the_palette_closes():
    """Escape must not strand focus on a hidden element."""
    text = _text()
    assert "cmdkLastFocus" in text
    m = re.search(r"function closeCommandPalette\(\)\{(.*?)\n\}", text, re.S)
    assert m and "cmdkLastFocus" in m.group(1)


def test_the_selected_item_is_visually_distinguishable():
    """Selection is driven by the keyboard, so it must be visible without a pointer hovering —
    it is the only affordance telling you what Enter will run."""
    assert re.search(r'\.cmdk-item\[aria-selected="true"\]\{[^}]*background', _text())
