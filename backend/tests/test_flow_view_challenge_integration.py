"""Regression tests for "Challenge This Pick" in the Flow View node popover — the item
docs/challenge-this-pick-spec.md explicitly named as deferred ("Flow View nodes have their own
separate inspection popover... extending this widget there is a follow-up decision, not assumed
here").

Two kinds of check:
1. Pure-function Node-harness tests for flowNodeLabel()/flowNodeCurrentPick() and
   attachChallengeToFlowNode() itself, against a from-scratch DOM stub (NOT the shared
   single-dummyEl stub other test files in this suite use — that stub returns the SAME object
   from every createElement() call, which can't distinguish between two distinct flow-node
   zones and so can't catch the exact duplicate-zone-accumulation bug this integration has to
   avoid: showFlowPopover() runs once per popover open, not once per full render like
   attachRefineUI(), so re-opening the same node's popover must not append a second zone).
2. Static regression locks (plain regex/string checks) confirming attachChallengeToFlowNode is
   actually wired into showFlowPopover, and that it reuses buildChallengeButtonHtml/
   buildChallengeBoxHtml rather than duplicating that markup.
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


def _text():
    return INDEX_HTML.read_text(encoding="utf-8")


# A from-scratch, per-test-file DOM stub — createElement() returns a FRESH object every call
# (tracking its own dataset/innerHTML/appendChild children), and document.querySelector()
# actually scans #contextPanelBody's real children for a matching data-card-key, instead of the
# shared dummyEl pattern (one object reused for every call) other test files in this suite use.
_STUBS = r"""
const fs = require('fs');
const src = fs.readFileSync(INDEX_PATH, 'utf8');

function makeEl(tag){
  return {
    tag, dataset:{}, className:'', innerHTML:'', style:{}, children:[], appendedHtml:[],
    value:'', textContent:'', options:[],
    appendChild(child){ this.children.push(child); },
    insertAdjacentHTML(pos, html){ this.appendedHtml.push(html); },
    classList:{add(){},remove(){},toggle(){}},
    querySelector:()=>null, querySelectorAll:()=>[],
    addEventListener(){}, setAttribute(){}, getAttribute:()=>null,
  };
}
const contextPanelBody = makeEl('div');
const flowPopoverEl = makeEl('div');
const byId = { contextPanelBody, flowPopover: flowPopoverEl };

const kbMatch = src.match(/id="stackKbData"[^>]*>([\s\S]*?)<\/script>/);
const kbNode = Object.assign(makeEl('script'), { textContent: kbMatch ? kbMatch[1] : '{}' });
byId.stackKbData = kbNode;

global.window = { location:{search:''}, addEventListener(){}, matchMedia:()=>({matches:false,addEventListener(){}}) };
global.document = {
  documentElement: makeEl('html'), body: makeEl('body'),
  createElement: (tag) => makeEl(tag),
  // Memoized (unlike other test files' single-shared dummyEl, but ALSO unlike a naive "fresh
  // element every call") — the same id always resolves to the same object, so a value set on
  // an element earlier in the test is still there when production code (e.g.
  // openContextPanelFor) looks that id up again later.
  getElementById: (id) => { if (!byId[id]) byId[id] = makeEl('div'); return byId[id]; },
  querySelector: (sel) => {
    const m = sel.match(/data-card-key="([^"]+)"/);
    if (!m) return null;
    return contextPanelBody.children.find(c => c.dataset.cardKey === m[1]) || null;
  },
  querySelectorAll: () => [],
  addEventListener(){},
};
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
global.alert = function(){};
"""


def _js(body: str):
    return run_node_json(f"const INDEX_PATH = {str(INDEX_HTML)!r};\n" + _STUBS + "\n" + body)


# --------------------------------------------------------------------------- pure functions

@requires_node
def test_flow_node_label_and_pick_for_a_plain_sub_node():
    out = _js("""
      const n = {id:'cloud', title:'Cloud Provider', sub:'AWS'};
      console.log(JSON.stringify({label: flowNodeLabel(n), pick: flowNodeCurrentPick(n)}));
    """)
    assert out["label"] == "Cloud Provider"
    assert out["pick"] == "AWS"


@requires_node
def test_flow_node_label_and_pick_splits_the_dash_packed_title():
    """iam/llm/rag nodes pack their pick value into title as "Label — Value" with an empty
    `sub` (see buildCanonicalArchitectureGraph's N() calls) — must split it back out, not show
    "Identity & Access — AWS IAM" as both the panel title and the "current pick" value."""
    out = _js("""
      const n = {id:'iam', title:'Identity & Access — AWS IAM', sub:''};
      console.log(JSON.stringify({label: flowNodeLabel(n), pick: flowNodeCurrentPick(n)}));
    """)
    assert out["label"] == "Identity & Access"
    assert out["pick"] == "AWS IAM"


@requires_node
def test_flow_node_pick_falls_back_to_title_when_no_sub_and_no_dash():
    out = _js("""
      const n = {id:'guardrails', title:'Guardrails', sub:'3 layer(s)'};
      console.log(JSON.stringify({pick: flowNodeCurrentPick(n)}));
    """)
    assert out["pick"] == "3 layer(s)"


@requires_node
def test_flow_node_category_overrides_the_four_mismatched_ids():
    """FLOW_NODE_CATEGORY_OVERRIDES itself is a `const` — invisible from outside the indirect
    eval it's declared in, unlike the function declarations this file also defines — so this
    checks its effect through the real call path (attachChallengeToFlowNode -> zone.dataset.category)
    instead of reading the object directly."""
    out = _js("""
      const pop = document.getElementById('flowPopover');
      const results = {};
      for (const id of ['arch', 'computemodel', 'lang', 'db']) {
        attachChallengeToFlowNode(pop, {id, title: id, sub: 'x'});
        results[id] = document.querySelector(`.context-zone[data-card-key="flow-${id}"]`).dataset.category;
      }
      console.log(JSON.stringify(results));
    """)
    assert out == {
        "arch": "architecture",
        "computemodel": "compute",
        "lang": "languages",
        "db": "database",
    }


# --------------------------------------------------------------- attachChallengeToFlowNode

@requires_node
def test_attach_challenge_to_flow_node_creates_exactly_one_zone():
    """cardLabelByKey/cardPickByKey are `let`-declared in index.html's own script (invisible
    from outside the indirect eval that ran it), so cardLabelByKey's population is verified
    through the real production read path — openContextPanelFor(), which is exactly what a
    click on the flow-node's Challenge button actually calls."""
    out = _js("""
      const pop = document.getElementById('flowPopover');
      attachChallengeToFlowNode(pop, {id:'cloud', title:'Cloud Provider', sub:'AWS'});
      const body = document.getElementById('contextPanelBody');
      openContextPanelFor('flow-cloud');
      console.log(JSON.stringify({
        zoneCount: body.children.length,
        cardKey: body.children[0] && body.children[0].dataset.cardKey,
        category: body.children[0] && body.children[0].dataset.category,
        panelTitle: document.getElementById('contextPanelTitle').textContent,
      }));
    """)
    assert out["zoneCount"] == 1
    assert out["cardKey"] == "flow-cloud"
    assert out["category"] == "cloud"
    assert out["panelTitle"] == "Cloud Provider"


