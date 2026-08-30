"""Regression tests for 3 UI items verified as real gaps during a manual QA sweep and scoped
for this pass (docs/manual-qa-test-matrix.csv's follow-up items #8, #10, #11 — #9 was judged
already partially addressed by earlier work, and #12 was judged not a real gap on inspection,
so neither is built here):

- #8: a bad/expired Anthropic API key left the user stuck — renderRefineKeyPrompt() only ever
  shows when no key is saved at all, so once ANY key (even a bad one) is saved, nothing in the
  UI could clear it short of a page refresh.
- #10: the sidebar reserves 208px of width even when its own content (This Analysis, Export/
  Share, History) is empty, which is exactly the state on a fresh input screen.
- #11: every signal chip (stated, excluded, known/assumed, why-signal) used one identical flat
  style, making the signals row hard to scan by category at a glance.
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


def _text():
    return INDEX_HTML.read_text(encoding="utf-8")


def _main_script() -> str:
    return INDEX_HTML.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]


_STUBS = r"""
function makeEl(tag){
  return {
    tag, dataset:{}, className:'', innerHTML:'', style:{}, children:[], value:'', textContent:'',
    classList:{
      _set: new Set(),
      add(c){ this._set.add(c); },
      remove(c){ this._set.delete(c); },
      toggle(c, force){
        const on = force === undefined ? !this._set.has(c) : !!force;
        if (on) this._set.add(c); else this._set.delete(c);
        return on;
      },
      contains(c){ return this._set.has(c); },
    },
    appendChild(child){ this.children.push(child); },
    insertAdjacentHTML(pos, html){ this.innerHTML += html; },
    querySelector:()=>null, querySelectorAll:()=>[],
    addEventListener(){}, setAttribute(){}, getAttribute:()=>null, scrollIntoView(){},
  };
}
const sidebarEl = makeEl('aside');
sidebarEl.classList.add('app-sidebar'); // mirrors the static HTML's default class
const byId = { sidebarThisAnalysisBtn: makeEl('button'), mobileThisAnalysisBtn: makeEl('button') };

