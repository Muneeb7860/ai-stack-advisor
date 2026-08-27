"""
Regression suite for the seven findings from the pre-merge review of this branch.

Every one of them is a defect the branch's own fixes introduced or left behind, so these tests
exist to stop the fixes from being worse than what they replaced. Where a defect had a shared
root cause (new analysis state added to one code path and not the others) the test asserts the
structural fix, not just the symptom.
"""
import re
import shutil
from pathlib import Path

import pytest

from app.rule_engine import (
    detect_exclusions,
    detect_known_tech,
    detect_signals,
    detect_timeline,
    recommend_stack,
)
from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

_STUBS = r"""
const fs = require('fs');
const src = fs.readFileSync(INDEX_PATH, 'utf8');
const dummyEl = { style:{}, classList:{add(){},remove(){},toggle(){}}, addEventListener(){},
  setAttribute(){}, getAttribute:()=>null, appendChild(){}, removeChild(){}, click(){}, focus(){},
  querySelector:()=>null, querySelectorAll:()=>[], innerHTML:'', textContent:'', value:'' };
const kbMatch = src.match(/id="stackKbData"[^>]*>([\s\S]*?)<\/script>/);
const kbNode = Object.assign({}, dummyEl, { textContent: kbMatch ? kbMatch[1] : '{}' });
const inputNode = Object.assign({}, dummyEl, { value: '' });
global.window = { location:{search:''}, addEventListener(){}, matchMedia:()=>({matches:false,addEventListener(){}}) };
global.document = { documentElement:dummyEl, body:dummyEl, querySelector:()=>dummyEl,
  querySelectorAll:()=>[], createElement:()=>dummyEl, addEventListener(){},
  getElementById:(id)=> id === 'stackKbData' ? kbNode : id === 'input' ? inputNode : dummyEl };
global.navigator = { clipboard:{} };
global.localStorage = { getItem:()=>null, setItem(){}, removeItem(){} };
global.fetch = () => Promise.resolve({ ok:false });
global.URL = { createObjectURL:()=>'', revokeObjectURL(){} };
global.alert = function(){};
for (const b of src.split('<script>').slice(1).map(b => b.split('</script>')[0])) {
  try { (0, eval)(b); } catch (e) {}
}
renderRecommendations = function(){};
attachRefineUI = undefined;
function runAnalyze(text){ inputNode.value = text; analyze(); }
"""


def _js(body: str):
    return run_node_json(f"const INDEX_PATH = {str(INDEX_HTML)!r};\n" + _STUBS + "\n" + body)


# ------------------------------------------------------------------ finding 1
@pytest.mark.parametrize("text", [
    "We need not only a website but also a mobile app.",
    "This is not just a database problem, we need real-time streaming.",
    "Latency must be no more than 200ms for the API.",
    "We want not merely a dashboard but a full analytics platform.",
])
def test_qualifying_negations_are_not_read_as_exclusions(text):
    """A negator followed by only/just/merely/more than QUALIFIES what comes next rather than
    prohibiting it. Reading these as exclusions deleted a category the user explicitly asked for,
    which is worse than the over-recommendation the exclusion mechanism exists to prevent."""
    assert detect_exclusions(text) == {}, text


def test_the_requested_category_survives_a_qualifying_negation():
    recs = recommend_stack("We need not only a website but also a mobile app.")["recommendations"]
    assert recs["frontend"].get("excluded") is not True
    assert "Not recommended" not in recs["frontend"]["v"]


def test_real_exclusions_still_work():
    """The fix must not disarm the mechanism it is narrowing."""
    assert detect_exclusions("We must not use Kubernetes.") == {"kubernetes": True}
    assert detect_exclusions("No caching is needed.") == {"cache": True}


# ------------------------------------------------------------------ finding 2
@pytest.mark.parametrize("text", [
    "We don't use Kubernetes today.",
    "We do not use Kubernetes today.",
    "We no longer use Kubernetes today.",
    "We are migrating off Kubernetes this year.",
])
def test_statements_of_non_use_are_not_read_as_ownership(text):
    """BUG-7 one phrasing over: the before-window "we don't use " does not contain "we use", so
    nothing disclaimed it, and the after-window " today" hit EXPERIENCE_AFTER."""
    assert detect_known_tech(text).get("kubernetes") is not True, text


