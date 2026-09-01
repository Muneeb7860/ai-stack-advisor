"""Semantic colour (--good / --warn) must survive the light theme.

The finding. `--good` (#34c98a) and `--warn` (#e0a23c) are the DARK theme's signal colours, and
both were also written as raw `rgba(52,201,138,…)` / `rgba(224,162,60,…)` literals in 11 CSS
rules. Literals don't follow a token override, so every one of those rules kept painting the dark
value under `[data-theme="light"]`, where `--good`/`--warn` are supposed to become #16a34a and
#f59e0b. Two measured consequences on a white card:

  * `.g-chip` — the guardrails list — was pale amber #e8c07e on a 10%-amber tint: **1.59:1**.
    WCAG wants 4.5:1 for body text. It was effectively unreadable in light mode.
  * `.iam-vendor-card.recommended` — the border that marks WHICH vendor was recommended — was
    `--good` at 40% over white: **1.37:1**. The mark carried information and was invisible.

The fix has two halves, and the second is the part worth remembering: swapping the literal for
`var(--good)` is necessary but NOT sufficient for text, because the signal tokens are tuned to sit
on a dark ground and are not legible as text on a light one — light `--warn` is only 2.15:1 on
white. So `--good-text` / `--warn-text` exist as the text-safe partners, and the rule is: signal
tokens for fills, borders and glyphs; text tokens for anything actually read.

These tests compute real WCAG contrast from the tokens rather than asserting a hex string appears.
A string check would pass on any value someone typed; this fails only when the page is genuinely
hard to read, which is the property that actually matters. It is also the lesson this suite keeps
relearning — several earlier tests in this repo passed while matching their own comment prose.
"""
import re
from pathlib import Path

import pytest

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"

# WCAG 2.1: 4.5:1 for normal-size text, 3:1 for large text and meaningful UI boundaries.
TEXT_MIN = 4.5
UI_MIN = 3.0


def _text() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- colour utilities

