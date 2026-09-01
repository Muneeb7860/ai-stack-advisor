"""Two signals that were parsed and then ignored.

Both are the same defect as the concurrency one fixed earlier: the engine visibly extracts
something from the requirement and then answers as though it had not been said. A reader who
states a fact precisely and gets the same output as someone who omitted it has been shown evidence
the tool understood them, and then not acted on.

**Team size.** Only `smallTeam` looked at numbers, and only across a hand-written span — the
literal strings "2 engineers" through "6 engineers", plus 1-12 for "N people" and "team of N".
`largeTeam` looked at no numbers at all. So "We have 60 engineers" fired neither signal. "solo
developer" fired neither either, because only "solo founder" was in the list — the most common way
a one-person team is described did nothing.

**Delivery timeline.** `detect_timeline` has always parsed this correctly, including rejecting
"retain audit logs for 12 months" as a retention rule rather than a deadline. Nothing read the
result. Now surfaced as a tradeoff rather than routed into a signal, deliberately: a tight deadline
is not evidence a project is an MVP — an enterprise with a six-week regulatory deadline is still an
enterprise — so folding the two together would reclassify the project instead of informing it.

The team-size thresholds are judgement calls, named so they can be argued with, with a deliberate
gap between them: a stated 20 is neither small nor large, and forcing it into one would be a claim
the requirement does not support.
"""
import json
import re
import shutil
from pathlib import Path

import pytest

from app.rule_engine import (
    TEAM_LARGE_MIN,
    TEAM_SMALL_MAX,
    detect_signals,
    detect_team_size,
    recommend_stack,
)
from tests.node_harness import run_node_json

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

BASE = "An e-commerce API for a retail company."


def _sig(extra):
    return detect_signals(f"{BASE} {extra}")


# ------------------------------------------------------------------------ team size

@pytest.mark.parametrize("phrase,n", [
    ("We have 60 engineers.", 60),
    ("A team of 60.", 60),
    ("50 developers.", 50),
    ("Team of 4.", 4),
    ("2 engineers.", 2),
    ("A 200-engineer company.", 200),
    ("15 devs.", 15),
])
def test_a_stated_team_size_is_extracted(phrase, n):
    assert detect_team_size(phrase) == n


def test_the_largest_stated_number_wins():
    """"A platform team of 8 inside a 200-engineer org" is a 200-engineer org; the 8 is a detail
    within it. Reading the first number instead returned 8 AND fired smallTeam alongside largeTeam
    (which "platform team" triggers) — two contradictory signals from one sentence."""
    s = _sig("A platform team of 8 inside a 200-engineer org.")
    assert detect_team_size("a platform team of 8 inside a 200-engineer org") == 200
    assert not (s["smallTeam"] and s["largeTeam"]), "both team-size signals fired at once"
    assert s["largeTeam"] is True


def test_the_hyphenated_form_is_read():
    """"200-engineer org" is written with a hyphen at least as often as a space, and missing it is
    what caused the contradiction above."""
    assert detect_team_size("a 200-engineer org") == 200


@pytest.mark.parametrize("n,small,large", [
    (1, True, False),
    (TEAM_SMALL_MAX, True, False),
    (TEAM_SMALL_MAX + 1, False, False),
    (TEAM_LARGE_MIN - 1, False, False),
    (TEAM_LARGE_MIN, False, True),
    (500, False, True),
])
def test_the_thresholds_are_applied_with_a_gap_between_them(n, small, large):
    """The gap is deliberate. A stated 20 is neither a small team nor a large one, and forcing it
    into one would be a claim the requirement does not support."""
    s = _sig(f"We have {n} engineers.")
    assert s["smallTeam"] is small and s["largeTeam"] is large


@pytest.mark.parametrize("phrase", [
    "solo developer", "solo engineer", "single developer", "just me",
])
def test_one_person_team_phrasings_fire_small_team(phrase):
    """Only "solo founder" was listed, so the most common ways of saying this did nothing."""
    assert _sig(f"Built by a {phrase}.")["smallTeam"] is True


@pytest.mark.parametrize("phrase", ["large team", "many teams", "multiple teams", "platform team"])
def test_the_existing_keywords_still_fire_without_a_number(phrase):
    """Additive: the numeric path is OR'd with the keywords, never substituted for them."""
    assert _sig(f"We have a {phrase}.")["largeTeam"] is True


def test_a_stated_team_size_changes_the_recommendation():
    """The point. Before this, "60 engineers" produced the same stack as saying nothing."""
    plain = recommend_stack(BASE)["recommendations"]
    large = recommend_stack(f"{BASE} We have 60 engineers.")["recommendations"]
    differing = [
        k for k in plain
        if isinstance(plain[k], dict) and "v" in plain[k] and plain[k]["v"] != large[k].get("v")
    ]
    assert differing, "a stated team of 60 changes nothing — the number is parsed and ignored"


# ------------------------------------------------------------------------- timeline

