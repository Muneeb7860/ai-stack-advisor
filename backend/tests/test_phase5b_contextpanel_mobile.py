"""
Regression tests for Phase 5b of the Enterprise-shell plan: #contextPanel gets a real mobile
treatment.

Before this phase, #contextPanel had NO override at all inside the 860px media query. Once its
flex parent (.results-shell) goes display:block there, flex:0 0 300px is meaningless (no longer
a flex item), so the panel fell back to full width — but it kept position:sticky from the
desktop rule, producing a sticky, full-bleed drawer on narrow viewports with no dedicated mobile
dismissal. This phase turns #contextPanel.open into a real full-screen modal at that breakpoint,
CSS-only — the existing .ctx-panel-header close button and closeContextPanel() JS are untouched
and don't need to be, since neither depends on the panel's positioning.

Plain string/regex checks against index.html, matching every other migration test file in this
suite — no Node/browser needed. Live-browser verification (opening refine/ask at 375px shows a
full-screen modal with a working close button; desktop is completely unaffected) was done
manually during the session that made this change, not re-verified by these tests.
"""
import re
from pathlib import Path

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"


def _text():
    return INDEX_HTML.read_text(encoding="utf-8")


def _results_shell_media_block(text):
    """The 860px @media block that holds .results-shell/.toc's mobile treatment — the one
    #contextPanel's mobile override was added to, distinct from the sidebar/bottom-nav's own
    860px block added in Phase 5a."""
    m = re.search(r"@media \(max-width:860px\)\{\s*\.results-shell\{display:block;\}(.*?)\n  \}", text, re.S)
    assert m, "results-shell 860px media query block not found"
    return m.group(1)


def test_context_panel_open_is_fullscreen_fixed_inside_the_media_query():
    text = _text()
    media = _results_shell_media_block(text)
    m = re.search(r"#contextPanel\.open\{([^}]*)\}", media)
    assert m, "#contextPanel.open override not found inside the results-shell 860px media query"
    rule = m.group(1)
    assert "position:fixed" in rule
    assert "inset:0" in rule


def test_context_panel_desktop_rule_still_sticky_and_unmodified():
    """Static regression lock — the BASE (pre-media-query) #contextPanel rule must still be the
    original sticky sidebar-column treatment; this phase only adds an override inside the media
    query, it must never touch the base rule."""
    text = _text()
    m = re.search(r"#contextPanel\{([^}]*)\}", text, re.S)  # first match = base rule
    assert m
    base_rule = m.group(1)
    assert "position:sticky" in base_rule
    assert "flex:0 0 300px" in base_rule


def test_ctx_panel_header_close_button_and_function_are_unchanged():
    """This phase is CSS-only — closeContextPanel() and the close button's onclick must not
    have been touched, since neither depends on the panel's positioning."""
    text = _text()
    assert 'onclick="closeContextPanel()"' in text
    m = re.search(r"function closeContextPanel\(\)\{(.*?)\n\}", text, re.S)
    assert m, "closeContextPanel not found"
    assert "classList.remove('open')" in m.group(1)


def test_mobile_override_is_scoped_to_the_open_class_not_the_bare_selector():
    """#contextPanel is already display:none by default (base rule) — the mobile override must
    key off .open (matching the desktop behavior's own gating), not the bare #contextPanel
    selector, or a closed panel could get pulled into fixed/fullscreen layout for no reason."""
    text = _text()
    media = _results_shell_media_block(text)
    assert "#contextPanel.open{" in media
    assert "#contextPanel{" not in media, "mobile override must be scoped to .open, not the bare selector"