def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _channel(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(rgb) -> float:
    r, g, b = (_channel(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b) -> float:
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def blend(fg, alpha: float, bg):
    """What `color-mix(in srgb, C alpha%, transparent)` actually looks like once composited."""
    return tuple(round(alpha * f + (1 - alpha) * b) for f, b in zip(fg, bg))


# --------------------------------------------------------------------------- token extraction

def _strip_comments(s: str) -> str:
    return re.sub(r"/\*.*?\*/", "", s, flags=re.S)


def _tokens(theme: str) -> dict:
    """Resolved token map for a theme. Comments are stripped first — this file's own history
    includes three separate tests that passed by matching a hex inside a comment explaining why
    that hex was NOT used."""
    t = _text()
    if theme == "dark":
        m = re.search(r":root\{(.*?)\n  \}", t, re.S)
    else:
        m = re.search(r':root\[data-theme="light"\]\{(.*?)\n  \}', t, re.S)
    assert m, f"{theme} token block not found"
    body = _strip_comments(m.group(1))
    found = dict(re.findall(r"(--[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8})\s*;", body))
    if theme == "light":  # light only overrides; everything else inherits from :root
        base = _tokens("dark")
        base.update(found)
        return base
    return found


THEMES = ["dark", "light"]


# --------------------------------------------------------------------------- the token set

@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("token", ["--good", "--warn", "--bad", "--good-text", "--warn-text"])
def test_every_semantic_token_is_defined_in_both_themes(theme, token):
    """--bad used to exist only under [data-theme="light"] — a token defined in one theme and not
    the other, which is the same shape of bug as light's --surface being collapsed onto --panel.
    Nothing read it yet, so it was harmless; asserted now so it cannot be reintroduced quietly."""
    assert token in _tokens(theme), f"{token} is missing from the {theme} theme"


# --------------------------------------------------------------------------- legibility

def _rule(selector: str) -> str:
    m = re.search(re.escape(selector) + r"\{([^}]*)\}", _text())
    assert m, f"{selector} rule not found"
    return m.group(1)


def _resolve(value: str, tok: dict):
    """Resolve a declared CSS colour to RGB, whether it is a literal or a var().

    This indirection is the whole point of the test. An earlier version read the --warn-text
    TOKEN directly and asserted it was legible — which it always was, so reverting `.g-chip` back
    to the hardcoded #e8c07e that caused the bug left the test GREEN. Mutation testing caught it.
    Reading what the selector actually declares is what makes this measure the page instead of
    measuring the palette.
    """
    value = value.strip()
    var = re.match(r"var\((--[a-z0-9-]+)\)$", value)
    if var:
        assert var.group(1) in tok, f"{value} refers to a token that is not defined"
        return _hex_to_rgb(tok[var.group(1)])
    lit = re.match(r"#[0-9a-fA-F]{3,8}$", value)
    assert lit, f"unexpected colour form: {value!r}"
    return _hex_to_rgb(value)


def _declared(selector: str, prop: str) -> str:
    m = re.search(rf"(?<![\w-]){prop}:\s*([^;]+);", _rule(selector))
    assert m, f"{selector} declares no {prop}"
    return m.group(1)


def _tint_alpha(selector: str, prop: str):
    """The composited alpha of a `color-mix(… N%, transparent)` background, or None if solid."""
    m = re.search(rf"(?<![\w-]){prop}:color-mix\(in srgb, var\((--[a-z0-9-]+)\) ([\d.]+)%, transparent\)",
                  _rule(selector))
    assert m, f"{selector} has no tinted {prop}"
    return m.group(1), float(m.group(2)) / 100


# Selectors whose text sits on their own tinted background. Nothing here is hardcoded about
# WHICH colour is used — it is read out of the rule, so a revert to a literal is caught.
TEXT_ON_TINT = [(".g-chip", "--panel"), (".refine-error", "--panel")]


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("selector,surface", TEXT_ON_TINT)
def test_text_on_a_tinted_ground_is_readable(theme, selector, surface):
    """The regression that started this. `.g-chip` is the guardrails list, and in light theme it
    measured 1.59:1 — pale amber on near-white."""
    tok = _tokens(theme)
    tint_token, alpha = _tint_alpha(selector, "background")
    ground = blend(_hex_to_rgb(tok[tint_token]), alpha, _hex_to_rgb(tok[surface]))
    fg = _resolve(_declared(selector, "color"), tok)
    ratio = contrast(fg, ground)
    assert ratio >= TEXT_MIN, (
        f"{selector} text in {theme} theme is {ratio:.2f}:1 against its own tinted "
        f"background — WCAG needs {TEXT_MIN}:1"
    )


@pytest.mark.parametrize("theme", THEMES)
def test_the_signal_tokens_would_not_have_been_safe_as_text(theme):
    """Why --good-text/--warn-text exist at all, asserted so nobody 'simplifies' them away by
    pointing the text rules back at --good/--warn. In light theme --warn is 2.15:1 on white: the
    naive fix for this bug would have left it just as unreadable."""
    tok = _tokens(theme)
    if theme != "light":
        pytest.skip("the constraint this documents only binds in light theme")
    on_white = contrast(_hex_to_rgb(tok["--warn"]), _hex_to_rgb(tok["--panel"]))
    assert on_white < TEXT_MIN, (
        "light --warn now passes as text on --panel; if that is deliberate, this test and the "
        "token comment both need revisiting"
    )


@pytest.mark.parametrize("theme", THEMES)
def test_the_recommended_vendor_border_is_visible(theme):
    """This border is the only thing marking which vendor was recommended, so it carries
    information and owes the 3:1 UI minimum. As a 40% tint over a white card it was 1.37:1."""
    tok = _tokens(theme)
    m = re.search(r"\.iam-vendor-card\.recommended\{([^}]*)\}", _text())
    assert m, ".iam-vendor-card.recommended not found"
    body = m.group(1)
    assert "border-color:var(--good)" in body, (
        "the recommended-vendor border must be solid --good, not a tint — a tint of it measured "
        "1.37:1 on a white card"
    )
    ratio = contrast(_hex_to_rgb(tok["--good"]), _hex_to_rgb(tok["--panel"]))
    assert ratio >= UI_MIN, f"recommended border is {ratio:.2f}:1 in {theme} theme"


# --------------------------------------------------------------------------- no literals left

@pytest.mark.parametrize(
    "literal,token",
    [(r"rgba\(52, ?201, ?138", "--good"), (r"rgba\(224, ?162, ?60", "--warn")],
)
def test_the_signal_hues_are_not_hardcoded_anywhere(literal, token):
    """Comments are stripped first: the explanatory comments deliberately name these literals to
    record what was removed, and matching those would make this test pass on its own prose."""
    body = _strip_comments(_text())
    hits = re.findall(literal, body)
    assert not hits, (
        f"{len(hits)} raw {token} literal(s) remain — a literal cannot follow the light-theme "
        f"override, which is exactly how this bug happened"
    )


def test_flow_category_palette_is_deliberately_left_alone():
    """FLOW_CATS is a CATEGORICAL palette (Client/Edge/Compute/Data/AI/Ops) whose 'data' and 'ai'
    hues coincide with --good/--warn by accident. Pointing them at the signal tokens would turn
    the Data category dark green in light theme for no reason — the same mistake as treating
    --accent2 as a spare colour when it is the confidence channel. Asserted so the next sweep for
    'leftover literals' doesn't helpfully convert them."""
    m = re.search(r"const FLOW_CATS = \{(.*?)\n\};", _text(), re.S)
    assert m, "FLOW_CATS not found"
    body = m.group(1)
    assert "'#34c98a'" in body and "'#e0a23c'" in body, (
        "FLOW_CATS should keep its own literals — it is a category palette, not a signal one"
    )
    assert "var(--good)" not in body and "var(--warn)" not in body


def test_confidence_dot_uses_signal_tokens_not_text_tokens():
    """A filled dot is not read text, so it takes --good/--warn (and --muted for low), not the
    text-safe partners — using the darker text tokens here would mute the signal for no gain."""
    m = re.search(r"const confColor = ([^;]*);", _text())
    assert m, "confColor not found"
    body = m.group(1)
    for expected in ("var(--good)", "var(--warn)", "var(--muted)"):
        assert expected in body, f"confidence dot should use {expected}"
