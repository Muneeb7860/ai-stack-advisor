"""landing.html: the Minimalist Modern design system, applied to the landing surface only.

Scope decision, made with the user and worth recording because two separate design reviews and an
implementation plan all pushed the other way: this system is applied to landing.html and NOT to
index.html.

Why. Both design systems reviewed were, by their own component inventories, landing-page systems —
hero, stats, features, pricing tiers, testimonials, final CTA — and both scored themselves ~9.8/10
for marketing surfaces against ~7.5/10 for the dashboard. The app had just reached a coherent
identity (dark, technical, canvas-first, progressively disclosed) through four decisions the user
approved; re-skinning it would have reversed them to fix a problem the interface audit did not
find.

Three specific things the accompanying implementation plan got wrong, all verified against the
repo before this work started:
  * "Collapse the 19 unrolled sections into 4 tiers" — already shipped; sections default to
    collapsed with only the stack grid open.
  * "--accent2: #4D7CFF as a gradient endpoint" — --accent2 is the CONFIDENCE channel
    (.conf::before, .card-conf-medium), used 16 times. Repurposing it would silently break the
    confidence signal on every card.
  * "Estimated Cost" in the hero — the engine produces no single total, and
    test_hero_does_not_invent_a_single_cost_figure exists to stop one being invented.

The gradient question resolves by surface rather than by compromise: the de-genericize pass
flattened the APP's decorative gradients because they read as generic AI-tool output. A landing
page has the opposite job — it needs a signature. Different surface, different rule, and the tests
below hold both halves.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LANDING = ROOT / "landing.html"
INDEX = ROOT / "index.html"


def _landing() -> str:
    return LANDING.read_text(encoding="utf-8")


# ------------------------------------------------------------------ typography

def test_display_face_is_loaded_and_mapped():
    """Calistoga is the one genuinely new face — Inter and JetBrains Mono were already loaded in
    exactly the roles this system specifies."""
    t = _landing()
    assert "family=Calistoga" in t
    assert "--font-display:'Calistoga'" in t


def test_display_face_is_used_only_for_headlines():
    """The design system's own rule: never below 18px, because a high-contrast display serif
    breaks up at small sizes. Restricting it to h1/h2 enforces that structurally rather than by
    remembering."""
    t = _landing()
    for sel in (r"h1\{", r"h2\{"):
        m = re.search(sel + r"([^}]*)\}", t)
        assert m and "var(--font-display)" in m.group(1), f"{sel} should use the display face"
    # Body/UI text must stay on Inter.
    body = re.search(r"body\{([^}]*)\}", t)
    assert body and "var(--font)" in body.group(1)


def test_existing_font_stack_is_unchanged():
    t = _landing()
    assert "family=Inter" in t and "family=JetBrains+Mono" in t


# ------------------------------------------------------------------ palette

def test_the_landing_keeps_the_app_palette():
    """A landing page that doesn't look like the product it advertises breaks the click-through —
    someone presses "try it" and arrives somewhere visually unrelated. The design system's own
    #0052FF/#FAFAFA light palette was deliberately not adopted."""
    t = _landing()
    assert "--accent:#5b8def" in t, "must keep the app's accent"
    assert "--bg:#0a0c11" in t, "must keep the app's dark canvas"
    # Checked against the :root DECLARATIONS with comments stripped. Two earlier attempts failed
    # here: the first searched the whole file, the second scoped to :root — both matched the hex
    # inside the CSS comment that explains why the colour wasn't adopted. Testing my own prose
    # instead of the code is the recurring way these string assertions go wrong.
    root = re.search(r":root\{(.*?)\n  \}", t, re.S)
    assert root, ":root token block not found"
    tokens = re.sub(r"/\*.*?\*/", "", root.group(1), flags=re.S)
    assert "#0052FF" not in tokens.upper(), "the design system's own accent must not be adopted"
    assert "#FAFAFA" not in tokens.upper(), "the design system's light canvas must not be adopted"


def test_the_signature_gradient_is_built_from_the_app_accent():
    t = _landing()
    m = re.search(r"--accent-grad:linear-gradient\([^;]*\);", t)
    assert m, "--accent-grad not found"
    assert "var(--accent)" in m.group(0), "the gradient must start from the product's own accent"


# --------------------------------------------- gradients: landing yes, app no

def test_landing_uses_the_gradient_on_primary_ctas():
    t = _landing()
    for sel in (r"\.btn-primary\{", r"\.nav-cta\{"):
        m = re.search(sel + r"([^}]*)\}", t)
        assert m and "var(--accent-grad)" in m.group(1), f"{sel} should carry the signature gradient"


