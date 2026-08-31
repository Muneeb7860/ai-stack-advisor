"""
Regression tests for 8 accessibility/interaction fixes found by an external
UI/UX browser audit (pasted into the session, then independently re-verified
against the actual code before any fix was applied — see PR description).
This precedes Phase 3 of the Enterprise v2.0 shell plan.

Plain string/regex checks against index.html, matching every other migration
test file in this suite — no Node/browser needed.
"""
import re
from pathlib import Path

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"


def _text():
    return INDEX_HTML.read_text(encoding="utf-8")


# ---------------------------------------------------------- 1. sidebar tooltips

def test_sidebar_new_analysis_and_this_analysis_have_title_and_aria_label():
    text = _text()
    m = re.search(r'<button type="button" class="app-sidebar-item" onclick="backToMode\(\)"([^>]*)>', text)
    assert m and 'title="' in m.group(1) and 'aria-label="' in m.group(1)
    m2 = re.search(r'<button type="button" class="app-sidebar-item" id="sidebarThisAnalysisBtn"([^>]*)>', text)
    assert m2 and 'title="' in m2.group(1) and 'aria-label="' in m2.group(1)


def test_export_and_share_buttons_have_title_and_aria_label():
    text = _text()
    m = re.search(r'<button class="share-btn icon-btn" id="exportMainBtn"([^>]*)>', text)
    assert m and 'title="' in m.group(1) and 'aria-label="' in m.group(1)
    m2 = re.search(r'<button class="share-btn icon-btn" id="shareBtn"([^>]*)>', text)
    assert m2 and 'title="' in m2.group(1) and 'aria-label="' in m2.group(1)


# ---------------------------------------------------------- 2. mode-card keyboard

def test_mode_cards_are_keyboard_operable():
    """4, not 3, as of the Harness Readiness audit mode (docs/harness-engineering/
    HARNESS_READINESS_SCOPE.md) — the count itself isn't the point of this test, keyboard
    operability of whichever cards exist is."""
    text = _text()
    cards = re.findall(r'<div class="mode-card"[^>]*>', text)
    assert len(cards) == 4
    for c in cards:
        assert 'tabindex="0"' in c
        assert 'role="button"' in c
        assert 'onkeydown="' in c


# ---------------------------------------------------------- 3. modal backdrop click

def test_custom_tech_modal_backdrop_click_dismisses():
    text = _text()
    m = re.search(r'<div id="customTechModal" class="custom-modal-backdrop"[^>]*>', text)
    assert m, "customTechModal opening tag not found"
    assert "onclick=\"if(event.target===this) closeCustomTechModal();\"" in m.group(0)


# ---------------------------------------------------------- 4. global Escape

def test_global_escape_handler_closes_glide_panel_modal_and_popover():
    text = _text()
    m = re.search(r"window\.addEventListener\('keydown', \(e\) => \{\s*if \(e\.key === 'Escape'\) \{(.*?)\}\s*\}\);", text, re.S)
    assert m, "global Escape keydown handler not found"
    body = m.group(1)
    assert "closeExportMenu();" in body
    assert "closeGlidePanel();" in body
    assert "closeCustomTechModal();" in body
    assert "flowPopover" in body and "display = 'none'" in body


# ---------------------------------------------------------- 5. flow node keyboard

def test_flow_nodes_are_keyboard_focusable_with_aria_label():
    text = _text()
    m = re.search(r'return `<div class="flow-node\$\{[^`]*?tabindex="0"[^`]*?role="button"[^`]*?aria-label="\$\{n\.title\}', text, re.S)
    assert m, "flow-node template is missing tabindex/role/aria-label"


def test_flow_node_handlers_attach_a_keydown_listener_for_enter_and_space():
    text = _text()
    m = re.search(r"function attachFlowNodeHandlers\(\)\{(.*?)\n\}", text, re.S)
    assert m, "attachFlowNodeHandlers not found"
    body = m.group(1)
    assert "el.addEventListener('keydown'" in body
    assert "showFlowPopover(el.dataset.id)" in body
    assert "e.key === 'Enter'" in body and "e.key === ' '" in body


# ---------------------------------------------------------- 6. fp-close popover

def test_flow_popover_close_button_is_keyboard_accessible():
    text = _text()
    m = re.search(r'<span class="fp-close"([^>]*)>', text)
    assert m, "fp-close span not found"
    attrs = m.group(1)
    assert 'role="button"' in attrs
    assert 'tabindex="0"' in attrs
    assert 'aria-label="Close"' in attrs
    assert "onkeydown=" in attrs


# ---------------------------------------------------------- 7. delete custom tech

def test_delete_custom_tech_button_has_aria_label():
    text = _text()
    m = re.search(r'onclick="removeCustomTech\(\'\$\{t\.id\}\'\)"([^>]*)>', text)
    assert m, "removeCustomTech button not found"
    assert 'aria-label="Delete custom technology' in m.group(1)


# ---------------------------------------------------------- 8. theme toggle aria sync

def test_sync_theme_toggle_icon_updates_aria_label_too():
    text = _text()
    m = re.search(r"function syncThemeToggleIcon\(\)\{(.*?)\n\}", text, re.S)
    assert m, "syncThemeToggleIcon not found"
    body = m.group(1)
    assert "btn.title = isLight" in body
    assert "btn.setAttribute('aria-label', btn.title);" in body
