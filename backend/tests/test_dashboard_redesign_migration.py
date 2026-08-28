"""
Regression tests for the dashboard-redesign migration (design/DESIGN-dashboard.md, steps 1-4 —
"mechanical and independent" per that doc's own Migration section). Scope, per an explicit user
decision mid-session: tokens (step 1) apply to the LIGHT theme only — the redesign's palette is
specified for a light background and the app has an existing, deliberate "keep dark as the
default" decision predating this work; dark theme keeps its existing colors, only losing the
two-hue accent gradient (steps 2/3/4, which are structural/effect changes, not new palette
values, apply to both themes).

These are plain string/regex checks against index.html — no Node/browser needed, matching the
"pure filesystem and string work... needs to run everywhere" reasoning already used by
test_kb_corpus.py in this same suite. They lock in PRESENCE of the change, not visual
correctness (that was verified live in-browser during the session that made this change, not
re-verified by these tests).
"""
import re
from pathlib import Path

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"


def _text():
    return INDEX_HTML.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------- step 1: tokens

def test_light_theme_uses_the_new_token_values():
    text = _text()
    m = re.search(r':root\[data-theme="light"\]\{(.*?)\}', text, re.S)
    assert m, "light theme block not found"
    block = m.group(1)
    assert "--bg:#f9fafb" in block
    assert "--text:#111827" in block
    assert "--border:#e5e7eb" in block
    assert "--good:#16a34a" in block
    assert "--warn:#f59e0b" in block
    assert "--bad:#b91c1c" in block


def test_light_theme_accent_is_text_safe_and_single_hue():
    """Decision #2 ("one accent") and #3 (contrast) — accent-700 (#0b7473, 5.59:1) used
    everywhere, not accent-500 (#0ea5a4, 3.03:1, fails text contrast), and --accent2 equals
    --accent so every `linear-gradient(135deg, var(--accent), var(--accent2))` rule collapses to
    a flat fill without needing to touch the rule itself."""
    text = _text()
    m = re.search(r':root\[data-theme="light"\]\{(.*?)\}', text, re.S)
    block = m.group(1)
    assert "--accent:#0b7473" in block
    assert "--accent2:#0b7473" in block
    assert "#0ea5a4" not in block, "accent-500 (fails text contrast) must not be used directly as a token value"


def test_dark_theme_keeps_its_own_accent_pair_unchanged():
    """The explicit scope decision: dark theme's palette is untouched, including keeping its
    two DISTINCT accent hues (unlike light theme, which collapses them to one)."""
    text = _text()
    m = re.search(r":root\{(.*?)\}", text, re.S)
    assert m, "base (dark) :root block not found"
    block = m.group(1)
    assert "--accent:#5b8def" in block
    assert "--accent2:#7c5bef" in block
    assert "--accent:#5b8def" != "--accent2:#7c5bef"  # sanity: still two distinct values


def test_font_mono_prefers_jetbrains_mono_with_the_old_stack_as_fallback():
    text = _text()
    assert "--font-mono:'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;" in text


def test_jetbrains_mono_is_loaded_via_the_existing_google_fonts_request():
    text = _text()
    assert "family=JetBrains+Mono" in text
    # Combined into the SAME <link> as Inter, not a second request.
    assert re.search(r'<link href="https://fonts\.googleapis\.com/css2\?family=Inter[^"]*family=JetBrains\+Mono[^"]*"', text)


# ------------------------------------------------------------------- step 2: no more glass

NAMED_GLASS_SELECTORS = [".theme-toggle", ".glide-panel", ".card", ".stack-card", ".mode-card", ".hero-preview", ".results-hero"]


def test_no_backdrop_filter_remains_on_the_seven_named_selectors():
    """DESIGN-dashboard.md decision #7 names these seven selectors as the backdrop-filter/glass
    sites to remove. Checks each selector's own rule block for an actual `backdrop-filter:`
    PROPERTY declaration (not a bare substring match, which would also trip on this file's own
    explanatory comments describing the removal) — the un-named floating-overlay uses (.toc's
    mobile bar, .flow-toolbar, #flowLegend, .export-menu, .custom-modal-backdrop) are
    deliberately untouched and must stay that way."""
    text = _text()
    for sel in NAMED_GLASS_SELECTORS:
        escaped = re.escape(sel)
        m = re.search(escaped + r"\{([^}]*)\}", text)
        assert m, f"{sel} rule not found"
        assert "backdrop-filter:" not in m.group(1), f"{sel} still has backdrop-filter"


def test_deliberately_excluded_overlays_still_have_backdrop_filter():
    """Negative control for the test above — if these ever lose backdrop-filter too, that's
    either a deliberate follow-up (update this test) or a sign the removal accidentally spread
    past the seven named selectors."""
    text = _text()
    for sel in [".flow-toolbar", "#flowLegend"]:
        escaped = re.escape(sel)
        m = re.search(escaped + r"\{([^}]*)\}", text)
        assert m and "backdrop-filter:" in m.group(1), f"{sel} unexpectedly lost backdrop-filter"
    assert 'class="custom-modal-backdrop"' in text and "backdrop-filter:blur(4px)" in text


def test_glass_only_tokens_were_removed_as_dead_code():
    text = _text()
    for tok in ("--panel-glass:", "--panel2-glass:", "--glass-border:", "--glass-blur:"):
        assert tok not in text, f"{tok} should have been removed once nothing reads it anymore"


# ------------------------------------------------------------------ step 3: no more emoji

WIZARD_EMOJI = ["🖥️", "📱", "🔌", "📊", "🛠️", "📋", "🛒", "🏥", "💳", "🏢", "🏛️", "☕", "🐍", "🟩",
                "🔷", "🐹", "💎", "🐘", "📚", "🎯", "🛡️", "🤔", "📡"]


def test_wizard_chip_and_radio_lines_have_no_emoji():
    text = _text()
    offenders = []
    for line in text.splitlines():
        if "pick-chip" in line or "pr-main" in line:
            for e in WIZARD_EMOJI:
                if e in line:
                    offenders.append((e, line.strip()[:80]))
    assert not offenders, f"emoji still present in wizard chip/radio markup: {offenders}"


def test_pick_chip_icon_span_class_exists_and_is_used():
    text = _text()
    assert ".pick-chip .pc-icon{" in text
    assert text.count('class="pc-icon"') >= 15, "expected at least the 15 originally-emoji chips to carry an icon span"


# --------------------------------------------------------- step 4: badge/signal-row collapse

def test_why_signals_row_is_collapsed_behind_a_details_disclosure():
    text = _text()
    m = re.search(r"function renderWhySignals\(category\)\{(.*?)\n\}", text, re.S)
    assert m, "renderWhySignals not found"
    body = m.group(1)
    assert "<details" in body
    assert "why-signals-toggle" in body


def test_pick_chip_and_radio_selected_tints_are_tokenized_not_hardcoded():
    """Directly-touched-by-this-change sites (the chip/radio components step 3 modified) must
    not carry the old hardcoded dark-theme-accent rgba literal, which would look wrong once
    light theme's accent became teal."""
    text = _text()
    m1 = re.search(r"\.pick-chip\.selected\{([^}]*)\}", text)
    m2 = re.search(r"\.pick-radio\.selected\{([^}]*)\}", text)
    assert m1 and "rgba(91,141,239" not in m1.group(1)
    assert m2 and "rgba(91,141,239" not in m2.group(1)
    assert "color-mix(in srgb, var(--accent)" in m1.group(1)