global.window = { location:{search:''}, addEventListener(){}, matchMedia:()=>({matches:false,addEventListener(){}}) };
global.document = {
  documentElement: makeEl('html'), body: makeEl('body'),
  createElement: (tag) => makeEl(tag),
  getElementById: (id) => { if (!byId[id]) byId[id] = makeEl('div'); return byId[id]; },
  querySelector: (sel) => sel === '.app-sidebar' ? sidebarEl : null,
  querySelectorAll: () => [],
  addEventListener(){},
};
global.navigator = { clipboard:{} };
const _session = {};
global.sessionStorage = {
  getItem: (k) => (k in _session ? _session[k] : null),
  setItem: (k, v) => { _session[k] = String(v); },
  removeItem: (k) => { delete _session[k]; },
};
global.localStorage = { getItem:()=>null, setItem(){}, removeItem(){} };
global.fetch = () => Promise.resolve({ ok:false });
global.URL = { createObjectURL:()=>'', revokeObjectURL(){} };
"""


def _js(body: str):
    return run_node_json(_STUBS + _main_script() + "\n" + body)


# --------------------------------------------------------------------------- #8 static checks

def test_prompt_to_update_api_key_function_exists():
    text = _text()
    assert "function promptToUpdateApiKey(cardKey, intent){" in text
    body_start = text.index("function promptToUpdateApiKey(cardKey, intent){")
    body_end = text.index("\n}\n", body_start)
    body = text[body_start:body_end]
    assert "renderRefineKeyPrompt(cardKey" in body
    # Deliberately does NOT clear the stored key itself (found in review): setApiKey()
    # overwrites unconditionally once a new key is submitted, so clearing here first would
    # only cost something -- a click prompted by an unrelated, transient error (a network
    # blip, a rate limit) would otherwise silently discard a perfectly good key.
    assert "sessionStorage.removeItem" not in body


def test_refine_error_path_offers_the_retry_button():
    text = _text()
    body_start = text.index("async function onRefineClick(cardKey, btnEl){")
    body_end = text.index("\n}\n", body_start)
    body = text[body_start:body_end]
    assert "promptToUpdateApiKey('${cardKey}','refine')" in body


def test_ask_error_path_offers_the_retry_button():
    text = _text()
    body_start = text.index("async function onAskClick(cardKey){")
    body_end = text.index("\n}\n", body_start)
    body = text[body_start:body_end]
    assert "promptToUpdateApiKey('${cardKey}','ask')" in body


# --------------------------------------------------------------------------- #8 behavior

@requires_node
def test_prompt_to_update_api_key_shows_the_entry_prompt():
    out = _js("""
      const before = document.getElementById('refineResult-stack-0').innerHTML.includes('apiKeyInput-stack-0');
      promptToUpdateApiKey('stack-0', 'refine');
      const html = document.getElementById('refineResult-stack-0').innerHTML;
      console.log(JSON.stringify({
        shownBefore: before,
        promptShown: html.includes('apiKeyInput-stack-0'),
        intent: html.includes('data-intent="refine"'),
      }));
    """)
    assert out == {"shownBefore": False, "promptShown": True, "intent": True}


@requires_node
def test_prompt_to_update_api_key_does_not_clear_a_good_key_the_user_never_meant_to_lose():
    """The whole point of the review-driven behavior change: clicking the recovery button
    because of an unrelated, transient error must not silently discard a perfectly good key."""
    out = _js("""
      sessionStorage.setItem('anthropic_api_key', 'a-perfectly-good-key');
      promptToUpdateApiKey('stack-0', 'refine');
      console.log(JSON.stringify({ keyStillThere: sessionStorage.getItem('anthropic_api_key') === 'a-perfectly-good-key' }));
    """)
    assert out == {"keyStillThere": True}


@requires_node
def test_prompt_to_update_api_key_preserves_the_ask_intent():
    """Re-saving the key after an ask-flow error must resume asking, not refining — the intent
    passed through here is what onSaveKeyClick branches on."""
    out = _js("""
      promptToUpdateApiKey('stack-0', 'ask');
      console.log(JSON.stringify({
        intent: document.getElementById('refineResult-stack-0').innerHTML.includes('data-intent="ask"'),
      }));
    """)
    assert out == {"intent": True}


# --------------------------------------------------------------------------- #10 static checks

def test_sidebar_focused_input_css_exists():
    text = _text()
    assert re.search(r"\.app-sidebar\.sidebar-focused-input\{[^}]*width:168px", text)


def test_sidebar_focused_input_rule_is_guarded_above_the_mobile_breakpoint():
    """Found in review, not the original implementation: an UNGUARDED
    `.app-sidebar.sidebar-focused-input{width:168px}` has HIGHER specificity (two classes) than
    the existing 860px breakpoint's `.app-sidebar{width:0}` collapse rule (one class) —
    specificity wins regardless of media-query nesting or source order. Since
    sidebar-focused-input is present by default in the static HTML, this made the sidebar
    render at 168px on a fresh MOBILE page load too, instead of collapsing to the bottom nav —
    reproduced live by actually resizing to a mobile viewport, not assumed safe from the CSS.
    The rule must sit inside a min-width media query matching (861px, one above) the existing
    860px mobile breakpoint so it never applies below it at all."""
    text = _text()
    m = re.search(
        r"@media \(min-width:861px\)\{\s*\.app-sidebar\.sidebar-focused-input\{[^}]*width:168px[^}]*\}\s*\}",
        text,
    )
    assert m, "the focused-input rule must be wrapped in @media (min-width:861px)"


def test_sidebar_starts_with_the_focused_class_in_static_html():
    text = _text()
    assert re.search(r'<aside class="app-sidebar sidebar-focused-input">', text)


def test_set_sidebar_this_analysis_visible_toggles_the_focus_class():
    text = _text()
    body_start = text.index("function setSidebarThisAnalysisVisible(visible){")
    body_end = text.index("\n}\n", body_start)
    body = text[body_start:body_end]
    assert "classList.toggle('sidebar-focused-input', !visible)" in body


# --------------------------------------------------------------------------- #10 behavior

@requires_node
def test_sidebar_unfocuses_when_an_analysis_becomes_visible_and_refocuses_when_cleared():
    out = _js("""
      setSidebarThisAnalysisVisible(true);
      const afterTrue = sidebarEl.classList.contains('sidebar-focused-input');
      setSidebarThisAnalysisVisible(false);
      const afterFalse = sidebarEl.classList.contains('sidebar-focused-input');
      console.log(JSON.stringify({ afterTrue, afterFalse }));
    """)
    assert out == {"afterTrue": False, "afterFalse": True}


# --------------------------------------------------------------------------- #11 static checks

@pytest.mark.parametrize("selector", [".sig-stated", ".sig-known", ".sig-excluded"])
def test_chip_category_css_rule_exists(selector):
    text = _text()
    escaped = re.escape(selector)
    assert re.search(rf"{escaped}\{{[^}}]*border-left", text), f"{selector} rule not found"


def test_why_sig_reuses_its_own_pre_existing_treatment_not_a_duplicate_rule():
    """.why-sig already had its own full border+tint+text-color rule from an earlier pass
    (near .why-signals) — this pass must not add a second .why-sig{} rule whose properties
    would just be shadowed by the existing one (same specificity, source order decides)."""
    text = _text()
    assert len(re.findall(r"\.why-sig\{", text)) == 1, "exactly one .why-sig rule must exist"


def test_active_signal_chips_use_the_stated_class():
    text = _text()
    assert '<span class="sig sig-stated">${x}</span>' in text


def test_render_chip_row_tags_chips_with_their_kind():
    """renderChipRow() is reused for BOTH 'excluded' and 'known' rows — the class must be
    templated on `kind`, not hardcoded to one or the other, or the two rows would render
    identically colored."""
    text = _text()
    body_start = text.index("const renderChipRow = (kind, label, title) => {")
    body_end = text.index("\n  };\n", body_start)
    body = text[body_start:body_end]
    assert body.count("sig-${kind}") >= 3, "expected the label chip and both branch chips to use sig-${kind}"
    assert "sig-excluded" not in body and "sig-known" not in body, (
        "must template on kind, not hardcode one specific category inside the shared function"
    )