def test_a_technology_is_never_both_excluded_and_known():
    """Contradictory state the rest of the engine has no way to resolve — the exclusion wins."""
    s = detect_signals("We don't use Kubernetes today.")
    assert s["excluded"].get("kubernetes") is True
    assert "kubernetes" not in s["known"]
    for key in s["known"]:
        assert key not in s["excluded"], f"{key} is both excluded and known"


def test_real_ownership_is_still_recognised():
    assert detect_known_tech("We run Kubernetes in production today.") == {"kubernetes": True}


# ------------------------------------------------------------------ finding 3
def test_excluded_categories_do_not_ship_a_vendor_recommendation():
    """Vendor comparisons are computed from the PRE-exclusion picks, so without suppression the
    Cloud card read "you excluded cloud hosting" directly above a starred best bet on AWS."""
    recs = recommend_stack("An internal knowledge assistant. No RAG and no cloud is needed.")["recommendations"]
    assert recs["cloud"].get("excluded") is True
    assert recs["cloud_vendor"].get("suppressed") is True
    assert recs["vector_db_vendor"].get("suppressed") is True


def test_vendor_comparisons_survive_when_nothing_is_excluded():
    recs = recommend_stack("A fintech payments platform, high traffic, PCI compliance.")["recommendations"]
    assert recs["cloud_vendor"].get("suppressed") is not True
    assert recs["cloud_vendor"]["v"]


@requires_node
def test_suppressed_vendor_toggle_renders_nothing():
    out = _js("""
      const V = [{id:'a',name:'A',cat:'c',bestFor:'b',strength:'s',drawback:'d',pricing:'p'}];
      const excluded = computeRecommendations(detectSignals("An internal knowledge assistant. No RAG and no cloud is needed."));
      const normal = computeRecommendations(detectSignals("A fintech payments platform, high traffic, PCI compliance."));
      console.log(JSON.stringify({
        excludedToggle: altToggle(V, excluded.cloudVendorPick, 'n'),
        normalToggleLength: altToggle(V, normal.cloudVendorPick, 'n').length,
        k8sOrchestratorToggle: altToggle(V, computeRecommendations(detectSignals("Enterprise platform, high traffic. We must not use Kubernetes.")).orchestratorPick, 'n'),
      }));
    """)
    assert out["excludedToggle"] == ""
    assert out["normalToggleLength"] > 0, "the fix must not suppress ordinary vendor comparisons"
    assert out["k8sOrchestratorToggle"] == "", (
        "the orchestrator table would star Kubernetes against a card that says 'not Kubernetes'"
    )


