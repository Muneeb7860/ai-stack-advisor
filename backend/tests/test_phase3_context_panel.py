"""
Regression tests for the Enterprise v2.0 shell — Phase 3: route refine/ask into
#contextPanel (see the plan: "retarget attachRefineToCard's DOM target, keep
the mechanism").

Mechanism preserved exactly: same "zone" element, same data-card-key /
data-category, same child ids (refineResult-${cardKey}, askBox-${cardKey},
askThread-${cardKey}, askInput-${cardKey}, askToggleBtn-${cardKey}) — every
downstream function (onRefineClick, onAskClick, applyRefinementToAllCards,
...) still finds them by id, untouched. What changed is only WHERE the zone
is appended (#contextPanelBody instead of the card) and that only one card's
zone is visible at a time (.context-zone.active), driven by two new
functions: openContextPanelFor(cardKey) / closeContextPanel().

Plain string/regex checks against index.html, matching every other migration
test file in this suite — no Node/browser needed. Live-browser verification
(opening the panel from a card's Refine/Ask button, Escape closing it, a
second analysis run not leaking the first run's zones) was done manually
during the session that made this change, not re-verified by these tests.
"""
import re
from pathlib import Path

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"


def _text():
    return INDEX_HTML.read_text(encoding="utf-8")


def _fn_body(name, text):
    m = re.search(r"function " + re.escape(name) + r"\(([^)]*)\)\{(.*?)\n\}", text, re.S)
    assert m, f"{name} not found"
    return m.group(2)


# ------------------------------------------------------------- panel markup

def test_context_panel_has_a_header_and_body_wrapper():
    text = _text()
    m = re.search(r'<aside id="contextPanel">(.*?)</aside>', text, re.S)
    assert m, "contextPanel markup not found"
    body = m.group(1)
    assert 'id="contextPanelTitle"' in body
    assert 'onclick="closeContextPanel()"' in body
    assert 'id="contextPanelBody"' in body


def test_context_panel_open_class_toggles_display():
    text = _text()
    m = re.search(r"#contextPanel\{([^}]*)\}", text)
    assert m and "display:none" in m.group(1)
    m2 = re.search(r"#contextPanel\.open\{([^}]*)\}", text)
    assert m2 and "display:flex" in m2.group(1)


# --------------------------------------------------------- mechanism intact

def test_attach_refine_to_card_still_targets_the_same_ids():
    text = _text()
    body = _fn_body("attachRefineToCard", text)
    for expected_id in (
        "refineResult-${cardKey}", "askBox-${cardKey}", "askThread-${cardKey}",
        "askInput-${cardKey}", "askToggleBtn-${cardKey}",
    ):
        assert expected_id in body, f"{expected_id} missing from attachRefineToCard"


def test_trigger_buttons_stay_on_the_card_not_in_the_panel():
    """The two buttons must still be appended to `card` directly (not to the zone that moves
    into the panel) — otherwise there'd be nothing left on the card to click to open a given
    card's drawer content in the first place."""
    text = _text()
    body = _fn_body("attachRefineToCard", text)
    assert "card.appendChild(triggerRow)" in body
    assert "document.getElementById('contextPanelBody').appendChild(zone)" in body


def test_trigger_buttons_open_the_panel_for_their_own_card_key():
    text = _text()
    body = _fn_body("attachRefineToCard", text)
    assert "openContextPanelFor('${cardKey}'); onRefineClick('${cardKey}', this)" in body
    assert "openContextPanelFor('${cardKey}'); onAskToggleClick('${cardKey}')" in body


def test_zone_carries_both_refine_zone_and_context_zone_classes():
    """applyRefinementToAllCards() selects `.refine-zone` across ALL cards at once (one
    /api/refine call can adjust several categories simultaneously) — that must keep working
    even though the zone now also carries `.context-zone` for the panel's show/hide toggle."""
    text = _text()
    body = _fn_body("attachRefineToCard", text)
    assert "zone.className = 'refine-zone context-zone';" in body
    text_all = text
    assert "document.querySelectorAll('.refine-zone')" in text_all  # applyRefinementToAllCards, unchanged


# ------------------------------------------------------- open/close functions

def test_open_context_panel_for_shows_only_the_matching_zone_and_sets_title():
    text = _text()
    body = _fn_body("openContextPanelFor", text)
    assert "z.dataset.cardKey === cardKey" in body
    assert "cardLabelByKey[cardKey]" in body
    assert "classList.add('open')" in body


def test_close_context_panel_removes_the_open_class():
    text = _text()
    body = _fn_body("closeContextPanel", text)
    assert "classList.remove('open')" in body


def test_global_escape_handler_also_closes_the_context_panel():
    text = _text()
    m = re.search(r"window\.addEventListener\('keydown', \(e\) => \{\s*if \(e\.key === 'Escape'\) \{(.*?)\}\s*\}\);", text, re.S)
    assert m, "global Escape keydown handler not found"
    assert "closeContextPanel();" in m.group(1)


# ------------------------------------------------------ re-render doesn't leak

def test_attach_refine_ui_clears_the_panel_body_and_label_map_before_rebuilding():
    """#contextPanelBody lives OUTSIDE #results, so unlike a card's own children (which
    renderRecommendations() rebuilds from scratch on every analysis run), a second run would
    silently accumulate the previous run's zones underneath the new ones without this."""
    text = _text()
    body = _fn_body("attachRefineUI", text)
    assert "document.getElementById('contextPanelBody').innerHTML = '';" in body
    assert "cardLabelByKey = {};" in body
    assert "closeContextPanel();" in body


# -------------------------------------------------- css specificity regression

def test_context_zone_override_has_higher_specificity_than_refine_zone():
    """Regression lock for a real specificity bug caught in this pass: a plain `.context-zone`
    rule (specificity 0,1,0) declared BEFORE `.refine-zone{margin-top:11px;...}` (also 0,1,0,
    declared later in the file) would LOSE that cascade fight — later same-specificity rule
    wins regardless of which one looks like the "override". Using the compound selector
    `.refine-zone.context-zone` (0,2,0) beats it unconditionally, independent of declaration
    order."""
    text = _text()
    assert re.search(r"\.refine-zone\.context-zone\{[^}]*display:none", text)
    assert re.search(r"\.refine-zone\.context-zone\.active\{[^}]*display:block", text)
