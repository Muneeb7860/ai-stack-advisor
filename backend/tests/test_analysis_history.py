"""
Regression tests for Phase 4 of the Enterprise-shell plan: a localStorage-backed "recent
analyses" list in the sidebar.

All three entry modes (wizard, freetext, upload) converge on `setAnalysis(text,
detectSignals(text))`, and detectSignals is a pure function of `text` alone — so storing just
`{id, text, ts}` per history entry is enough to exactly reconstruct any past analysis. The
save hook lives inside setAnalysis() itself (see test_review_findings.py's
test_every_analysis_path_goes_through_one_funnel for the "exactly one funnel" contract this
must not violate), so every creation path AND every "reopen a past entry" replay saves/reorders
for free.

Unlike test_inference_overrides.py/test_review_findings.py, which stub `localStorage` as a
no-op (getItem always returns null — they aren't testing persistence), these tests stub a REAL
in-memory localStorage so round-trip read/write can actually be asserted.
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

# Same stub shape as test_inference_overrides.py's _STUBS, except localStorage is a real
# in-memory Map-backed object instead of a no-op, and renderRecommendations/attachRefineUI are
# no-op'd the same way (this suite tests the history-save funnel, not full DOM rendering).
_STUBS = r"""
const fs = require('fs');
const src = fs.readFileSync(INDEX_PATH, 'utf8');
const dummyEl = { style:{}, classList:{add(){},remove(){},toggle(){}}, addEventListener(){},
  setAttribute(){}, getAttribute:()=>null, appendChild(){}, removeChild(){}, click(){}, focus(){},
  querySelector:()=>null, querySelectorAll:()=>[], innerHTML:'', textContent:'', value:'',
  scrollIntoView(){} };
const kbMatch = src.match(/id="stackKbData"[^>]*>([\s\S]*?)<\/script>/);
const kbNode = Object.assign({}, dummyEl, { textContent: kbMatch ? kbMatch[1] : '{}' });
global.window = { location:{search:''}, addEventListener(){}, matchMedia:()=>({matches:false,addEventListener(){}}) };
global.document = { documentElement:dummyEl, body:dummyEl, querySelector:()=>dummyEl,
  querySelectorAll:()=>[], createElement:()=>dummyEl, addEventListener(){},
  getElementById:(id)=> id === 'stackKbData' ? kbNode : dummyEl };
global.navigator = { clipboard:{} };
// Real in-memory localStorage (not the no-op stub other test files use) so history
// persistence can actually be round-tripped.
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
renderRecommendations = function(){};
attachRefineUI = undefined;
global.alert = function(){};

const inputNode = Object.assign({}, dummyEl, { value: '' });
global.document.getElementById = (id) => id === 'input' ? inputNode
  : id === 'stackKbData' ? kbNode : dummyEl;
function runAnalyze(text){ inputNode.value = text; analyze(); }
"""


def _js(body: str):
    return run_node_json(f"const INDEX_PATH = {str(INDEX_HTML)!r};\n" + _STUBS + "\n" + body)


# --------------------------------------------------------------------------- basic round-trip

@requires_node
def test_saving_an_analysis_and_reading_it_back():
    out = _js("""
      runAnalyze("A customer support chatbot for an e-commerce company.");
      const hist = getAnalysisHistory();
      console.log(JSON.stringify({count: hist.length, text: hist[0] && hist[0].text}));
    """)
    assert out["count"] == 1
    assert out["text"] == "A customer support chatbot for an e-commerce company."


@requires_node
def test_history_caps_at_20_oldest_dropped():
    out = _js("""
      for (let i = 0; i < 21; i++) { runAnalyze("Distinct analysis number " + i); }
      const hist = getAnalysisHistory();
      console.log(JSON.stringify({
        count: hist.length,
        newestIsLast: hist[0].text === "Distinct analysis number 20",
        oldestDropped: !hist.some(e => e.text === "Distinct analysis number 0"),
      }));
    """)
    assert out["count"] == 20
    assert out["newestIsLast"] is True
    assert out["oldestDropped"] is True


@requires_node
def test_reanalyzing_the_same_text_moves_it_to_front_not_duplicated():
    out = _js("""
      runAnalyze("Text A");
      runAnalyze("Text B");
      runAnalyze("Text A");
      const hist = getAnalysisHistory();
      console.log(JSON.stringify({
        count: hist.length,
        front: hist[0].text,
        countOfA: hist.filter(e => e.text === "Text A").length,
      }));
    """)
    assert out["count"] == 2, "re-running the same text must not duplicate the entry"
    assert out["front"] == "Text A"
    assert out["countOfA"] == 1


# ------------------------------------------------------------------------- delete / clear

@requires_node
def test_delete_history_entry_removes_only_that_one():
    out = _js("""
      runAnalyze("Keep me");
      runAnalyze("Delete me");
      const hist = getAnalysisHistory();
      const toDelete = hist.find(e => e.text === "Delete me");
      deleteHistoryEntry(toDelete.id);
      const after = getAnalysisHistory();
      console.log(JSON.stringify({count: after.length, remaining: after.map(e => e.text)}));
    """)
    assert out["count"] == 1
    assert out["remaining"] == ["Keep me"]


@requires_node
def test_clear_analysis_history_empties_the_list():
    out = _js("""
      runAnalyze("One");
      runAnalyze("Two");
      clearAnalysisHistory();
      console.log(JSON.stringify({count: getAnalysisHistory().length}));
    """)
    assert out["count"] == 0


# --------------------------------------------------------------------- reopen replays cleanly

@requires_node
def test_open_history_entry_replays_via_set_analysis_not_a_new_code_path():
    """openHistoryEntry must reuse setAnalysis(text, detectSignals(text)) — the same funnel
    every other entry mode goes through — not touch the rule engine independently."""
    out = _js("""
      runAnalyze("Enterprise platform with PostgreSQL and Python.");
      runAnalyze("A completely different analysis.");
      const hist = getAnalysisHistory();
      const original = hist.find(e => e.text.includes("PostgreSQL"));
      openHistoryEntry(original.id);
      console.log(JSON.stringify({
        reloadedText: inputNode.value,
        // reopening re-saves via setAnalysis -> saveAnalysisHistoryEntry, bumping it to front
        frontAfterReopen: getAnalysisHistory()[0].text,
      }));
    """)
    assert out["reloadedText"] == "Enterprise platform with PostgreSQL and Python."
    assert out["frontAfterReopen"] == "Enterprise platform with PostgreSQL and Python."


# -------------------------------------------------------- doesn't break the one-funnel contract

def test_set_analysis_signature_and_last_raw_signals_assignment_count_unchanged():
    """Static regression lock mirroring test_review_findings.py's
    test_every_analysis_path_goes_through_one_funnel — the history-save hook must live INSIDE
    setAnalysis's existing body as a plain function call, not as a new assignment to
    lastRawSignals or a signature change, or that test (and this one) breaks."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "function setAnalysis(text, rawSignals, opts){" in html
    assignments = re.findall(r"^\s*(?:let )?lastRawSignals = ", html, re.M)
    assert len(assignments) == 2
    body_start = html.index("function setAnalysis(text, rawSignals, opts){")
    body_end = html.index("\n}\n", body_start)
    body = html[body_start:body_end]
    assert "saveAnalysisHistoryEntry(text)" in body, "the save hook must live inside setAnalysis's body"
