"""
Regression tests for the "de-genericize" pass — sourced from a reference document
(~/Downloads/pr/DESIGN-dashboard.md, outside this repo) that called out concrete
"generic AI tool" tells still present in index.html after Phases 1-3 of the
Enterprise-shell rollout: a two-hue decorative gradient system not fully retired,
a full-viewport marketing hero with a redundant self-referential eyebrow badge,
and some genuinely-read text sitting below a comfortable reading size.

Scope, per explicit user decisions (see the plan file's "De-genericize pass"
section): flatten only 4 specific decorative gradients (not the whole --accent2
system, which stays live for its many other legitimate uses); raise a curated,
targeted list of font sizes to 12px (not every sub-12px selector in the file);
remove the mode-eyebrow badge only (not #screenMode's viewport-centering, which
was itself a deliberate earlier fix for a different problem — dead space around
a small box).

Plain string/regex checks against index.html, matching every other migration
test file in this suite. Live-browser verification (solid accent fills in dark
theme, unchanged appearance in light theme where --accent/--accent2 were already
equal, larger curated text, no eyebrow badge) was done manually during the
session that made this change, not re-verified by these tests.
"""
import re
from pathlib import Path

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"


def _text():
    return INDEX_HTML.read_text(encoding="utf-8")


# ------------------------------------------------------------- gradient flattening

def test_the_four_decorative_gradients_are_flattened_to_solid_accent():
    text = _text()
    m1 = re.search(r"\.glide-item\.selected \.gi-check\{([^}]*)\}", text)
    assert m1 and "background:var(--accent);" in m1.group(1) and "linear-gradient" not in m1.group(1)

    m2 = re.search(r"button\.primary\{([^}]*)\}", text, re.S)
    assert m2 and "background:var(--accent);" in m2.group(1) and "linear-gradient" not in m2.group(1)

    m3 = re.search(r"\.mode-head h1 \.hl-accent\{([^}]*)\}", text)
    assert m3 and "color:var(--accent);" in m3.group(1) and "linear-gradient" not in m3.group(1)

    m4 = re.search(r"\.wiz-fill\{([^}]*)\}", text)
    assert m4 and "background:var(--accent);" in m4.group(1) and "linear-gradient" not in m4.group(1)


def test_accent2_remains_a_distinct_live_token_elsewhere():
    """Static guard for the scope boundary: this pass must NOT have touched --accent2's other
    legitimate uses. A regex sanity check that --accent2 still appears many times in the file
    (i.e. it wasn't globally aliased to --accent) — the two dedicated tests below lock in the
    two specific rules the plan calls out as explicitly out of scope."""
    text = _text()
    assert text.count("var(--accent2)") > 10, "‑‑accent2 should still be a widely-used, distinct token"


def test_results_hero_gradient_and_refine_btn_blend_are_untouched():
    """Explicitly out of scope per the plan: these two use both hues WITH semantic meaning
    (a real background-panel gradient and a real color-mix blend), unlike the four flattened
    above which were purely decorative two-tone effects."""
    text = _text()
    m = re.search(r"\.results-hero\{([^}]*)\}", text, re.S)
    assert m and "linear-gradient" in m.group(1)
    m2 = re.search(r"\.refine-btn\{([^}]*)\}", text, re.S)
    assert m2, ".refine-btn rule not found"
    body = m2.group(1)
    # Counts rather than a bare `in` check: .refine-btn's --accent2 blend appears TWICE
    # (background gradient stop + border color) — a mutation that removes only one occurrence
    # would still satisfy a plain substring check via the surviving second one.
    assert body.count("color-mix(in srgb, var(--accent2)") == 2
    assert body.count("color-mix(in srgb, var(--accent)") == 1


# ------------------------------------------------------------------- font floor

