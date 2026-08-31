"""Harness Readiness score history — implements docs/harness-engineering/HARNESS_HISTORY_SCOPE.md.

Third and smallest piece of the harness-engineering direction, after the audit itself
(test_harness_readiness_feature.py) and the optional evidence upload
(test_harness_evidence_upload.py). Before this, a completed audit existed only until the user
navigated away — which made the rubric's own "fix your lowest component, then re-audit" loop
impossible to actually follow in the product.

Like test_analysis_history.py (and unlike most Node-harness suites here, which stub localStorage
as a no-op), these tests use a REAL in-memory localStorage so persistence can be round-tripped.

The most important test in this file is test_identical_scores_are_not_deduplicated: harness
history deliberately does NOT de-dupe, unlike analysis_history, and that divergence is the kind
of thing a future reader could "fix" into a bug by pattern-matching on the neighbouring code.
"""
import shutil
from pathlib import Path

import pytest

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
  querySelector:()=>null, querySelectorAll:()=>[], innerHTML:'', textContent:'', value:'',
  scrollIntoView(){} };
global.window = { location:{search:''}, addEventListener(){}, matchMedia:()=>({matches:false,addEventListener(){}}) };
global.document = { documentElement:dummyEl, body:dummyEl, querySelector:()=>dummyEl,
  querySelectorAll:()=>[], createElement:()=>dummyEl, addEventListener(){},
  getElementById:()=>dummyEl };
