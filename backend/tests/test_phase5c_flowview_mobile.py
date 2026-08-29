"""
Regression tests for Phase 5c of the Enterprise-shell plan: Flow View canvas gets a mobile
treatment. Before this phase, #flowMinimap/.flow-toolbar/#flowLegend had zero mobile-specific
CSS anywhere in the file — all three fixed-position/fixed-size overlays, likely to crowd or
overlap a phone viewport, plus 26px zoom-toolbar buttons (touch-target-small).

Plain string/regex checks against index.html, matching every other migration test file in this
suite — no Node/browser needed. Live-browser verification (minimap hidden, toolbar buttons
enlarged, legend uncrowded, and — the one real bug this phase found — the toolbar no longer
sitting underneath the fixed mobile bottom nav at the natural "flow view scrolled fully into
view" scroll position) was done manually during the session that made this change, not
re-verified by these tests.
"""
import re
from pathlib import Path

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"


def _text():
    return INDEX_HTML.read_text(encoding="utf-8")


def _flowview_media_block(text):
    """The dedicated Phase 5c 860px block, placed immediately after the base .flow-hint rule —
    deliberately its own media query (not appended to the Phase 5a/5b blocks earlier in the
    file), since it must come AFTER the base .flow-toolbar/#flowLegend/#flowMinimap
    declarations to win the cascade."""
    m = re.search(r"\.flow-hint\{[^}]*\}\s*(?:/\*.*?\*/\s*)?@media \(max-width:860px\)\{(.*?)\n  \}", text, re.S)
    assert m, "Phase 5c 860px media block not found after .flow-hint"
    return m.group(1)


def test_flow_minimap_hidden_additively_not_replacing_its_base_rule():
    text = _text()
    media = _flowview_media_block(text)
    assert re.search(r"#flowMinimap\{display:none;?\}", media)
    # Base rule (declared earlier, before this media block) must be untouched.
    base = re.search(r"#flowMinimap\{([^}]*)\}", text)
    assert base and "width:170px" in base.group(1) and "height:110px" in base.group(1)


def test_flow_toolbar_and_legend_keep_their_backdrop_filter():
    """Locked in by test_dashboard_redesign_migration.py::
    test_deliberately_excluded_overlays_still_have_backdrop_filter — this phase's media block
    must never redeclare background/backdrop-filter/border for either overlay, only add to
    what's not already covered (button size, bottom offset)."""
    text = _text()
    for sel in (".flow-toolbar", "#flowLegend"):
        m = re.search(re.escape(sel) + r"\{([^}]*)\}", text)
        assert m and "backdrop-filter:" in m.group(1), f"{sel} unexpectedly lost backdrop-filter"
    media = _flowview_media_block(text)
    # The media block itself must not redeclare backdrop-filter/background for either overlay —
    # confirms this phase only ever ADDS new properties, never touches the locked ones.
    assert "backdrop-filter" not in media
    assert "background:rgba" not in media


def test_flow_toolbar_buttons_have_a_real_touch_target():
    text = _text()
    media = _flowview_media_block(text)
    m = re.search(r"\.flow-toolbar button\{([^}]*)\}", media)
    assert m, "mobile .flow-toolbar button override not found"
    rule = m.group(1)
    assert "width:36px" in rule and "height:36px" in rule
    # Base (desktop) rule must stay at its original smaller size — untouched by this phase.
    base = re.search(r"\.flow-toolbar button\{([^}]*)\}", text)
    assert base and "width:26px" in base.group(1) and "height:26px" in base.group(1)


def test_flow_toolbar_bottom_offset_clears_the_mobile_bottom_nav():
    """Regression lock for a real bug found via live scroll testing in this pass:
    .flow-toolbar's bottom:12px is relative to #flowWrap's own box, not the viewport — at the
    natural scroll position where #flowWrap is scrolled fully into view, that put the toolbar
    entirely inside the fixed .mobile-bottom-nav's 56px band (it renders on top, higher
    z-index), making pan/zoom/fit unusable. Must be large enough to clear that band (56px) plus
    the original 12px gap."""
    text = _text()
    media = _flowview_media_block(text)
    m = re.search(r"(?<!button)\.flow-toolbar\{([^}]*)\}", media)
    assert m, "mobile .flow-toolbar bottom-offset override not found"
    rule = m.group(1)
    bottom_match = re.search(r"bottom:(\d+)px", rule)
    assert bottom_match, "no bottom offset override found for .flow-toolbar on mobile"
    assert int(bottom_match.group(1)) >= 68, "bottom offset must clear the ~56px fixed bottom nav plus a gap"


def test_mobile_bottom_nav_height_matches_the_toolbar_clearance_assumption():
    """If .mobile-bottom-nav's height ever changes, the toolbar clearance above must be
    re-derived — this test makes that coupling explicit rather than a coincidence two
    independent-looking numbers happen to agree on today."""
    text = _text()
    m = re.search(r"\.mobile-bottom-nav\{[^}]*height:(\d+)px", text)
    assert m, ".mobile-bottom-nav height not found"
    nav_height = int(m.group(1))
    media = _flowview_media_block(text)
    bottom_match = re.search(r"(?<!button)\.flow-toolbar\{[^}]*bottom:(\d+)px", media)
    assert bottom_match
    assert int(bottom_match.group(1)) >= nav_height, "toolbar clearance must be >= the bottom nav's own height"