CURATED_SELECTOR_MIN_SIZE = [
    (r"label\.field-label\{([^}]*)\}", "font-size:12px"),
    (r"\.footer-note\{([^}]*)\}", "font-size:12px"),
    (r"\.cost-label\{([^}]*)\}", "font-size:12px"),
    (r"\.cost-detail\{([^}]*)\}", "font-size:12px"),
    (r"\.gov-block h4\{([^}]*)\}", "font-size:12px"),
    (r"\.assumption\{([^}]*)\}", "font-size:12px"),
    (r"\.tradeoff-card h3\{([^}]*)\}", "font-size:12px"),
    (r"\.glossary\{([^}]*)\}", "font-size:12px"),
    (r"\.flow-popover \.fp-why\{([^}]*)\}", "font-size:12px"),
    (r"\.flow-popover \.fp-why ul\{([^}]*)\}", "font-size:12px"),
]


def test_curated_font_size_selectors_are_raised_to_12px():
    text = _text()
    for pattern, expected in CURATED_SELECTOR_MIN_SIZE:
        m = re.search(pattern, text)
        assert m, f"selector not found: {pattern}"
        assert expected in m.group(1), f"{pattern} missing {expected}: {m.group(1)[:120]!r}"


def test_custom_tech_form_labels_are_raised_to_12px():
    text = _text()
    old = '<label style="display:block; font-size:11px; font-weight:600; color:var(--muted); margin-bottom:4px;">'
    new = '<label style="display:block; font-size:12px; font-weight:600; color:var(--muted); margin-bottom:4px;">'
    assert old not in text, "old 11px custom-tech form label style should be gone"
    assert text.count(new) == 8, f"expected 8 custom-tech form labels at 12px, found {text.count(new)}"


def test_ai_opportunity_drawer_text_is_raised_to_12px_in_both_views():
    """Counts occurrences rather than a bare substring check — the flow-view copy of this
    template was ALREADY 12px before this pass (only the results-view copy needed raising), so
    a plain `in` check would silently pass even if the results-view edit were reverted, since
    the untouched flow-view copy alone satisfies it."""
    text = _text()
    assert text.count('<strong style="font-size:12px; color:var(--text);">${o.name}</strong>') == 2, \
        "expected both the results-view and flow-view o.name templates at 12px"
    assert text.count('<div style="font-size:12px; color:var(--muted); line-height:1.4;">${o.rationale}</div>') == 1
    assert text.count('<div style="font-size:12px; color:var(--muted); margin-bottom:4px;">${o.rationale}</div>') == 1


def test_section_title_and_badge_family_font_sizes_are_untouched():
    """Regression guard for the scope boundary: this pass was explicitly a curated list, not a
    full sub-12px sweep. summary.section-title stays at 11px (load-bearing on an existing
    Phase 2 test and a deliberate type-scale decision), and representative "tiny by design" UI
    (a badge, a popover category eyebrow) must not have been swept up by mistake."""
    text = _text()
    m = re.search(r"summary\.section-title\{([^}]*)\}", text, re.S)
    assert m and "font-size:11px" in m.group(1)
    m2 = re.search(r"\.flow-popover \.fp-cat\{([^}]*)\}", text)
    assert m2 and "font-size:9px" in m2.group(1)


# -------------------------------------------------------------------- hero de-emphasis

def test_mode_eyebrow_badge_is_removed():
    text = _text()
    assert "mode-eyebrow" not in text, "the self-referential eyebrow badge and its CSS should be fully removed"
    assert '<div class="mode-eyebrow">' not in text


def test_mode_head_still_renders_headline_and_subhead():
    """Positive control: removing the eyebrow badge must not have taken the actual headline/
    subhead content with it."""
    text = _text()
    m = re.search(r'<div class="mode-head">(.*?)</div>', text, re.S)
    assert m, "mode-head block not found"
    body = m.group(1)
    assert "<h1>" in body and "hl-accent" in body
    assert "<p>" in body


def test_screen_mode_viewport_centering_is_untouched():
    """This pass explicitly did NOT touch #screenMode's min-height/centering — that was a
    separate, deliberate earlier fix for dead space around a small box, not the marketing-hero
    complaint this pass addresses. Only the eyebrow badge (a redundant self-referential status
    pill) was in scope."""
    text = _text()
    m = re.search(r"#screenMode\{([^}]*)\}", text, re.S)
    assert m and "min-height:calc(100vh - 90px)" in m.group(1)