global.navigator = { clipboard:{} };
const _store = {};
global.localStorage = {
  getItem: (k) => (k in _store ? _store[k] : null),
  setItem: (k, v) => { _store[k] = String(v); },
  removeItem: (k) => { delete _store[k]; },
};
global.fetch = () => Promise.resolve({ ok:false });
global.URL = { createObjectURL:()=>'', revokeObjectURL(){} };
for (const b of src.split('<script>').slice(1).map(b => b.split('</script>')[0])) {
  try { (0, eval)(b); } catch (e) {}
}
// Helper: save an audit with the given per-component answers, as haFinish would.
function saveAudit(answers){
  const result = scoreHarnessAudit(answers);
  saveHarnessAuditEntry(result, answers);
  return result;
}
const FULL = {system_of_record:2, tools:2, verification:2, guardrails:1, observability:1};
"""


def _js(body: str):
    return run_node_json(f"const INDEX_PATH = {str(INDEX_HTML)!r};\n" + _STUBS + "\n" + body)


# --------------------------------------------------------------------------- basic round-trip

@requires_node
def test_saving_an_audit_and_reading_it_back():
    out = _js("""
      saveAudit(FULL);
      const h = getHarnessHistory();
      console.log(JSON.stringify({count: h.length, total: h[0].total, band: h[0].band, answers: h[0].answers}));
    """)
    assert out["count"] == 1
    assert out["total"] == 8
    assert out["band"] == "Real harness exists"
    assert out["answers"] == {
        "system_of_record": 2, "tools": 2, "verification": 2, "guardrails": 1, "observability": 1,
    }


@requires_node
def test_raw_per_component_answers_are_stored_not_just_the_total():
    """The whole point of storing answers: per-component deltas later, without re-running."""
    out = _js("""
      saveAudit({system_of_record:3, tools:0, verification:1, guardrails:0, observability:2});
      console.log(JSON.stringify(getHarnessHistory()[0].answers));
    """)
    assert out["tools"] == 0
    assert out["system_of_record"] == 3


@requires_node
def test_newest_entry_is_first():
    out = _js("""
      saveAudit({system_of_record:0, tools:0, verification:0, guardrails:0, observability:0});
      saveAudit({system_of_record:3, tools:3, verification:3, guardrails:3, observability:3});
      console.log(JSON.stringify(getHarnessHistory().map(e => e.total)));
    """)
    assert out == [15, 0]


# ------------------------------------------------------- the deliberate no-de-dup divergence

@requires_node
def test_identical_scores_are_not_deduplicated():
    """THE load-bearing divergence from analysis_history (which DOES de-dupe by identical text).
    Two identical scores months apart are two real data points — collapsing them would destroy
    the exact signal this feature exists to show ("we've been stuck at 8 all quarter"). A future
    reader pattern-matching on the neighbouring analysis-history code could easily "fix" this
    into a bug; this test is what stops that."""
    out = _js("""
      saveAudit(FULL);
      saveAudit(FULL);
      saveAudit(FULL);
      const h = getHarnessHistory();
      console.log(JSON.stringify({count: h.length, totals: h.map(e => e.total)}));
    """)
    assert out["count"] == 3
    assert out["totals"] == [8, 8, 8]


# ---------------------------------------------------------------------------------- the cap

@requires_node
def test_history_caps_at_ten_oldest_dropped():
    """11 saved, 10 kept. The oldest (observability:0, the very first) must be the one dropped —
    asserted via the surviving sequence, not just the count, so a cap that trimmed the wrong end
    would still fail. (HARNESS_HISTORY_MAX itself isn't referenced here: it's a `const`, and
    `const` declared inside an indirect eval stays in that eval's lexical scope rather than
    becoming a global the way `function` declarations do — the value is asserted statically
    below instead.)"""
    out = _js("""
      for (let i = 0; i < 11; i++) {
        saveAudit({system_of_record:0, tools:0, verification:0, guardrails:0, observability: i % 4});
      }
      const h = getHarnessHistory();
      console.log(JSON.stringify({count: h.length, totals: h.map(e => e.total)}));
    """)
    assert out["count"] == 10
    # Saved observability values were i%4 for i=0..10 -> 0,1,2,3,0,1,2,3,0,1,2; newest first,
    # with the oldest (i=0, total 0) dropped.
    assert out["totals"] == [2, 1, 0, 3, 2, 1, 0, 3, 2, 1]


def test_history_cap_constant_is_ten():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "const HARNESS_HISTORY_MAX = 10;" in text


# ------------------------------------------------------------------------------- delta math

@requires_node
def test_delta_reports_improvement_regression_and_omits_unchanged():
    out = _js("""
      const prev = {total: 5, answers: {system_of_record:1, tools:1, verification:1, guardrails:1, observability:1}};
      const cur  = {total: 7, answers: {system_of_record:3, tools:1, verification:0, guardrails:1, observability:2}};
      console.log(JSON.stringify(haComputeDeltas(cur, prev)));
    """)
    assert out["totalDelta"] == 2
    moved = {d["name"]: [d["from"], d["to"]] for d in out["changed"]}
    assert moved == {
        "System of record": [1, 3],           # improved
        "Feedback and verification": [1, 0],  # regressed — must still be reported
        "Observability and memory": [1, 2],   # improved
    }
    # tools and guardrails were unchanged at 1 — deliberately omitted so every rendered line means something
    assert "Tools" not in moved
    assert "Guardrails and permissions" not in moved


@requires_node
def test_delta_is_null_with_no_previous_audit():
    out = _js("""
      console.log(JSON.stringify(haComputeDeltas({total: 5, answers: {}}, null)));
    """)
    assert out is None


@requires_node
def test_first_ever_audit_renders_no_history_block():
    """Nothing to compare against — an empty 'no history yet' card would be noise on the one
    screen the user is actually trying to read."""
    out = _js("""
      let display = 'unset';
      const card = { set style(v){}, get style(){ return { set display(v){ display = v; }, get display(){ return display; } }; }, innerHTML: '' };
      const styleObj = { display: 'unset' };
      const card2 = { style: styleObj, innerHTML: '' };
      global.document.getElementById = (id) => id === 'haHistoryCard' ? card2 : dummyEl;
      haRenderHistory([], null);
      console.log(JSON.stringify({display: card2.style.display, html: card2.innerHTML}));
    """)
    assert out["display"] == "none"
    assert out["html"] == ""


# ------------------------------------------------------------------------------- robustness

@requires_node
def test_corrupt_localStorage_returns_empty_list_rather_than_throwing():
    out = _js("""
      localStorage.setItem('harness_history', 'not valid json{{{');
      console.log(JSON.stringify(getHarnessHistory()));
    """)
    assert out == []


@requires_node
def test_clear_history_empties_the_list():
    out = _js("""
      saveAudit(FULL);
      global.document.getElementById = () => null;  // haRenderHistory no-ops without the card
      clearHarnessHistory();
      console.log(JSON.stringify(getHarnessHistory()));
    """)
    assert out == []


# ------------------------------------------------------------------------------- DOM wiring

def test_history_card_element_exists_on_the_results_screen():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="haHistoryCard"' in text


def test_hafinish_reads_history_before_saving_so_the_delta_is_against_the_prior_audit():
    """Ordering bug this locks out: saving first then reading would compare the new entry
    against itself, making every delta zero."""
    text = INDEX_HTML.read_text(encoding="utf-8")
    start = text.index("function haFinish(){")
    section = text[start:start + 3000]
    read_at = section.index("const priorEntries = getHarnessHistory();")
    save_at = section.index("saveHarnessAuditEntry(result, haAnswers);")
    assert read_at < save_at
