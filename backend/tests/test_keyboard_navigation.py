"""Keyboard navigation: the skip link, the heading outline, and the modal focus trap.

Written after the fact, and that is the point. The change these guard
(205ec2f, "Make the page navigable without a mouse") shipped with no coverage —
`test_ui_ux_accessibility_fixes.py` predates it and passes identically with and
without it, so the suite would not have noticed any of this breaking. The seven
properties below were verified by hand in a browser at commit time; these tests
are what turns "verified once" into "stays verified".

A focus trap is a good candidate for a regression that nobody notices: it fails
open. Tab simply escapes to the page behind the dialog, everything still looks
right, and only a keyboard user finds out. So the behavioural tests below drive
the real `enableModalFocusTrap`/`disableModalFocusTrap` under a DOM stub that
actually models focus, rather than asserting the functions exist.
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


def _body() -> str:
    return _text().split("<body>", 1)[1]


# --------------------------------------------------------------- skip link

def test_the_skip_link_is_the_first_focusable_thing_in_the_body():
    """A skip link that is not first is not a skip link — the user tabs into the header before
    reaching it, which is the exact thing it exists to avoid."""
    body = _body()
    focusable = re.search(
        r"<a\s[^>]*href=|<(?:button|input|select|textarea)\b|tabindex=[\"'](?!-1)", body, re.I
    )
    assert focusable, "no focusable element found in <body> at all"
    # Scoped to the matched TAG, not a window of following characters: a 200-char window happily
    # contained the skip link sitting immediately after an interloping <button>, so the mutation
    # that put a focusable element in front of it passed.
    tag = body[focusable.start():body.index(">", focusable.start()) + 1]
    assert 'class="skip-link"' in tag, (
        f"the first focusable element in <body> is not the skip link, it is: {tag}"
    )


def test_the_skip_link_points_at_a_landmark_that_exists():
    """A skip link targeting a missing id is worse than none: the browser moves focus nowhere and
    the user has no way to tell it did nothing."""
    m = re.search(r'<a\s+href="#([\w-]+)"\s+class="skip-link"', _text())
    assert m, "skip link not found"
    target = m.group(1)
    assert re.search(rf'<main\s[^>]*id="{re.escape(target)}"', _text()), (
        f'skip link targets #{target}, but no <main id="{target}"> exists'
    )


def test_the_skip_link_is_offscreen_until_focused():
    """Visible at rest it is clutter for the 99% who never use it; permanently hidden with
    `display:none` it is unreachable for the 1% who do. Off-screen plus a :focus rule is the
    only arrangement that serves both."""
    css = _text()
    at_rest = re.search(r"\.skip-link\{([^}]*)\}", css)
    on_focus = re.search(r"\.skip-link:focus\{([^}]*)\}", css)
    assert at_rest and on_focus, "the skip-link needs both a resting and a :focus rule"
    assert "display:none" not in at_rest.group(1).replace(" ", ""), (
        "display:none removes the skip link from the tab order entirely"
    )
    assert re.search(r"left:\s*-\d+", at_rest.group(1)), "expected the resting rule to park it off-screen"
    assert "position:fixed" in on_focus.group(1).replace(" ", "")


# ---------------------------------------------------------- heading outline

def test_there_is_exactly_one_h1_and_one_main_landmark():
    """Four competing <h1>s (the modals each had one) give a screen reader four page titles and no
    outline. Demoting them to <h2> only helps if exactly one survives."""
    text = _text()
    assert len(re.findall(r"<h1[\s>]", text)) == 1, "expected exactly one <h1> on the page"
    assert len(re.findall(r"<main[\s>]", text)) == 1, "expected exactly one <main> landmark"


def test_every_dialog_that_opens_also_closes_its_trap():
    """An enable without a matching disable leaks a keydown handler per open and strands focus
    inside a dialog the user already dismissed."""
    src = _text()
    assert src.count("enableModalFocusTrap(") == src.count("disableModalFocusTrap("), (
        f"{src.count('enableModalFocusTrap(')} enable call(s) against "
        f"{src.count('disableModalFocusTrap(')} disable call(s) — they must pair"
    )
    # Definition + one call site per dialog (glide panel, custom-tech modal, MCP modal).
    assert src.count("enableModalFocusTrap(") == 4


# ------------------------------------------------------------- focus trap

# A DOM stub that models the one thing that matters here: which element has focus. The real
# functions run against it unchanged — nothing about the trap is reimplemented in the test.
_FOCUS_DOM = r"""
function mkEl(tag, attrs){
  return {
    tagName: tag.toUpperCase(), attrs: attrs || {}, offsetParent: {}, _l: {},
    hasAttribute(a){ return Object.prototype.hasOwnProperty.call(this.attrs, a); },
    getAttribute(a){ return this.attrs[a] === undefined ? null : this.attrs[a]; },
    focus(){ document.activeElement = this; },
    addEventListener(t, h){ (this._l[t] = this._l[t] || []).push(h); },
    removeEventListener(t, h){ const l = this._l[t] || []; const i = l.indexOf(h); if (i >= 0) l.splice(i, 1); },
    listeners(t){ return (this._l[t] || []).length; },
  };
}
function mkModal(kids){
  const m = mkEl('div');
  m.querySelectorAll = () => kids;
  m.contains = (el) => el === m || kids.indexOf(el) >= 0;
  // Dispatches straight to the registered handlers, so a removed handler really is gone.
  m.press = (key, shift) => {
    let prevented = false;
    const ev = { key: key, shiftKey: !!shift, preventDefault(){ prevented = true; } };
    for (const h of (m._l.keydown || []).slice()) h(ev);
    return prevented;
  };
  return m;
}
const wait = (ms) => new Promise(r => setTimeout(r, ms));
"""


def _js(body: str):
    stubs = r"""
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
    main = _text().split("<script>")[2].split("</script>")[0]
    # The focus-modelling document replaces the load-time stub AFTER the script has run: the trap
    # functions resolve `document` at call time, so they see this one.
    #
    # The body is wrapped in an async IIFE rather than using top-level await: a `.js` file with
    # top-level await fails to parse as CommonJS, so Node 22 retries it as an ES module — and ESM
    # is strict mode, where the stubs' `global.navigator = ...` throws instead of being ignored.
    # The failure surfaces as a navigator TypeError with no mention of await, which is a long way
    # from the cause.
    return run_node_json(stubs + main + "\n" + _FOCUS_DOM + "\n(async () => {\n" + body + "\n})();")


