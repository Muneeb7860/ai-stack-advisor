"""
User authority over heuristic inferences.

detectExclusions() and detectKnownTech() are keyword heuristics. They drive real changes to the
output — an exclusion can remove a whole category, an ownership assumption can add a "your team
already knows X" claim and raise a card's confidence — and they will sometimes be wrong. So the
user gets the final say, and before any override is applied they are told exactly which
recommendations that one change alters, computed by diffing the two results rather than warning
generically that "results may differ".

The override layer is frontend-only (it is UI state over the engine), so most of this runs the
real index.html under Node. The sentence-boundary fix is in the shared detector and is asserted
against both engines.
"""
import re
import shutil
from pathlib import Path

import pytest

from app.rule_engine import detect_known_tech
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
global.window = { location:{search:''}, addEventListener(){}, matchMedia:()=>({matches:false,addEventListener(){}}) };
global.document = { documentElement:dummyEl, body:dummyEl, querySelector:()=>dummyEl,
  querySelectorAll:()=>[], createElement:()=>dummyEl, addEventListener(){},
  getElementById:(id)=> id === 'stackKbData' ? kbNode : dummyEl };
global.navigator = { clipboard:{} };
global.localStorage = { getItem:()=>null, setItem(){}, removeItem(){} };
global.fetch = () => Promise.resolve({ ok:false });
global.URL = { createObjectURL:()=>'', revokeObjectURL(){} };
for (const b of src.split('<script>').slice(1).map(b => b.split('</script>')[0])) {
  try { (0, eval)(b); } catch (e) {}
}
// renderRecommendations touches the DOM heavily; the override path is what is under test.
// (Function declarations DO reach globalThis through indirect eval, so these take effect;
// top-level `let` state does not, which is why the tests read it back via __inferenceState().)
renderRecommendations = function(){};
attachRefineUI = undefined;
global.alert = function(){};

// analyze() reads the requirement from the DOM — give it a real input node to read.
const inputNode = Object.assign({}, dummyEl, { value: '' });
const _getById = global.document.getElementById;
global.document.getElementById = (id) => id === 'input' ? inputNode
  : id === 'stackKbData' ? kbNode : dummyEl;
