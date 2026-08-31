"""Minimalist pass, step 1: retire the decorative second hue from the label system.

Direction: "upgrade the FE toward n8n's look — minimalist", scoped (with the user) to a
minimalist pass on the EXISTING dark theme rather than a full light/coral re-skin or a
canvas-first restructure. Flow View already had its own n8n visual pass (PR #4, locked by
test_flow_view_style.py); this is about the app around it.

What this pass changes and why it's decidable rather than a matter of taste: --accent2 (purple)
was used 34 times, and those uses split cleanly into two kinds.

  * DECORATIVE — small uppercase eyebrow/heading/persona/table-header text rendered purple for
    no semantic reason. A second hue applied to label chrome is exactly the "generic AI tool"
    tell the earlier de-genericize pass was already chasing. These move to --muted, and their
    font-weight drops 700 -> 600 (same "quiet the label system" move, applied to the same
    selectors rather than as a separate sweep).
  * SEMANTIC — confidence level (.card-conf-medium's border, .conf's dot), basis type
    (.conf-basis-constraint-derived), signal chips (.why-sig), the complementary-vendor block,
    the inference strip. These carry information in the hue; removing it would lose a channel,
    not reduce noise. Untouched.

One case is neither: `.alt-toggle summary` ("See N alternatives") is an interactive control that
happened to be purple. Muting it would cost discoverability, so it moves to --accent (the primary
hue) instead — the second hue leaves the palette without the affordance leaving with it.

Deliberately compatible with two prior locked decisions rather than reversing them:
  * test_dashboard_redesign_migration.py::test_dark_theme_keeps_its_own_accent_pair_unchanged
    asserts both tokens stay DEFINED in :root — they do.
  * test_degenericize_pass.py::test_accent2_remains_a_distinct_live_token_elsewhere asserts
    var(--accent2) still appears >10 times — it appears 16 times after this pass, all semantic.
Both still pass unmodified. This pass narrows where the second hue is used; it does not retire
the token, which the user explicitly locked as a live, distinct token in the de-genericize scope.
"""
import re
from pathlib import Path

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"


def _text() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


# ------------------------------------------------- decorative labels lost the decorative hue

DECORATIVE_LABEL_SELECTORS = [
    r"\.results-hero \.rh-eyebrow\{",
    r"\.persona\{",
    r"\.cost-label\{",
    r"\.gov-block h4\{",
    r"\.vram-table th\{",
    r"\.flow-popover \.fp-persona\{",
    r"\.refine-history-time\{",
]


def _rule_body(pattern: str) -> str:
    text = _text()
    m = re.search(pattern + r"([^}]*)\}", text)
    assert m, f"rule {pattern!r} not found"
    return m.group(1)


def test_decorative_label_selectors_no_longer_use_the_second_accent():
    """The core of the pass: a second hue on non-semantic label chrome is the noise being
    removed. Each of these is small uppercase text whose purple carried no meaning."""
    for pattern in DECORATIVE_LABEL_SELECTORS:
        body = _rule_body(pattern)
        assert "var(--accent2)" not in body, f"{pattern} still uses the decorative second accent"
        assert "var(--muted)" in body, f"{pattern} should now use the muted token"


def test_decorative_labels_are_not_also_heavy_weight():
    """Same "quiet the label system" move as the hue change, applied to the same selectors: a
    700-weight uppercase micro-label is loud regardless of its colour."""
    for pattern in [r"\.results-hero \.rh-eyebrow\{", r"\.persona\{", r"\.cost-label\{",
                    r"\.gov-block h4\{", r"\.flow-popover \.fp-persona\{"]:
        body = _rule_body(pattern)
        assert "font-weight:700" not in body, f"{pattern} should no longer be 700-weight"


# --------------------------------------- interactive control kept its affordance, lost the hue

def test_alt_toggle_summary_is_accent_not_muted_and_not_second_accent():
    """The one case that is neither decorative nor semantic: an interactive disclosure that
    happened to be purple. Muting it would cost discoverability, so it takes the PRIMARY accent
    — the second hue leaves the palette without the affordance leaving with it."""
    body = _rule_body(r"\.alt-toggle summary, \.why-signals-toggle summary\{")
    assert "var(--accent2)" not in body
    assert "var(--accent)" in body
    assert "var(--muted)" not in body, "an interactive control must not be muted into the chrome"


# ------------------------------------------------------------- semantic uses stayed untouched

def test_confidence_and_basis_channels_still_carry_the_second_hue():
    """These encode information in the hue — confidence level and basis type. Removing it would
    lose a channel rather than reduce noise, which is the line this pass draws."""
    text = _text()
    assert "border-left-color:var(--accent2)" in text, "confidence-medium border channel lost"
    assert re.search(r"\.conf::before\{[^}]*background:var\(--accent2\)", text), "confidence dot lost"
    assert re.search(r"\.conf-basis-constraint-derived\{[^}]*var\(--accent2\)", text), "basis channel lost"


def test_the_second_accent_token_is_still_defined_and_live():
    """Explicit compatibility check with the two prior locked decisions this pass must not
    reverse: the token stays defined in :root and stays widely used for its semantic purposes.
    This pass narrows WHERE the hue is used; it does not retire it."""
    text = _text()
    m = re.search(r":root\{(.*?)\}", text, re.S)
    assert m and "--accent2:#7c5bef" in m.group(1), "token must remain defined in :root"
    assert text.count("var(--accent2)") > 10, "token must remain live, per the de-genericize lock"


def test_second_accent_is_now_used_less_than_before_this_pass():
    """Directional guard: the pass only means something if the decorative uses actually went
    away. 34 before; anything at or above that means the pass was reverted or re-expanded."""
    assert _text().count("var(--accent2)") < 30