_SETUP = """
const opener = mkEl('button');
const a = mkEl('button'), b = mkEl('button'), c = mkEl('button');
const modal = mkModal([a, b, c]);
global.document = { activeElement: opener };
document.activeElement = opener;
"""


@requires_node
def test_opening_a_dialog_moves_focus_into_it():
    out = _js(_SETUP + """
        enableModalFocusTrap(modal);
        const immediately = document.activeElement === opener;
        await wait(80);
        console.log(JSON.stringify({
          focusStillOutsideBeforeTimer: immediately,
          focusedFirstChild: document.activeElement === a,
          handlerRegistered: modal.listeners('keydown'),
        }));
    """)
    assert out["focusedFirstChild"], "focus never moved into the dialog"
    assert out["handlerRegistered"] == 1


@requires_node
def test_tab_at_the_last_element_wraps_to_the_first_instead_of_escaping():
    """The failure this catches is silent: without the wrap, Tab lands on the page behind the
    dialog and everything still looks correct on screen."""
    out = _js(_SETUP + """
        enableModalFocusTrap(modal);
        await wait(80);
        c.focus();
        const prevented = modal.press('Tab', false);
        console.log(JSON.stringify({prevented, wrappedToFirst: document.activeElement === a}));
    """)
    assert out["prevented"], "Tab was allowed through to the browser's default handling"
    assert out["wrappedToFirst"]


@requires_node
def test_shift_tab_at_the_first_element_wraps_to_the_last():
    out = _js(_SETUP + """
        enableModalFocusTrap(modal);
        await wait(80);
        a.focus();
        const prevented = modal.press('Tab', true);
        console.log(JSON.stringify({prevented, wrappedToLast: document.activeElement === c}));
    """)
    assert out["prevented"]
    assert out["wrappedToLast"]


