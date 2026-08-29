"""
Regression tests for the Enterprise v2.0 shell — Phase 2 (see
docs plan: "visual re-skin of the 17 existing sections... finish the remaining
accent-tint -> color-mix() conversions").

Two deliverables locked in here:
  1. Every remaining hardcoded dark-theme-accent-as-literal CSS declaration
     (the rgba(91,141,239,...)/rgba(124,91,239,...) pattern, and the standalone
     hex literals #8fb2f7/#b4a2f5/#c3b6f7 it left behind) has been converted to
     a theme-aware color-mix()/var() expression. Only explanatory comments
     documenting the old values may still mention them.
  2. The shared sec()-dispatcher section-header template (details.section-block /
     summary.section-title, used by all 17 result sections) got a real re-skin,
     including a genuine bug fix: summary.section-title:hover was still a
     hardcoded blue (#8fb2f7) that silently contradicted .section-title's own
     "neutral, not accent-blue" comment.

Plain string/regex checks against index.html, matching every other migration
test file in this suite (test_dashboard_redesign_migration.py,
test_enterprise_shell_v2_migration.py) — no Node/browser needed. Live-browser
verification (computed styles in both dark and light theme) was done manually
during the session that made this change, not re-verified by these tests.
"""
import re
from pathlib import Path

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"


def _text():
    return INDEX_HTML.read_text(encoding="utf-8")


def _non_comment_lines(text):
    """Strip /* ... */ comments (including multi-line ones) before scanning for
    literals, so an explanatory comment that legitimately mentions an old
    hardcoded value doesn't count as a regression."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


# --------------------------------------------------------- accent-tint sweep

def test_no_hardcoded_dark_accent_rgba_literals_remain_outside_comments():
    code = _non_comment_lines(_text())
    assert "rgba(91,141,239" not in code
    assert "rgba(124,91,239" not in code


def test_no_hardcoded_accent_hex_text_colors_remain_outside_comments():
    code = _non_comment_lines(_text())
    for literal in ("#8fb2f7", "#b4a2f5", "#c3b6f7"):
        assert literal not in code, f"{literal} still used as a real declaration, not just in a comment"


def test_conf_basis_stated_and_constraint_derived_use_color_mix_and_vars():
    text = _text()
    m1 = re.search(r"\.conf-basis-stated\{([^}]*)\}", text)
    m2 = re.search(r"\.conf-basis-constraint-derived\{([^}]*)\}", text)
    assert m1 and "color-mix(in srgb, var(--accent)" in m1.group(1) and "color:var(--accent)" in m1.group(1)
    assert m2 and "color-mix(in srgb, var(--accent2)" in m2.group(1) and "color:var(--accent2)" in m2.group(1)


def test_refine_btn_and_ask_toggle_use_color_mix_not_literals():
    text = _text()
    m = re.search(r"\.refine-btn\{([^}]*)\}", text, re.S)
    assert m and "color-mix(in srgb, var(--accent2)" in m.group(1) and "color-mix(in srgb, var(--accent)" in m.group(1)
    m2 = re.search(r"\.ask-toggle-btn\{([^}]*)\}", text, re.S)
    assert m2 and "color-mix(in srgb, var(--accent)" in m2.group(1)


# ---------------------------------------------------- section-header re-skin

def test_section_block_and_title_have_the_refined_spacing_and_type_scale():
    text = _text()
    m = re.search(r"details\.section-block\{([^}]*)\}", text)
    assert m and "margin-bottom:18px" in m.group(1)
    m2 = re.search(r"summary\.section-title\{([^}]*)\}", text, re.S)
    assert m2, "summary.section-title rule not found"
    body = m2.group(1)
    assert "padding:4px 0 11px" in body
    assert "font-size:11px" in body
    assert "letter-spacing:0.065em" in body


def test_section_title_hover_is_neutral_not_hardcoded_blue():
    """Regression lock for the real bug found in this pass: the hover state was
    color:#8fb2f7 (hardcoded light blue, ignores theme) — directly contradicting
    the adjacent .section-title comment that the base (non-hover) color was
    deliberately made neutral, not accent-blue, to remove a generic-AI-dashboard
    tell. The base state honored that decision; hovering silently undid it."""
    text = _text()
    m = re.search(r"summary\.section-title:hover\{([^}]*)\}", text)
    assert m, "summary.section-title:hover rule not found"
    assert m.group(1).strip() == "color:var(--text);"
    assert "#8fb2f7" not in m.group(1)


def test_section_title_base_rule_is_still_the_pre_existing_neutral_color():
    """Positive control: this pass only touched the hover state — the base
    (non-hover, non-open) color decision from the earlier redesign pass must be
    untouched."""
    text = _text()
    m = re.search(r"(?<!summary)\.section-title\{([^}]*)\}", text, re.S)
    assert m, ".section-title base rule not found"
    assert "color:var(--muted2)" in m.group(1)