def test_the_app_gradient_flattening_is_untouched():
    """The other half of the surface distinction. This asserts from the landing-page test file on
    purpose: it is where someone would come to 'make the app match the landing page', and this is
    the note that should stop them."""
    t = INDEX.read_text(encoding="utf-8")
    for sel in (r"button\.primary\{", r"\.mode-head h1 \.hl-accent\{"):
        m = re.search(sel + r"([^}]*)\}", t, re.S)
        assert m and "linear-gradient" not in m.group(1), \
            "index.html's decorative gradients stay flattened — the de-genericize decision stands"


def test_the_confidence_channel_token_was_not_repurposed():
    """The implementation plan proposed --accent2 as a gradient endpoint. It is the confidence
    channel, and repurposing it would break the signal on every card."""
    t = INDEX.read_text(encoding="utf-8")
    assert "border-left-color:var(--accent2)" in t
    assert re.search(r"\.conf::before\{[^}]*background:var\(--accent2\)", t)


# ------------------------------------------------------------------ motion

def test_entrance_motion_has_a_failsafe():
    """Non-negotiable for this pattern. Hiding content and waiting for an observer means that if
    the observer never fires, the page is permanently blank below the hero — the worst failure a
    landing page can have, and silent. Verified as a real risk, not theoretical:
    IntersectionObserver did not fire at all in the browser used to build this."""
    t = _landing()
    assert "IntersectionObserver" in t
    m = re.search(r"setTimeout\(function\(\)\{(.*?)\}, (\d+)\);", t, re.S)
    assert m, "no reveal failsafe found"
    assert int(m.group(2)) <= 2000, "the failsafe must fire promptly, not eventually"


def test_the_failsafe_does_not_depend_on_transitions():
    """The failsafe went through three versions, each defeated by the next thing measured:

      1. add .in  -> reveals via a CSS transition, and a context with a dead observer is often one
         with dead transitions too (hidden/throttled tab).
      2. also remove js-motion -> the cascade then says opacity:1, but a transition ALREADY in
         flight keeps running and holds the old value. Six staggered elements sat frozen at
         opacity 0 while reporting playState 'running'.
      3. inline transition:none + opacity/transform -> cancels running transitions outright, and
         inline styles cannot be lost to a cascade change.

    A last line of defence must not depend on machinery that could itself be broken. Verified in a
    hidden tab where transitions freeze and requestAnimationFrame never fires: all 13 elements
    visible, zero running transitions."""
    t = _landing()
    m = re.search(r"setTimeout\(function\(\)\{(.*?)\}, \d+\);", t, re.S)
    body = m.group(1)
    assert "classList.remove('js-motion')" in body, "must drop the class that hides content"
    assert "style.transition = 'none'" in body, "must cancel transitions already in flight"
    assert "style.opacity = '1'" in body, "must set the value inline, not via the cascade"
    # Ordering matters: cancelling the transition has to happen before the value is set.
    assert body.index("style.transition") < body.index("style.opacity")


def test_the_failsafe_yields_to_a_working_observer():
    """A page whose observer works should keep its scroll animation, not have it cancelled a
    second in."""
    t = _landing()
    m = re.search(r"setTimeout\(function\(\)\{(.*?)\}, \d+\);", t, re.S)
    assert "if (document.querySelector('.reveal.in')) return;" in m.group(1)


def test_hidden_state_is_opt_in_from_javascript():
    """The base .reveal state is VISIBLE; only the js-motion class (added by script) hides it. So
    a no-script or script-error path renders fully readable rather than blank."""
    t = _landing()
    m = re.search(r"\.reveal\{([^}]*)\}", t)
    assert m and "opacity:1" in m.group(1), ".reveal must default to visible"
    m2 = re.search(r"\.js-motion \.reveal\{([^}]*)\}", t)
    assert m2 and "opacity:0" in m2.group(1), "only the JS-added class may hide content"


def test_reduced_motion_is_honoured():
    t = _landing()
    assert "prefers-reduced-motion" in t
    block = re.search(r"@media \(prefers-reduced-motion: reduce\)\{(.*?)\n  \}", t, re.S)
    assert block, "reduced-motion block not found"
    assert "animation:none" in block.group(1) or "animation-iteration-count:1" in block.group(1)


def test_pulsing_dot_exists_for_the_live_badge():
    t = _landing()
    assert "@keyframes pulse-dot" in t
    assert "animation:pulse-dot" in t


# ------------------------------------------------------------------ accuracy

def test_the_advertised_test_count_is_not_stale():
    """Unrelated to the theme, but wrong on a page whose whole pitch is rigour: it advertised 521
    passing tests. Asserted as a range so this fails loudly when it drifts again rather than
    needing an exact edit on every merge."""
    t = _landing()
    m = re.search(r"(\d+) passing regression tests", t)
    assert m, "the test-count claim was not found"
    claimed = int(m.group(1))
    assert claimed >= 900, f"landing.html advertises {claimed} tests; the suite is far larger"