@requires_node
def test_focus_that_has_already_escaped_is_pulled_back_in():
    """Focus can land outside the dialog without a Tab the trap saw — a click, a programmatic
    focus() elsewhere. The next Tab has to recover rather than continue from wherever it is."""
    out = _js(_SETUP + """
        enableModalFocusTrap(modal);
        await wait(80);
        opener.focus();                       // focus escaped behind the dialog
        modal.press('Tab', false);
        const forward = document.activeElement === a;
        opener.focus();
        modal.press('Tab', true);
        console.log(JSON.stringify({forward, backward: document.activeElement === c}));
    """)
    assert out["forward"], "Tab from outside the dialog did not return focus to it"
    assert out["backward"], "Shift+Tab from outside the dialog did not return focus to it"


@requires_node
def test_an_ordinary_keystroke_is_not_intercepted():
    """The trap must only own Tab. Swallowing anything else would break typing in a dialog that
    contains an input — the MCP and custom-technology modals both do."""
    out = _js(_SETUP + """
        enableModalFocusTrap(modal);
        await wait(80);
        c.focus();
        const prevented = modal.press('a', false);
        console.log(JSON.stringify({prevented, focusUnmoved: document.activeElement === c}));
    """)
    assert out["prevented"] is False
    assert out["focusUnmoved"]


@requires_node
def test_closing_removes_the_handler_and_returns_focus_to_the_opener():
    """Two separate leaks. A handler left attached fires again on the next open (once per previous
    open); focus left inside a dismissed dialog leaves the keyboard user nowhere."""
    out = _js(_SETUP + """
        enableModalFocusTrap(modal);
        await wait(80);
        disableModalFocusTrap(modal);
        const afterClose = modal.listeners('keydown');
        // Re-open and close twice more: handlers must not accumulate.
        enableModalFocusTrap(modal); await wait(60); disableModalFocusTrap(modal);
        enableModalFocusTrap(modal); await wait(60); disableModalFocusTrap(modal);
        console.log(JSON.stringify({
          handlersAfterClose: afterClose,
          handlersAfterThreeCycles: modal.listeners('keydown'),
          focusRestored: document.activeElement === opener,
        }));
    """)
    assert out["handlersAfterClose"] == 0
    assert out["handlersAfterThreeCycles"] == 0, "keydown handlers accumulated across open/close cycles"
    assert out["focusRestored"], "focus was not returned to the element that opened the dialog"


@requires_node
def test_a_dialog_with_nothing_focusable_swallows_tab_rather_than_leaking():
    """Every child hidden (`offsetParent === null`) is a real state — the glide panel renders its
    contents after opening. Tab must not fall through to the page behind in that window."""
    out = _js("""
        const opener = mkEl('button');
        const hidden = mkEl('button'); hidden.offsetParent = null;
        const modal = mkModal([hidden]);
        global.document = { activeElement: opener };
        enableModalFocusTrap(modal);
        await wait(80);
        const prevented = modal.press('Tab', false);
        console.log(JSON.stringify({prevented, focusUnchanged: document.activeElement === opener}));
    """)
    assert out["prevented"], "Tab leaked out of a dialog with no focusable children"
    assert out["focusUnchanged"]


@requires_node
def test_a_disabled_control_is_not_a_tab_stop():
    out = _js("""
        const opener = mkEl('button');
        const a = mkEl('button'), off = mkEl('button', {disabled: ''}), c = mkEl('button');
        const modal = mkModal([a, off, c]);
        global.document = { activeElement: opener };
        enableModalFocusTrap(modal);
        await wait(80);
        c.focus();
        modal.press('Tab', false);
        const first = document.activeElement === a;
        a.focus();
        modal.press('Tab', true);
        console.log(JSON.stringify({first, last: document.activeElement === c}));
    """)
    assert out["first"]
    assert out["last"], "a disabled control was treated as the last tab stop"
