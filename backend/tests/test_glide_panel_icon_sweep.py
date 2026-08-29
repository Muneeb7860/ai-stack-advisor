"""
Regression tests for the last real emoji-as-iconography sweep in index.html: the 45-item
GLIDE_CONFIGS data object (backing the "Browse all options in a panel" drawer for the
`building` and `teamskills` wizard steps) and 3 unrelated stray emoji.

test_dashboard_redesign_migration.py::test_wizard_chip_and_radio_lines_have_no_emoji only
scans lines containing "pick-chip"/"pr-main" — it never covered GLIDE_CONFIGS, which is a
plain JS object literal with neither substring on any of its lines. This was a real,
previously-uncaught gap, not a regression of that test.

Plain string/regex checks against index.html, matching every other migration test file in
this suite — no Node/browser needed. Live-browser verification (all 45 items render a crisp
stroke icon or the plain dash, in both wizard groups, and the selected-tile pill carries the
icon too) was done manually during the session that made this change, not re-verified here.
"""
import re
from pathlib import Path

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"

# A representative sample, not exhaustive — covers every emoji glyph family used in the
# original GLIDE_CONFIGS (languages, DBs, frontend, cloud, containers, CI/CD, monitoring).
GLIDE_EMOJI_SAMPLE = ["🖥️", "📱", "🔌", "💬", "📊", "🛠️", "📋", "🛒", "☕", "🐍", "🟩", "🔷",
                      "🐹", "💎", "🐘", "🐬", "🗄️", "🔴", "🍃", "🌲", "🔶", "🧩", "⚛️", "🅰️",
                      "💚", "☁️", "🐳", "☸️", "🎩", "🧱", "⚙️", "🔧", "🦊", "⭕", "🐶", "📈",
                      "🔵", "🚗", "🔍"]


def _text():
    return INDEX_HTML.read_text(encoding="utf-8")


def _glide_configs_block(text):
    m = re.search(r"const GLIDE_CONFIGS = \{.*?\n\};", text, re.S)
    assert m, "GLIDE_CONFIGS not found"
    return m.group(0)


# --------------------------------------------------------------- GLIDE_CONFIGS emoji removal

def test_no_icon_field_remains_in_glide_configs():
    block = _glide_configs_block(_text())
    assert "icon:" not in block, "GLIDE_CONFIGS items should no longer carry an icon: field"


def test_no_emoji_glyphs_remain_in_glide_configs():
    block = _glide_configs_block(_text())
    offenders = [e for e in GLIDE_EMOJI_SAMPLE if e in block]
    assert not offenders, f"emoji still present in GLIDE_CONFIGS: {offenders}"


def test_glide_configs_still_has_all_45_items():
    """Guard against the icon-field removal accidentally dropping an item instead of just its
    icon — building (8) + teamskills (38) items, matched by counting `val:` occurrences."""
    block = _glide_configs_block(_text())
    assert block.count("val:") == 46  # 8 building + 38 teamskills


# --------------------------------------------------------------------- GLIDE_ITEM_ICONS map

def test_glide_item_icons_map_exists_and_is_keyed_correctly():
    text = _text()
    m = re.search(r"const GLIDE_ITEM_ICONS = \{(.*?)\n\};", text, re.S)
    assert m, "GLIDE_ITEM_ICONS not found"
    body = m.group(1)
    # building group, keyed by val
    for key in ("web", "mobile", "api", "chatbot", "data", "internal", "admin", "ecommerce"):
        assert f"{key}:" in body, f"GLIDE_ITEM_ICONS missing building key {key!r}"
    # teamskills group, keyed by category
    for cat in ("'Backend language'", "'Database'", "'Frontend framework'", "'Cloud'",
                "'Containers / Orchestration'", "'DevOps / CI-CD'", "'Monitoring'"):
        assert cat in body, f"GLIDE_ITEM_ICONS missing category key {cat}"
    # 'General' deliberately has no entry — falls through to no icon
    assert "'General'" not in body


def test_glide_item_icons_use_the_established_stroke_convention():
    text = _text()
    m = re.search(r"const GLIDE_ITEM_ICONS = \{(.*?)\n\};", text, re.S)
    body = m.group(1)
    assert 'viewBox="0 0 24 24"' in body
    assert 'stroke="currentColor"' in body
    assert "stroke-width=\"1.5\"" in body


# ---------------------------------------------------------------------- render sites updated

def test_open_glide_panel_looks_up_icon_from_the_map_not_the_item():
    text = _text()
    assert 'class="gi-icon">${GLIDE_ITEM_ICONS[it.val] || GLIDE_ITEM_ICONS[it.category] || \'\'}' in text
    assert "class=\"gi-icon\">${it.icon}" not in text


def test_selected_tiles_label_for_looks_up_icon_from_the_map():
    text = _text()
    m = re.search(r"const labelFor = val => \{(.*?)\n  \};", text, re.S)
    assert m, "labelFor not found"
    body = m.group(1)
    assert "GLIDE_ITEM_ICONS[it.val] || GLIDE_ITEM_ICONS[it.category]" in body
    assert "st-icon" in body
    assert "${it.icon}" not in body


def test_gi_icon_and_st_icon_css_are_width_height_based_not_font_size():
    text = _text()
    m = re.search(r"\.glide-item \.gi-icon\{([^}]*)\}", text)
    assert m and "width:16px" in m.group(1) and "height:16px" in m.group(1)
    assert "font-size:16px" not in m.group(1)
    m2 = re.search(r"\.sel-tile \.st-icon\{([^}]*)\}", text)
    assert m2 and "width:14px" in m2.group(1) and "height:14px" in m2.group(1)


# ------------------------------------------------------------------------- 3 stray emoji

def test_export_json_and_save_to_catalog_buttons_have_no_emoji():
    text = _text()
    assert '>Export JSON</button>' in text
    assert '>📥 Export JSON</button>' not in text
    assert '>Save to Local Catalog</button>' in text
    assert '>💾 Save to Local Catalog</button>' not in text


def test_ai_opportunity_tech_label_has_no_emoji():
    text = _text()
    assert '>Tech: <span style="color:var(--text); font-weight:400;">${o.tech}</span>' in text
    assert "🛠️ Tech:" not in text