# ------------------------------------------------------------------ findings 4 + 5 (shared cause)
@requires_node
def test_every_analysis_path_goes_through_one_funnel():
    """Findings 4 and 5 were the same mistake twice: new state added to the free-text path and not
    to the diagram or override paths. A single funnel is the structural fix — asserting it here
    means a fourth path cannot reintroduce the class."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "function setAnalysis(text, rawSignals, opts){" in html

    # Exactly two assignments: the declaration, and the one inside setAnalysis. Any third means a
    # caller is setting analysis state by hand again — which is precisely how findings 4 and 5
    # happened.
    assignments = re.findall(r"^\s*(?:let )?lastRawSignals = ", html, re.M)
    assert len(assignments) == 2, (
        f"expected only the declaration and setAnalysis's assignment, found {len(assignments)}"
    )
    for caller in ["function analyze(){", "const synthesizedText ="]:
        assert caller in html


@requires_node
def test_diagram_analysis_refreshes_the_inference_state():
    """The diagram path set lastSignals/lastRecommendations but never lastRawSignals or the
    overrides, so the chips described the PREVIOUS requirement and clicking one discarded the
    diagram analysis in favour of a text-derived one."""
    out = _js("""
      global.confirm = () => true;
      runAnalyze("Enterprise platform, large organization, high traffic. We must not use Kubernetes.");
      toggleInference('excluded', 'kubernetes');
      const before = __inferenceState();

      // The diagram path synthesises its own text and calls setAnalysis with it.
      setAnalysis("Existing architecture diagram components: postgres, redis. Evaluate stack modernization.",
                  detectSignals("Existing architecture diagram components: postgres, redis. Evaluate stack modernization."));
      const after = __inferenceState();
      console.log(JSON.stringify({
        overridesBefore: Object.keys(before.signalOverrides.excluded).length,
        overridesAfter: Object.keys(after.signalOverrides.excluded).length,
        rawMatchesReport: after.lastRawSignals !== null && after.lastRawSignals.excluded !== undefined,
        rawIsFresh: JSON.stringify(after.lastRawSignals) !== JSON.stringify(before.lastRawSignals),
      }));
    """)
    assert out["overridesBefore"] == 1
    assert out["overridesAfter"] == 0, "a new requirement must start from the raw inferences"
    assert out["rawMatchesReport"] is True
    assert out["rawIsFresh"] is True, "chips must describe the requirement now on screen"


@requires_node
def test_override_invalidates_the_cached_refine_session():
    """currentAnalysisId/refineResultCache describe the recommendations that were on screen a
    moment ago. After an override they are stale, so /api/ask and /api/refine would ground on the
    recommendation the user just rejected."""
    # resetRefineSession is a function declaration, so it reaches globalThis and can be spied on;
    # currentAnalysisId is a top-level `let` and cannot be read from outside the eval's scope.
    out = _js("""
      global.confirm = () => true;
      runAnalyze("Enterprise platform, large organization, high traffic. We must not use Kubernetes.");
      let resets = 0;
      const real = resetRefineSession;
      resetRefineSession = function(){ resets++; return real.apply(this, arguments); };
      toggleInference('excluded', 'kubernetes');
      console.log(JSON.stringify({resets}));
    """)
    assert out["resets"] == 1, (
        "toggleInference must reset the refine session like every other analysis change — "
        "otherwise /api/ask and /api/refine keep grounding on the superseded analysis id"
    )


# ------------------------------------------------------------------ finding 6
@pytest.mark.parametrize("text", [
    # Caught by the disqualifier list (retention/tenure wording)...
    "Retain audit logs for 12 months.",
    "We have 3 years of transaction history to migrate.",
    "Team of 6 engineers with 10 years experience.",
    # ...and these carry no disqualifier at all, so only the positive delivery-cue requirement
    # rejects them. Without it a reporting cadence becomes a ship date.
    "We process 3 million records every 6 months.",
    "The board reviews the roadmap every 2 quarters.",
])
def test_durations_without_a_delivery_cue_are_not_deadlines(text):
    """"Retain audit logs for 12 months" was exported into the ADR as "First production release
    ships inside <= 360 days" — a retention rule turned into a commitment, inside a decision
    record someone might act on."""
    assert detect_timeline(text) is None, text


@pytest.mark.parametrize("text,days", [
    ("4 month timeline", 120),
    ("12 week delivery", 84),
    ("launch within 6 months", 180),
    ("ship in two quarters", 182),
])
def test_real_delivery_windows_are_still_parsed(text, days):
    assert detect_timeline(text)["days"] == days


# ------------------------------------------------------------------ finding 7
def test_shared_read_only_view_does_not_advertise_an_inert_control():
    """The share view renders from a stored analysis and never populates lastRawSignals, so
    toggleInference returns early — but the chips still rendered as buttons, so every click and
    keypress was a silent no-op."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    match = re.search(r"const canOverride = (.+);", html)
    assert match, "canOverride not found"
    # It must actually be derived from whether an overridable analysis is loaded — a hardcoded
    # `true` would restore the inert-button behaviour while keeping every other assertion green.
    assert "lastRawSignals" in match.group(1), (
        f"canOverride must depend on lastRawSignals, got: {match.group(1)}"
    )
    assert "if (!canOverride){" in html, "chips must render as plain labels when overriding is unavailable"
    assert "not on a shared read-only report" in html, "and must say why"
