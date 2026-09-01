"""Results hierarchy restructure — implements docs/design/RESULTS_HIERARCHY_SCOPE.md.

The problem this fixes, from the code rather than impressions:
  1. Every section rendered with a hardcoded `open`, so all 19 expanded on every analysis. The
     disclosure mechanism existed and worked; it was simply never used as disclosure.
  2. .results-hero spent the lead space echoing the user's OWN input back at them ("N signals
     detected" plus the signal chips), with the recommendation starting below it in section 1.

Three tiers, borrowed from Lighthouse — which this product already imitates correctly in its own
harness audit (score -> band -> ranked fixes) but not in its main report:
  Tier 1  the hero states the recommendation spine, not the input echo
  Tier 2  a capped, ranked "needs your attention" list
  Tier 3  everything else, collapsed

Tier 2 adds NO rule-engine output: it crosses two things the engine already computes — exit cost
(EXIT_COST_CATEGORIES) and confidence (`conf`, on every pick) — so the dual-engine parity surface
is untouched and there is nothing for the Python twin to mirror.

The scope doc named the likeliest bug in advance: sections now collapse, so a #sideNav click must
OPEN its target as well as scroll to it, or it appears to do nothing. That has its own test below.
"""
import re
import shutil
from pathlib import Path

import pytest

from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)


def _text() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _main_script() -> str:
    return _text().split("<script>")[2].split("</script>")[0]


_STUBS = r"""
const dummyEl = { style:{}, classList:{add(){},remove(){},toggle(){}}, addEventListener(){},
  setAttribute(){}, getAttribute:()=>null, appendChild(){}, removeChild(){}, click(){}, focus(){},
  querySelector:()=>null, querySelectorAll:()=>[], innerHTML:'', textContent:'', value:'' };
global.window = { location:{search:''}, addEventListener(){}, matchMedia:()=>({matches:false,addEventListener(){}}) };
global.document = { documentElement:dummyEl, body:dummyEl, querySelector:()=>dummyEl,
  querySelectorAll:()=>[], getElementById:()=>dummyEl, createElement:()=>dummyEl, addEventListener(){} };
global.navigator = { clipboard:{} };
global.localStorage = { getItem:()=>null, setItem(){}, removeItem(){} };
global.fetch = () => Promise.resolve({ ok:false });
global.URL = { createObjectURL:()=>'', revokeObjectURL(){} };
"""


def _js(body: str):
    return run_node_json(_STUBS + _main_script() + "\n" + body)


# stackCards rows are [title, pick, why, conf, ...] — only the 1st, 2nd and 4th matter here.
def _card(title, conf, pick="X"):
    return f"['{title}', '{pick}', 'why', '{conf}', 'persona', '', '']"


# ------------------------------------------------------------------ Tier 2: ranking logic

@requires_node
def test_hard_to_reverse_plus_low_confidence_ranks_first():
    """The whole point of the feature: crossing exit cost with confidence surfaces "you are being
    asked to commit to something expensive to reverse, on weak signal" — which neither field
    gives on its own, and which nothing surfaced before this."""
    out = _js(f"""
      const cards = [{_card('Caching', 'low')}, {_card('Cloud Provider', 'low')}, {_card('Primary Database(s)', 'medium')}];
      console.log(JSON.stringify(computeAttentionItems(cards).map(i => [i.title, i.rank])));
    """)
    assert out[0] == ["Cloud Provider", 1], out
    assert [i[0] for i in out] == ["Cloud Provider", "Primary Database(s)", "Caching"]


@requires_node
def test_high_confidence_picks_are_never_listed_at_any_exit_cost():
    """A short list of things that warrant attention, not a re-listing of the report. A
    well-supported pick is not a concern even when it is expensive to reverse."""
    out = _js(f"""
      const cards = [{_card('Cloud Provider', 'high')}, {_card('Primary Database(s)', 'high')}, {_card('Caching', 'high')}];
      console.log(JSON.stringify(computeAttentionItems(cards)));
    """)
    assert out == []


@requires_node
def test_low_exit_cost_low_confidence_ranks_last_but_is_still_listed():
    out = _js(f"""
      console.log(JSON.stringify(computeAttentionItems([{_card('Caching', 'low')}]).map(i => [i.title, i.rank])));
    """)
    assert out == [["Caching", 3]]


@requires_node
def test_list_is_capped():
    """An uncapped list is just the report again, which is the failure mode this restructure
    exists to avoid (the AWS Well-Architected "close the tab" problem)."""
    cards = ", ".join(_card(t, "low") for t in
                      ["Cloud Provider", "Identity & Access (IAM)", "Primary Database(s)",
                       "API Gateway / Edge", "Messaging / Streaming", "Observability"])
    out = _js(f"console.log(JSON.stringify(computeAttentionItems([{cards}]).length));")
    assert out == 4