@requires_node
def test_reopening_the_same_node_popover_does_not_accumulate_a_second_zone():
    """showFlowPopover() (and therefore attachChallengeToFlowNode) runs once per popover open,
    not once per full render — a user clicking the same node twice must not leave two
    `.context-zone[data-card-key="flow-cloud"]` elements sitting in #contextPanelBody."""
    out = _js("""
      const pop = document.getElementById('flowPopover');
      const node = {id:'cloud', title:'Cloud Provider', sub:'AWS'};
      attachChallengeToFlowNode(pop, node);
      attachChallengeToFlowNode(pop, node);
      attachChallengeToFlowNode(pop, node);
      const body = document.getElementById('contextPanelBody');
      console.log(JSON.stringify({ zoneCount: body.children.length, buttonAppends: pop.appendedHtml.length }));
    """)
    assert out["zoneCount"] == 1
    # The trigger button DOES need to be re-added every time (showFlowPopover wipes
    # pop.innerHTML on every open) — only the #contextPanelBody zone must stay singular.
    assert out["buttonAppends"] == 3


@requires_node
def test_attach_challenge_to_flow_node_applies_the_category_override():
    out = _js("""
      const pop = document.getElementById('flowPopover');
      attachChallengeToFlowNode(pop, {id:'db', title:'Primary Database', sub:'PostgreSQL'});
      const body = document.getElementById('contextPanelBody');
      console.log(JSON.stringify({ category: body.children[0].dataset.category }));
    """)
    assert out["category"] == "database"


@requires_node
def test_attach_challenge_to_flow_node_button_uses_the_flow_prefixed_card_key():
    out = _js("""
      const pop = document.getElementById('flowPopover');
      attachChallengeToFlowNode(pop, {id:'cache', title:'Caching', sub:'Redis'});
      console.log(JSON.stringify({ buttonHtml: pop.appendedHtml[0] }));
    """)
    assert "flow-cache" in out["buttonHtml"]
    assert "challenge-toggle-btn" in out["buttonHtml"]


# --------------------------------------------------------------------- static regression lock

def test_show_flow_popover_calls_attach_challenge_to_flow_node():
    text = _text()
    body_start = text.index("function showFlowPopover(id){")
    body_end = text.index("\n}\n", body_start)
    body = text[body_start:body_end]
    assert "attachChallengeToFlowNode(pop, n)" in body


def test_attach_challenge_to_flow_node_reuses_the_shared_builders_not_new_markup():
    text = _text()
    body_start = text.index("function attachChallengeToFlowNode(pop, n){")
    body_end = text.index("\n}\n", body_start)
    body = text[body_start:body_end]
    assert "buildChallengeButtonHtml(cardKey)" in body
    assert "buildChallengeBoxHtml(cardKey, category)" in body
    # Must not hand-roll a second copy of the button/box HTML.
    assert "challenge-toggle-btn icon-btn" not in body
    # cardPickByKey is `let`-scoped and unreadable directly from a test's Node harness (see the
    # docstrings above) — this is the regression lock for its population, verified by source
    # instead of by reading the runtime value.
    assert "cardPickByKey[cardKey] = flowNodeCurrentPick(n)" in body
    assert "cardLabelByKey[cardKey] = flowNodeLabel(n)" in body
    assert re.search(r"if\s*\(document\.querySelector\(`\.context-zone\[data-card-key=", body), \
        "must guard against re-appending a zone for a node whose popover was opened before"