@pytest.mark.parametrize("phrase,expect", [
    ("We must launch in 6 weeks.", "6 weeks"),
    ("Deadline is 4 months.", "4 months"),
    ("Ship the MVP in one quarter.", "one quarter"),
])
def test_a_stated_deadline_leads_the_tradeoffs(phrase, expect):
    first = recommend_stack(f"{BASE} {phrase}")["recommendations"]["tradeoffs"][0]
    assert first["d"].startswith("Delivery window")
    assert expect in first["d"]
    assert expect in first["why"], "the stated window must be quoted back, not just categorised"


def test_no_deadline_leaves_the_tradeoffs_unchanged():
    assert not recommend_stack(BASE)["recommendations"]["tradeoffs"][0]["d"].startswith("Delivery window")


@pytest.mark.parametrize("phrase,marker", [
    ("We must launch in 6 weeks.", "Cut scope"),
    ("Deadline is 4 months.", "Sequence the hard parts"),
    ("Delivery in 2 years.", "build for change"),
])
def test_the_advice_differs_by_how_much_time_there_is(phrase, marker):
    """Three bands, because "you have a deadline" is not advice. A six-week window and a two-year
    window imply opposite choices, and a single message for both would be true of neither."""
    assert marker in recommend_stack(f"{BASE} {phrase}")["recommendations"]["tradeoffs"][0]["rec"]


def test_a_retention_period_is_still_not_read_as_a_deadline():
    """detect_timeline's existing disqualifier, re-asserted because this change is the first thing
    to consume its output — a regression there would now surface as an invented delivery window in
    the tradeoffs rather than as an unused value."""
    recs = recommend_stack(f"{BASE} Retain audit logs for 12 months.")["recommendations"]
    assert not recs["tradeoffs"][0]["d"].startswith("Delivery window")


def test_a_deadline_does_not_reclassify_the_project_as_an_mvp():
    """The design decision. An enterprise with a six-week regulatory deadline is still an
    enterprise; routing the timeline into startupMvp would have been the easy version of this and
    would have changed what the project IS rather than noting a constraint on it."""
    s = _sig("Enterprise rollout, SOC 2 required. We must launch in 6 weeks.")
    assert s["timeline"] is not None
    assert s["startupMvp"] is False, "a tight deadline must not make an enterprise project an MVP"
    assert s["enterprise"] is True


# ----------------------------------------------------------------------- dual engine

@requires_node
def test_both_engines_agree_on_both_signals():
    script = INDEX.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]
    cases = [
        BASE,
        f"{BASE} We have 60 engineers.",
        f"{BASE} A platform team of 8 inside a 200-engineer org.",
        f"{BASE} Built by a solo developer.",
        f"{BASE} 20 engineers.",
        f"{BASE} We must launch in 6 weeks.",
        f"{BASE} Retain audit logs for 12 months.",
    ]
    stubs = """
const d={style:{},classList:{add(){},remove(){},toggle(){},contains:()=>false},addEventListener(){},
  setAttribute(){},getAttribute:()=>null,querySelector:()=>d,querySelectorAll:()=>[],innerHTML:'',textContent:''};
global.window={innerWidth:1280,location:{search:''},addEventListener(){},matchMedia:()=>({matches:false,addEventListener(){}})};
global.document={documentElement:d,body:d,querySelector:()=>d,querySelectorAll:()=>[],
  getElementById:()=>d,createElement:()=>d,addEventListener(){}};
global.navigator={clipboard:{}};global.localStorage={getItem:()=>null,setItem(){},removeItem(){}};
global.fetch=()=>Promise.resolve({ok:false});global.URL={createObjectURL:()=>'',revokeObjectURL(){}};
global.requestAnimationFrame=(fn)=>fn();
"""
    body = (
        "const cases = " + json.dumps(cases) + ";\n"
        "console.log(JSON.stringify(cases.map(c => {"
        "  const s = detectSignals(c);"
        "  return {teamSize: s.teamSize, small: s.smallTeam, large: s.largeTeam,"
        "          timeline: s.timeline ? s.timeline.text : null,"
        "          firstTradeoff: pickTradeoffs(s)[0].d};"
        "})));"
    )
    js = run_node_json(stubs + script + "\n" + body)
    for text, got in zip(cases, js):
        py = detect_signals(text)
        assert got["teamSize"] == py["teamSize"], f"teamSize differs on {text!r}"
        assert got["small"] == py["smallTeam"], f"smallTeam differs on {text!r}"
        assert got["large"] == py["largeTeam"], f"largeTeam differs on {text!r}"
        py_tl = (py["timeline"] or {}).get("text")
        assert got["timeline"] == py_tl, f"timeline differs on {text!r}"
        assert got["firstTradeoff"] == recommend_stack(text)["recommendations"]["tradeoffs"][0]["d"], (
            f"leading tradeoff differs on {text!r}"
        )


def test_the_thresholds_are_named_constants_in_both_engines():
    """A literal in one engine and a constant in the other is how they drift apart on every
    requirement naming a number between the two values."""
    text = INDEX.read_text(encoding="utf-8")
    for name, value in (("TEAM_SMALL_MAX", TEAM_SMALL_MAX), ("TEAM_LARGE_MIN", TEAM_LARGE_MIN)):
        m = re.search(r"const " + name + r" = (\d+);", text)
        assert m, f"{name} is not a named constant in index.html"
        assert int(m.group(1)) == value, f"{name} differs: JS {m.group(1)} vs Python {value}"
