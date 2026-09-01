"""Density pass: retire redundant nested borders, and add architecture to the results hero.

Audit item 4, deliberately sequenced last so spacing wasn't tuned against a layout that was about
to change underneath it.

The finding that shaped this pass: four blocks (.rag-pick, .opt-item, .gov-block, .cost-row) each
sit INSIDE a .card that already carries a background, border and shadow, and each added its own
background AND border on top — a bordered box inside a bordered box. The obvious fix is to drop
the inner border and let the --surface/--panel tonal shift carry the separation.

That fix would have silently broken light mode. In the light theme --surface and --panel were
BOTH #ffffff, so the border was the only thing distinguishing those blocks there; removing it
would have made them invisible on a white card. The light theme's own comment claims "every token
below has a real, checked light equivalent", which wasn't true of --surface — it was collapsed
onto --panel. Fixed the token first, then removed the borders.
"""
import re
from pathlib import Path

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"

# The four blocks that were bordered boxes inside a bordered card.
NESTED_BLOCKS = ["rag-pick", "opt-item", "gov-block", "cost-row"]


def _text() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    m = re.search(r"\." + re.escape(selector) + r"\{([^}]*)\}", _text())
    assert m, f".{selector} rule not found"
    return m.group(1)


def _light_theme_block() -> str:
    m = re.search(r'\[data-theme="light"\]\s*\{(.*?)\n  \}', _text(), re.S)
    assert m, "light theme block not found"
    return m.group(1)


# ---------------------------------------------------- the token that made the fix safe

def test_light_theme_surface_is_distinct_from_panel():
    """The load-bearing precondition. With both at #ffffff, removing the inner borders would have
    made these blocks invisible in light mode — a white box on a white card with nothing between
    them. This is what makes the tonal separation real in BOTH themes rather than dark only."""
    block = _light_theme_block()
    surface = re.search(r"--surface:(#[0-9a-fA-F]{3,8})", block)
    panel = re.search(r"--panel:(#[0-9a-fA-F]{3,8})", block)
    assert surface and panel, "light theme must define both --surface and --panel"
    assert surface.group(1).lower() != panel.group(1).lower(), \
        "light --surface must differ from --panel, or the borderless blocks vanish"


def test_dark_theme_surface_is_also_distinct_from_panel():
    """Held already, but asserted so a future palette edit can't collapse them the way light's
    were collapsed."""
    m = re.search(r":root\{(.*?)\}", _text(), re.S)
    assert m
    root = m.group(1)
    surface = re.search(r"--surface:(#[0-9a-fA-F]{3,8})", root)
    panel = re.search(r"--panel:(#[0-9a-fA-F]{3,8})", root)
    assert surface and panel
    assert surface.group(1).lower() != panel.group(1).lower()


# ------------------------------------------------------------- the borders themselves

def test_nested_blocks_no_longer_carry_their_own_border():
    for sel in NESTED_BLOCKS:
        body = _rule(sel)
        assert "border:1px solid" not in body, \
            f".{sel} is inside a .card that already has a border — it must not add a second one"


def test_nested_blocks_keep_the_surface_shift_that_replaced_the_border():
    """Removing the border only works because the background still changes. Dropping both would
    merge these blocks into the card entirely."""
    for sel in NESTED_BLOCKS:
        assert "background:var(--surface)" in _rule(sel), \
            f".{sel} must keep its surface background — it is now the only separation"


def test_the_parent_card_keeps_its_own_border():
    """The pass removes the INNER border of a nested pair, not chrome generally — the card is the
    outer boundary and still needs one."""
    body = _rule("card")
    assert "border:1px solid var(--border)" in body


# --------------------------------------------------------------- hero: architecture added

def test_hero_spine_leads_with_architecture():
    """Architecture is the decision the other three hang off — you pick a shape before you pick
    what runs it."""
    text = _text()
    m = re.search(r"const heroSpine = \[\n\s*(.*?)\n\s*\]", text, re.S)
    assert m, "heroSpine not found"
    spine = m.group(1)
    assert spine.index("'Architecture'") < spine.index("'Cloud'")
    for label in ("'Architecture'", "'Cloud'", "'Database'", "'Compute'"):
        assert label in spine


def test_hero_does_not_invent_a_single_cost_figure():
    """The engine produces separate compute/database/LLM bands on purpose, and some read "Not
    applicable — capex, not opex". Summing those strings into one headline number would invent a
    precision the product deliberately refuses to claim — so cost stays in its own section where
    its per-category caveats travel with it. Asserted because a plausible-sounding request for an
    "estimated run-rate" in the hero is exactly how that precision would get invented later."""
    text = _text()
    m = re.search(r"const heroSpine = \[\n\s*(.*?)\n\s*\]", text, re.S)
    spine = m.group(1)
    assert "costEstimate" not in spine
    assert "Cost" not in spine
