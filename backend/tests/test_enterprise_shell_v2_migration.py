"""
Regression tests for Enterprise v2.0 shell — Phase 1: persistent sidebar + 3-column skeleton
(see the plan this was built from: a persistent app shell wrapping the existing, unmodified
results pipeline). Purely additive DOM/CSS restructuring — computeRecommendations,
renderRecommendations's section content, sec(), the wizard, and the rule engine are untouched.

Plain string/regex checks against index.html — no Node/browser needed, matching
test_kb_corpus.py's and test_dashboard_redesign_migration.py's own reasoning for why this class
of check needs to run everywhere. Live-browser verification (sidebar renders, stays pinned while
scrolling, export flyout opens on-screen, Cards/Flow toggle and theme toggle still work) was done
manually during the session that made this change, not re-verified by these tests.
"""
import re
from pathlib import Path

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"


def _text():
    return INDEX_HTML.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- shell structure

def test_app_shell_and_sidebar_exist():
    text = _text()
    assert '<div class="app-shell">' in text
    assert '<aside class="app-sidebar">' in text
    assert '<div class="app-main">' in text


def test_sidebar_contains_new_analysis_this_analysis_and_export_share():
    text = _text()
    assert 'onclick="backToMode()"' in text
    assert 'id="sidebarThisAnalysisBtn"' in text
    assert 'id="sidebarExportShare"' in text


def test_context_panel_placeholder_exists_and_is_hidden():
    """Reserved for a future phase (routing refine/ask into a drawer) — must exist as a real
    DOM node now, but must not be visibly active yet: no content, no visible styling beyond the
    hidden-by-default CSS rule."""
    text = _text()
    assert '<aside id="contextPanel"></aside>' in text
    m = re.search(r"#contextPanel\{([^}]*)\}", text)
    assert m, "#contextPanel CSS rule not found"
    assert "display:none" in m.group(1)


def test_theme_toggle_moved_into_sidebar_not_fixed_at_document_root():
    """The button element itself must be a child of the sidebar markup now (not a
    document-root sibling of the glide panel, its old position)."""
    text = _text()
    sidebar_open = text.index('<aside class="app-sidebar">')
    sidebar_close = text.index("</aside>", sidebar_open)
    assert 'id="themeToggle"' in text[sidebar_open:sidebar_close]


# ------------------------------------------------------------------- export/share relocation

def test_export_dropdown_and_share_button_moved_out_of_results_header():
    """The results-header must no longer contain the export dropdown or share button — only
    the (unrelated, untouched) refine-history-controls row."""
    text = _text()
    m = re.search(r'<div class="results-header" id="resultsHeader"[^>]*>(.*?)<div id="results">', text, re.S)
    assert m, "resultsHeader..#results span not found"
    header_body = m.group(1)
    assert 'id="exportDropdown"' not in header_body
    assert 'id="shareBtn"' not in header_body
    assert 'id="refineHistoryControls"' in header_body


def test_export_dropdown_and_share_button_now_live_in_sidebar_export_share():
    text = _text()
    m = re.search(r'<div id="sidebarExportShare"[^>]*>(.*?)</div>\s*</nav>', text, re.S)
    assert m, "#sidebarExportShare block not found"
    body = m.group(1)
    assert 'id="exportDropdown"' in body
    assert 'id="shareBtn"' in body
    # All seven export actions must have moved with it, not been dropped.
    for handler in ("onExportAdrClick", "onExportJsonClick", "onExportDrawioClick",
                     "onExportMermaidClick", "onCopyMermaidClick", "onExportSvgClick",
                     "onOpenDiagramsNetClick"):
        assert handler in body, f"{handler} missing from relocated export menu"


def test_export_menu_anchors_left_when_inside_the_sidebar():
    """Regression lock for a real bug found via live browser check: .export-menu's default
    right:0 anchored it 280px leftward from the button, which extended off the left edge of the
    viewport entirely once the button moved into a narrow, left-edge-hugging sidebar column
    (measured: opened at x:-69). Anchoring left instead lets it open into the main content area."""
    text = _text()
    m = re.search(r"\.app-sidebar \.export-menu\{([^}]*)\}", text)
    assert m, ".app-sidebar .export-menu override not found"
    assert "left:0" in m.group(1)


# -------------------------------------------------------------------------- sidebar viewport pin

def test_sidebar_is_pinned_to_the_viewport_not_stretched_to_page_height():
    """Regression lock for a real bug found via live browser check: align-items:stretch (flex's
    default) made the sidebar match .app-main's height, which is the full PAGE height (very
    tall once results render), not the viewport's — measured at ~19,500px tall in a real
    analysis, scrolling the sidebar's own nav items far off-screen. position:sticky + a real
    viewport-relative height (100vh) + align-items:flex-start on the parent fixes it."""
    text = _text()
    shell_m = re.search(r"\.app-shell\{([^}]*)\}", text)
    assert shell_m, ".app-shell rule not found"
    assert "align-items:flex-start" in shell_m.group(1)
    sidebar_m = re.search(r"\.app-sidebar\{([^}]*)\}", text, re.S)
    assert sidebar_m, ".app-sidebar rule not found"
    sidebar_rule = sidebar_m.group(1)
    assert "position:sticky" in sidebar_rule
    assert "height:100vh" in sidebar_rule


# ------------------------------------------------------------------ untouched-by-design checks

def test_results_shell_still_has_all_three_children_with_original_ids():
    """#sideNav and #results/#flowWrap (inside .results-col) must keep their ids — every
    getElementById call and resultsShell.scrollIntoView() site depends on this. #contextPanel is
    the one new addition, added as a THIRD sibling, not a replacement of anything."""
    text = _text()
    m = re.search(r'<div class="results-shell" id="resultsShell">(.*?)\n<!-- Custom Technology', text, re.S)
    assert m, "resultsShell block not found"
    body = m.group(1)
    assert 'id="sideNav"' in body
    assert 'id="results"' in body
    assert 'id="flowWrap"' in body
    assert 'id="contextPanel"' in body


def test_compute_and_render_recommendations_are_unchanged_by_this_phase():
    """This phase is presentation/layout only — the actual signal-detection and
    recommendation-computation logic must not have moved or been touched."""
    text = _text()
    assert "function computeRecommendations(s){" in text
    assert "function renderRecommendations(s, rec){" in text
    assert "const sec = (id, navLabel, titleHtml, bodyHtml)" in text
