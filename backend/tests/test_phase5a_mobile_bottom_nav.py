"""
Regression tests for Phase 5a of the Enterprise-shell plan: the sidebar's interim 64px
icon-rail treatment on narrow viewports is replaced by a real mobile bottom nav, and
#sidebarHistory/#sidebarExportShare become full-screen overlays (via a new
toggleMobileOverlay()) instead of being hidden or squeezed into an icon rail.

Locks in two things this phase must not break:
- The base (pre-media-query) .app-sidebar/.app-shell rules that
  test_enterprise_shell_v2_migration.py::test_sidebar_is_pinned_to_the_viewport_not_stretched_to_page_height
  already asserts (position:sticky, height:100vh, align-items:flex-start) — this phase only
  adds a media-query override, it must never touch those base declarations.
- .flow-toolbar/#flowLegend keep their backdrop-filter (test_dashboard_redesign_migration.py's
  test_deliberately_excluded_overlays_still_have_backdrop_filter) — unrelated to this phase but
  a common thing to accidentally clobber when touching mobile CSS broadly.

Plain string/regex checks against index.html, matching every other migration test file in this
suite — no Node/browser needed. Live-browser verification (bottom nav appears at narrow
widths, History/Export overlays open and close, desktop is unaffected) was done manually
during the session that made this change, not re-verified by these tests.
"""
import re
from pathlib import Path

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"


def _text():
    return INDEX_HTML.read_text(encoding="utf-8")


def _media_block(text):
    """The 860px @media block that holds the new mobile-nav/overlay rules."""
    m = re.search(r"@media \(max-width:860px\)\{(.*?)\n  \}", text, re.S)
    assert m, "860px media query block not found"
    return m.group(1)


# --------------------------------------------------------------------------- bottom nav exists

def test_mobile_bottom_nav_exists_and_reuses_desktop_handlers():
    text = _text()
    m = re.search(r'<nav class="mobile-bottom-nav">(.*?)</nav>', text, re.S)
    assert m, "mobile-bottom-nav markup not found"
    body = m.group(1)
    # Same onclick handlers already wired to the desktop sidebar buttons — not new logic.
    for handler in ("backToMode()", "scrollToResultsShell()", "toggleTheme()"):
        assert handler in body, f"{handler} missing from mobile bottom nav — must reuse the desktop handler"
    assert "toggleMobileOverlay('sidebarHistory')" in body
    assert "toggleMobileOverlay('sidebarExportShare')" in body


def test_bottom_nav_hidden_by_default_shown_only_at_860px():
    text = _text()
    m = re.search(r"\.mobile-bottom-nav\{([^}]*)\}", text)
    assert m and "display:none" in m.group(1), "base rule must hide the bottom nav outside the media query"
    media = _media_block(text)
    assert re.search(r"\.mobile-bottom-nav\{[^}]*display:flex", media), "media query must show it"


# ------------------------------------------------------------------ sidebar collapse mechanism

def test_app_sidebar_collapses_via_flex_basis_not_just_width():
    """Regression lock for a real bug found in this pass: overriding only `width:0` on a flex
    child does nothing when the base rule already sets an explicit `flex:0 0 208px` — flex-basis
    wins over width for a flex item. Both must be zeroed together."""
    text = _text()
    media = _media_block(text)
    m = re.search(r"\.app-sidebar\{([^}]*)\}", media)
    assert m, ".app-sidebar override not found inside the 860px media query"
    rule = m.group(1)
    assert "width:0" in rule
    assert "flex:0 0 0" in rule, "flex-basis must also be zeroed, or the sidebar stays 208px wide"


def test_app_sidebar_collapse_is_not_display_none():
    """display:none on an ancestor can never be overridden by a descendant (no CSS escape
    exists) — that would make it impossible for #sidebarHistory/#sidebarExportShare to ever
    re-appear as full-screen overlays. The collapse must use zero-size + overflow:hidden
    instead, which position:fixed descendants can legitimately escape."""
    text = _text()
    media = _media_block(text)
    m = re.search(r"\.app-sidebar\{([^}]*)\}", media)
    assert m
    assert "display:none" not in m.group(1)
    assert "overflow:hidden" in m.group(1)


def test_base_sidebar_rule_unmodified_by_this_phase():
    """Static regression lock mirroring
    test_sidebar_is_pinned_to_the_viewport_not_stretched_to_page_height — the FIRST (base,
    non-media-query) .app-sidebar block must still carry position:sticky/height:100vh."""
    text = _text()
    m = re.search(r"\.app-sidebar\{([^}]*)\}", text, re.S)  # first match = base rule
    assert m
    base_rule = m.group(1)
    assert "position:sticky" in base_rule
    assert "height:100vh" in base_rule
    shell_m = re.search(r"\.app-shell\{([^}]*)\}", text)
    assert shell_m and "align-items:flex-start" in shell_m.group(1)


# --------------------------------------------------------------------------- overlay mechanism

def test_toggle_mobile_overlay_is_a_true_toggle_reused_for_close():
    text = _text()
    m = re.search(r"function toggleMobileOverlay\(id\)\{(.*?)\n\}", text, re.S)
    assert m, "toggleMobileOverlay not found"
    body = m.group(1)
    assert "classList.toggle('mobile-open'" in body
    # Only one overlay open at a time.
    assert "mobile-open" in body and "forEach" in body


def test_sidebar_history_and_export_share_have_close_buttons_calling_the_same_toggle():
    text = _text()
    assert "toggleMobileOverlay('sidebarHistory')" in text
    assert "toggleMobileOverlay('sidebarExportShare')" in text
    # Count only the actual HTML attribute, not CSS selectors/comments that also mention the
    # class name — must be exactly the two real close-button elements.
    close_buttons = re.findall(r'class="mobile-overlay-close[^"]*"', text)
    assert len(close_buttons) == 2, f"expected exactly 2 close-button elements, found {len(close_buttons)}"


def test_overlay_open_state_is_fixed_fullscreen_inside_media_query():
    text = _text()
    media = _media_block(text)
    m = re.search(r"#sidebarHistory\.mobile-open, #sidebarExportShare\.mobile-open\{([^}]*)\}", media)
    assert m, "mobile-open overlay rule not found inside the 860px media query"
    rule = m.group(1)
    assert "position:fixed" in rule
    assert "inset:0" in rule


def test_render_sidebar_history_syncs_the_mobile_bottom_nav_button():
    text = _text()
    m = re.search(r"function renderSidebarHistory\(\)\{(.*?)\n\}", text, re.S)
    assert m, "renderSidebarHistory not found"
    assert "mobileHistoryBtn" in m.group(1)


def test_set_analysis_syncs_the_mobile_export_share_button():
    text = _text()
    body_start = text.index("function setAnalysis(text, rawSignals, opts){")
    body_end = text.index("\n}\n", body_start)
    body = text[body_start:body_end]
    assert "mobileExportShareBtn" in body


# ------------------------------------------------------- unrelated locked-in overlays untouched

def test_flow_toolbar_and_flow_legend_still_have_backdrop_filter():
    text = _text()
    for sel in (".flow-toolbar", "#flowLegend"):
        m = re.search(re.escape(sel) + r"\{([^}]*)\}", text)
        assert m and "backdrop-filter:" in m.group(1), f"{sel} unexpectedly lost backdrop-filter"