@requires_node
def test_hard_to_reverse_flag_is_reported_per_item():
    out = _js(f"""
      const r = computeAttentionItems([{_card('Cloud Provider', 'low')}, {_card('Caching', 'low')}]);
      console.log(JSON.stringify(r.map(i => [i.title, i.hardToReverse])));
    """)
    assert out == [["Cloud Provider", True], ["Caching", False]]


@requires_node
def test_empty_and_missing_input_do_not_throw():
    out = _js("console.log(JSON.stringify([computeAttentionItems([]).length, computeAttentionItems(undefined).length]));")
    assert out == [0, 0]


@requires_node
def test_unknown_card_title_is_treated_as_cheap_to_reverse_not_crashed_on():
    """A title with no STACK_CARD_CATEGORY entry (a future card added without the map updated)
    must degrade to "not hard to reverse" rather than throwing mid-render."""
    out = _js(f"""
      const r = computeAttentionItems([{_card('Some Future Category', 'low')}]);
      console.log(JSON.stringify([r.length, r[0].hardToReverse, r[0].rank]));
    """)
    assert out == [1, False, 3]


# --------------------------------------------------------------- Tier 3: collapsed by default

def test_sections_are_no_longer_all_hardcoded_open():
    text = _text()
    assert '<details class="section-block" id="${x.id}" open>' not in text, \
        "the hardcoded `open` on every section is the thing this restructure removes"
    assert "DEFAULT_OPEN_SECTIONS" in text


def test_only_the_stack_section_opens_by_default():
    """A product decision, not a mechanical one: the stack grid is the detail behind the Tier 1
    answer, so it stays open. Everything else is one click away."""
    text = _text()
    m = re.search(r"const DEFAULT_OPEN_SECTIONS = new Set\(\[([^\]]*)\]\)", text)
    assert m, "DEFAULT_OPEN_SECTIONS not found"
    assert m.group(1).strip() == "'stack'"


def test_collapsing_did_not_remove_any_section():
    """Nothing is cut — this is a hierarchy change. Sections must all still be registered, which
    is also what keeps the existing ALL_SECTION_IDS locks in the category test files passing."""
    text = _text()
    assert text.count("  sec('") == 19


# ------------------------------------- the bug the scope doc predicted: nav into a closed section

def test_nav_links_open_their_target_section():
    """Called out in the scope doc as the likeliest bug in the whole change: with sections
    collapsed, a plain href="#id" scrolls to a closed accordion and appears to do nothing."""
    text = _text()
    assert 'onclick="openSectionFromNav(' in text, "nav links must open their target"
    assert "function openSectionFromNav(" in text


@requires_node
def test_open_section_from_nav_opens_a_details_and_returns_true():
    """Returns true so the href="#id" navigation still happens — this augments the anchor rather
    than replacing it, so the URL still carries the section and back/forward still work."""
    out = _js("""
      const el = { tagName: 'DETAILS', open: false };
      global.document.getElementById = () => el;
      const ret = openSectionFromNav('cost');
      console.log(JSON.stringify({opened: el.open, returned: ret}));
    """)
    assert out["opened"] is True
    assert out["returned"] is True


@requires_node
def test_open_section_from_nav_is_safe_when_the_target_is_missing_or_not_a_details():
    out = _js("""
      global.document.getElementById = () => null;
      const a = openSectionFromNav('nope');
      global.document.getElementById = () => ({ tagName: 'DIV' });
      const b = openSectionFromNav('sig-anchor');
      console.log(JSON.stringify([a, b]));
    """)
    assert out == [True, True]


def test_toggle_all_button_starts_as_expand_all():
    """toggleAll() derives its next action from the button's own text, so seeding it with the old
    "Collapse all" would invert the control on first click now that collapsed is the default."""
    text = _text()
    assert 'id="toggleAllBtn">Expand all<' in text


# ------------------------------------------------------------------ Tier 1: the hero leads

def test_hero_leads_with_the_recommendation_not_the_signal_count():
    text = _text()
    assert '<div class="rh-eyebrow">Recommended stack</div>' in text
    assert '<div class="rh-eyebrow">${activeSignals.length} signal' not in text, \
        "the lead space must not restate the user's own input back at them"


def test_signals_are_still_reachable_behind_a_disclosure():
    """Demoted, not removed — they are evidence for the answer, and are still one interaction
    away (plus already duplicated per-card by the existing why-this-pick inspection)."""
    text = _text()
    assert 'class="rh-evidence"' in text
    assert "signal${activeSignals.length===1?'':'s'} detected" in text


def test_hero_shows_the_stack_spine():
    text = _text()
    assert 'class="rh-spine"' in text
    for label in ("'Cloud'", "'Database'", "'Compute'"):
        assert label in text