function runAnalyze(text){ inputNode.value = text; analyze(); }
"""


def _js(body: str):
    return run_node_json(f"const INDEX_PATH = {str(INDEX_HTML)!r};\n" + _STUBS + "\n" + body)


@requires_node
def test_override_removes_the_inference_without_editing_the_requirement():
    """The user is overriding the ENGINE'S READING, not their own text — the raw signal read must
    survive so the override stays visible and reversible."""
    out = _js("""
      runAnalyze("Enterprise platform, high traffic. We must not use Kubernetes.");
      const withExclusion = __inferenceState().lastSignals;
      global.confirm = () => true;
      toggleInference('excluded', 'kubernetes');
      const st = __inferenceState();
      console.log(JSON.stringify({
        rawStillHasIt: !!st.lastRawSignals.excluded.kubernetes,
        effectiveWith: !!withExclusion.excluded.kubernetes,
        effectiveWithout: !!st.lastSignals.excluded.kubernetes,
      }));
    """)
    assert out["rawStillHasIt"] is True, "the raw read must not be mutated"
    assert out["effectiveWith"] is True
    assert out["effectiveWithout"] is False


@requires_node
def test_warning_names_the_specific_cards_the_change_alters():
    """A generic "this may change your results" would be useless — the point is that the user can
    see the consequence of this one toggle before accepting it."""
    out = _js("""
      runAnalyze("Enterprise platform, large organization, high traffic. We must not use Kubernetes.");
      let shown = null;
      global.confirm = (m) => { shown = m; return false; };
      toggleInference('excluded', 'kubernetes');
      console.log(JSON.stringify({dialog: shown}));
    """)
    dialog = out["dialog"]
    assert "Containers / Orchestration" in dialog, "must name the affected card"
    assert "→" in dialog, "must show from → to"
    assert "Kubernetes" in dialog, "must show the value that comes back"


@requires_node
def test_declining_the_warning_changes_nothing():
    """Authority means the user decides — declining must leave both the override state and the
    recommendations exactly as they were."""
    out = _js("""
      runAnalyze("Enterprise platform, large organization, high traffic. We must not use Kubernetes.");
      const before = __inferenceState().lastRecommendations.containers.v;
      global.confirm = () => false;
      toggleInference('excluded', 'kubernetes');
      const st = __inferenceState();
      console.log(JSON.stringify({
        before, after: st.lastRecommendations.containers.v,
        overrideLeftBehind: Object.keys(st.signalOverrides.excluded).length,
      }));
    """)
    assert out["before"] == out["after"]
    assert out["overrideLeftBehind"] == 0, "a declined toggle must not leave override state behind"


@requires_node
def test_accepting_applies_exactly_what_was_promised():
    out = _js("""
      runAnalyze("Enterprise platform, large organization, high traffic. We must not use Kubernetes.");
      const before = __inferenceState().lastRecommendations.containers.v;
      global.confirm = () => true;
      toggleInference('excluded', 'kubernetes');
      console.log(JSON.stringify({before, after: __inferenceState().lastRecommendations.containers.v}));
    """)
    assert "not Kubernetes" in out["before"]
    assert "Kubernetes (EKS/GKE/AKS" in out["after"], "the promised change must actually happen"


@requires_node
def test_toggle_is_reversible():
    out = _js("""
      runAnalyze("Enterprise platform, large organization, high traffic. We must not use Kubernetes.");
      global.confirm = () => true;
      const start = __inferenceState().lastRecommendations.containers.v;
      toggleInference('excluded', 'kubernetes');
      toggleInference('excluded', 'kubernetes');
      console.log(JSON.stringify({start, back: __inferenceState().lastRecommendations.containers.v}));
    """)
    assert out["start"] == out["back"]


@requires_node
def test_rationale_only_changes_are_reported_not_swallowed():
    """Withdrawing a "your team already knows X" claim often leaves the pick identical and changes
    only the reasoning. Reporting that as "no changes" would make the warning wrong in exactly the
    case it exists for."""
    out = _js("""
      runAnalyze("We run Kubernetes in production today for our enterprise platform.");
      let shown = null;
      global.confirm = (m) => { shown = m; return false; };
      toggleInference('known', 'kubernetes');
      console.log(JSON.stringify({dialog: shown}));
    """)
    assert "No recommendation changes" not in out["dialog"], (
        "the skill claim is withdrawn by this toggle — saying nothing changes is false"
    )
    assert "reasoning" in out["dialog"]


@requires_node
def test_overrides_reset_when_the_requirement_changes():
    """An override is a decision about one sentence — silently carrying it to a different
    requirement would apply it to text the user never judged."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert re.search(
        r"if \(text !== lastRequirementText\) signalOverrides = \{ excluded: \{\}, known: \{\} \};", html
    ), "analyze() must clear overrides when the requirement text changes"


@requires_node
def test_both_inference_kinds_are_shown_and_switchable():
    """An inference the user cannot see is one they cannot correct — both heuristic reads are
    rendered as chips, including ones already switched off."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "renderChipRow('excluded'" in html
    assert "renderChipRow('known'" in html
    assert "toggleInference('${kind}','${k}')" in html
    assert "line-through" in html, "an overridden inference stays visible rather than disappearing"


# ------------------------------------------------------------------ shared detector fix
@pytest.mark.parametrize("text,expected", [
    # Found by using the feature: the after-window ran into the NEXT sentence, so a sentence that
    # EXCLUDES Kubernetes was read as evidence the team runs it.
    ("We must not use Kubernetes. We run PostgreSQL in production today.", {"postgres": True}),
    ("We run Kubernetes in production today.", {"kubernetes": True}),
    ("Should we use Kubernetes? We have never used it before.", {}),
])
def test_experience_windows_do_not_cross_sentence_boundaries(text, expected):
    assert detect_known_tech(text) == expected


@requires_node
def test_sentence_clipping_matches_in_both_engines():
    out = _js("""
      console.log(JSON.stringify(detectKnownTech("We must not use Kubernetes. We run PostgreSQL in production today.")));
    """)
    assert out == {"postgres": True}
