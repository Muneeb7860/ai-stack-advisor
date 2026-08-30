"""Regression tests for 5 real gaps found in a manual "positive/alternative/negative scenario"
QA sweep against the live app in Chrome — each independently verified as a real, reproducible
bug before any fix existed:

1. "Neither Java nor Python" — "neither" was never in the negator word list, so both names were
   read as POSITIVE mentions, and the tool recommended exactly what the user said not to use.
2. "We do not want Java, nor Python" — same root cause, phrased as an active negator + "nor".
3. "Please avoid both Java and Python" — "avoid" was never a recognized negator at all.
4. EXCLUSION_TERMS had NO "languages" category whatsoever — no phrasing of "don't use Java"
   could ever exclude it, independent of how well the negation-clause regex worked.
5. "We already use Postgres, don't need ANOTHER database" — wrongly excluded the database
   category entirely, when the actual intent was "don't add a second one," the opposite of "we
   don't want a database."
6. "On-premises... no public cloud" (both s.onPrem AND ex.cloud fire on the same sentence) —
   the generic "you excluded cloud hosting" stub clobbered pickCloud's own, more useful
   on-prem-specific answer. The phrasing that gave the tool MORE information produced the LESS
   useful answer.

Asserted against BOTH engines (rule_engine.py and index.html's JS twin).
"""
import shutil
from pathlib import Path

import pytest

from app.rule_engine import detect_exclusions, recommend_stack
from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

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


def _main_script() -> str:
    return INDEX_HTML.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]


def _js(expr_body: str):
    return run_node_json(_STUBS + _main_script() + "\n" + expr_body)


NEITHER_NOR_TEXT = "We need a web application. Neither Java nor Python should be used for the backend — browser-based only."
NOT_NOR_TEXT = "We do not want Java, nor Python, for the backend."
AVOID_BOTH_TEXT = "Please avoid both Java and Python for this project."
ALREADY_HAVE_DB_TEXT = "We already use PostgreSQL in production and don't need another database added."
ONPREM_AND_NOCLOUD_TEXT = "Build a system for on-premises deployment only, no public cloud."


# ---------------------------------------------------------------------- language exclusions

@pytest.mark.parametrize("text", [NEITHER_NOR_TEXT, NOT_NOR_TEXT, AVOID_BOTH_TEXT])
def test_language_negation_phrasings_are_recognized(text):
    assert detect_exclusions(text).get("languages") is True, text


def test_neither_nor_flows_through_to_the_final_recommendation():
    """As of the follow-up "so what do I use instead?" fix, this is no longer a bare "not
    recommended" stub — it's a real, context-appropriate alternative (this text says
    "browser-based only", so JavaScript/TypeScript is the expected fit)."""
    import re as _re
    rec = recommend_stack(NEITHER_NOR_TEXT)["recommendations"]
    v = rec["languages"]["v"]
    assert rec["languages"].get("excluded") is True
    # Word-boundary check: "JavaScript" itself contains the substring "Java", so a naive
    # `"Java" not in v` would wrongly fail on the correct answer.
    assert not _re.search(r"\bJava\b", v)
    assert "Python" not in v
    assert "JavaScript" in v


def test_avoid_is_only_recognized_together_with_something_excludable():
    """"avoid" alone, with nothing after it matching an EXCLUSION_TERMS key, must not fabricate
    an exclusion out of thin air."""
    assert detect_exclusions("We want to avoid technical debt and move fast.") == {}


# ------------------------------------------------------------------------ quantity qualifier

def test_another_database_does_not_exclude_the_database_category():
    assert detect_exclusions(ALREADY_HAVE_DB_TEXT) == {}
    rec = recommend_stack(ALREADY_HAVE_DB_TEXT)["recommendations"]
    assert "excluded" not in rec["database"]["v"].lower()
    assert "PostgreSQL" in rec["database"]["v"]


@pytest.mark.parametrize("qualifier", ["another", "a second", "an additional", "a different", "one more"])
def test_quantity_qualifiers_all_prevent_a_false_exclusion(qualifier):
    text = f"We already have Redis. We don't need {qualifier} cache."
    assert detect_exclusions(text) == {}, f"{qualifier!r} should have been recognized as qualifying, not excluding"


def test_a_real_exclusion_right_after_a_quantity_qualifier_phrase_still_works():
    """The qualifier check must be scoped to the specific term match, not the whole clause —
    a genuine, unrelated exclusion elsewhere in the same clause must still register."""
    text = "We don't need another cache, and we don't want Kubernetes at all."
    ex = detect_exclusions(text)
    assert ex.get("cache") is None
    assert ex.get("kubernetes") is True


# --------------------------------------------------------------------------- on-prem precedence

def test_onprem_and_explicit_no_cloud_together_get_the_informative_onprem_answer():
    """Regression lock for the exact inconsistency found live: phrasing that trips BOTH
    s.onPrem and ex.cloud must not get the WORSE (generic, less actionable) message than
    phrasing that trips only onPrem."""
    rec = recommend_stack(ONPREM_AND_NOCLOUD_TEXT)["recommendations"]
    assert "On-premises" in rec["cloud"]["v"]
    assert "you excluded" not in rec["cloud"]["v"].lower()


def test_explicit_no_cloud_without_onprem_still_gets_the_generic_exclusion_message():
    """The guard must be specific to onPrem — a plain "we must not use any cloud provider"
    with no on-prem signal at all must still get the existing generic exclusion wording."""
    rec = recommend_stack("This must not use any cloud provider at all — pure client-side app.")["recommendations"]
    assert "you excluded" in rec["cloud"]["v"].lower()


# --------------------------------------------------------------------------- JS parity

@requires_node
@pytest.mark.parametrize("text", [NEITHER_NOR_TEXT, NOT_NOR_TEXT, AVOID_BOTH_TEXT])
def test_js_language_negation_phrasings_match_python(text):
    out = _js(f"console.log(JSON.stringify(detectExclusions({text!r})));")
    assert out.get("languages") is True


@requires_node
def test_js_another_database_does_not_exclude_the_database_category():
    out = _js(f"console.log(JSON.stringify(detectExclusions({ALREADY_HAVE_DB_TEXT!r})));")
    assert out == {}


@requires_node
def test_js_onprem_and_explicit_no_cloud_gets_the_informative_answer():
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({ONPREM_AND_NOCLOUD_TEXT!r}));
      console.log(JSON.stringify({{ cloud: rec.cloud.v }}));
    """)
    assert "On-premises" in out["cloud"]
    assert "you excluded" not in out["cloud"].lower()
