"""The Review view — a third rendering of an analysis that already exists, for a review board.

The feature is deliberately small: every number on it was already computed, and three of the four
panels were previously visible only inside a file you had to click Export to get. What these tests
pin is that it stayed small, and the one new thing on it behaves.

Two properties are load-bearing:

* The decision records are the exporter's. `AdrExport.buildExports` renders ADRs; an earlier plan
  for this view proposed formatting the analysis into ADRs a second time for display, which is the
  same mistake as generating a second architecture diagram — two renderers drift, and the one on
  screen is the one nobody exports.
* A sign-off is a sign-off OF something. The ledger is keyed on the deck's own content, so a
  changed analysis starts unsigned. Four ticks carried over from an architecture that no longer
  exists is worse than no ledger, because it looks like governance happened.
"""
import json
import re
import shutil
from pathlib import Path

import pytest

from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

# Two requirements that resolve to genuinely different stacks — regulated/on-prem against a
# cloud-native MVP — so "different analysis" means different picks, not different prose.
REQ_A = (
    "Internal enterprise knowledge assistant with RAG over our Confluence policy documents. "
    "We use Azure and Entra ID, Python, and PostgreSQL. 500 concurrent users. Team of 6 "
    "engineers. SOC2 compliance required."
)
REQ_B = (
    "Public e-commerce storefront for a seed-stage startup. Two engineers, three month runway, "
    "React and Node. No AI features. Deploy on AWS."
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
// A real store, not a null stub: the sign-off tests are about what survives a write.
const _store = {};
global.localStorage = {
  getItem:(k)=> Object.prototype.hasOwnProperty.call(_store, k) ? _store[k] : null,
  setItem:(k,v)=>{ _store[k] = String(v); },
  removeItem:(k)=>{ delete _store[k]; },
};
global.fetch = () => Promise.resolve({ ok:false });
global.URL = { createObjectURL:()=>'', revokeObjectURL(){} };
for (const b of src.split('<script>').slice(1).map(b => b.split('</script>')[0])) {
  try { (0, eval)(b); } catch (e) {}
}
function deckFor(req){
  const s = detectSignals(req);
  return arbBuildDeck(computeRecommendations(s), s);
}
"""


def _js(body: str):
    return run_node_json(f"const INDEX_PATH = {str(INDEX_HTML)!r};\n" + _STUBS + "\n" + body)


def _text() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


@requires_node
def test_the_deck_shows_the_exporters_records_not_a_second_rendering():
    """Number and title, record for record, against buildExports' own output for the same input.

    A second ADR renderer would pass a "the panel is not empty" test and fail this one.
    """
    out = _js(
        f"const s = detectSignals({REQ_A!r});\n"
        """
        const rec = computeRecommendations(s);
        const {recommendations, omitted} = mapAppPicksToKb(rec, s);
        const exported = window.AdrExport.buildExports({
          kb: getKbData(), input: buildAdrInput(s), recommendations, omitted});
        const deck = arbBuildDeck(rec, s);
        console.log(JSON.stringify({
          fromExporter: exported.adrs.map(a => [a.number, a.title]),
          onDeck: deck.records.map(r => [r.number, r.title]),
          tokensMatch: deck.totalTokens === exported.totalTokens,
        }));
        """
    )
    assert out["onDeck"], "the deck rendered no decision records at all"
    assert out["onDeck"] == out["fromExporter"]
    assert out["tokensMatch"], "the deck recomputed an innovation-token total of its own"


@requires_node
def test_the_cost_panel_never_adds_the_bands_up():
    """Three bands, each carrying its own caveat, and no fourth row totalling them.

    One of these bands routinely reads "Not applicable - capex, not opex" for an on-prem pick.
    Adding an amortised hardware budget to a monthly cloud bill produces a run-rate figure the
    engine has no basis for, which is the same call test_hero_does_not_invent_a_single_cost_figure
    makes about the hero - and that test only guards heroSpine, so it would pass no matter what
    this view rendered.
    """
    out = _js(
        f"const onprem = detectSignals('Regulated payments platform, strictly on-premise, no cloud. Java and Oracle. 200 staff.');\n"
        """
        const rows = arbCostRows(computeRecommendations(onprem));
        console.log(JSON.stringify({
          labels: rows.map(r => r.label),
          values: rows.map(r => r.value),
          everyRowHasItsCaveat: rows.every(r => typeof r.detail === 'string' && r.detail.length > 40),
        }));
        """
    )
    assert out["labels"] == ["Compute", "Database", "LLM API"]
    assert out["everyRowHasItsCaveat"]
    # The capex band is the one that makes summing incoherent, so prove it is really in play here.
    assert any("capex" in v for v in out["values"]), out["values"]
    joined = " ".join(out["labels"]).lower()
    for banned in ("total", "run-rate", "run rate", "combined", "all-in"):
        assert banned not in joined


@requires_node
def test_a_different_analysis_gets_a_different_signoff_key():
    out = _js(
        f"const a = deckFor({REQ_A!r}), b = deckFor({REQ_B!r});\n"
        """
        console.log(JSON.stringify({
          a: arbFingerprint(a), b: arbFingerprint(b),
          stableAcrossRebuilds: arbFingerprint(a) === arbFingerprint(deckFor(%s)),
        }));
        """ % repr(REQ_A)
    )
    assert out["a"] != out["b"]
    assert out["stableAcrossRebuilds"], "the same analysis produced two different sign-off keys"


@requires_node
def test_the_signoff_key_survives_the_clock():
    """The same decisions on a different day are the same decisions.

    renderAdr stamps "- Date: <today>" into every record's markdown. Fingerprinting the record
    objects wholesale would therefore invalidate every sign-off at midnight - a ledger that
    appears to work and quietly empties itself once a day, which is the failure mode you would
    not notice until an audit.
    """
    out = _js(
        f"const first = deckFor({REQ_A!r});\nconst before = arbFingerprint(first);\n"
        """
        const recordFields = [...new Set(first.records.flatMap(r => Object.keys(r)))].sort();
        const RealDate = Date;
        global.Date = class extends RealDate {
          constructor(...a){ a.length ? super(...a) : super('2031-07-19T12:00:00Z'); }
          static now(){ return new RealDate('2031-07-19T12:00:00Z').getTime(); }
        };
        const after = arbFingerprint(deckFor(%s));
        const stampMoved = window.AdrExport.buildExports({
          kb: getKbData(), input: {}, recommendations: []}).bundle.includes('2031-07-19');
        global.Date = RealDate;
        console.log(JSON.stringify({before, after, stampMoved, recordFields}));
        """ % repr(REQ_A)
    )
    assert out["stampMoved"], "the Date stub never took effect, so this test proved nothing"
    assert out["before"] == out["after"]
    # Belt and braces, and the half that actually bites: hashing a projection is only safe while
    # the projection stays date-free. Carrying the exporter's ADR objects through unchanged would
    # put `markdown` - and the date stamped inside it - one careless `Object.keys` away from the
    # hash, without today's clock moving far enough for the assertion above to notice.
    assert out["recordFields"] == ["number", "title", "tokens"], out["recordFields"]


@requires_node
def test_signoffs_do_not_follow_you_to_a_different_analysis():
    out = _js(
        f"const a = deckFor({REQ_A!r});\n"
        """
        // ARB_SIGNOFF_ROLES is a `const` inside an eval'd <script> block, so unlike a function
        // declaration it does not reach this scope. The ids are named here and pinned against
        // the source in test_the_signoff_roles_are_the_four_this_suite_signs_off_with.
        const ROLES = ['security','architecture','cloudops','data'];
        const fpA = arbFingerprint(a);
        ROLES.forEach(id => arbSaveSignoff(fpA, id, true));
        const b = deckFor(%s);
        const fpB = arbFingerprint(b);
        console.log(JSON.stringify({
          signedOnA: Object.keys(arbLoadSignoffs(fpA)).length,
          signedOnB: Object.keys(arbLoadSignoffs(fpB)).length,
          roles: ROLES,
        }));
        """ % repr(REQ_B)
    )
    assert out["signedOnA"] == len(out["roles"]) == 4
    assert out["signedOnB"] == 0, "sign-offs carried over to a different architecture"


@requires_node
def test_the_coverage_gaps_reach_the_deck():
    """The `omitted` ledger is the reason this view earns its place: mapAppPicksToKb has always
    computed "on the report, but not in the decision pack", and it was only ever readable inside
    a downloaded file."""
    out = _js(
        f"const deck = deckFor({REQ_A!r});\n"
        """
        console.log(JSON.stringify({
          categories: deck.gaps.map(g => g.category),
          allExplained: deck.gaps.every(g => typeof g.detail === 'string' && g.detail.length > 30),
        }));
        """
    )
    assert len(out["categories"]) >= 5
    # DNS has no KB representation at all and is named as a gap unconditionally - if the deck ever
    # stops carrying `omitted`, this is the first thing to disappear.
    assert "DNS" in out["categories"]
    assert out["allExplained"], "a gap was listed with no explanation of why it is a gap"


@requires_node
def test_a_brownfield_analysis_says_why_the_pack_is_empty():
    """Guardrails-only mode proposes no stack, so there is nothing to write a decision record
    about. An empty panel there would read like a bug; the deck says why instead.

    This one found a real defect rather than pinning an intended behaviour. computeRecommendations
    computes a full stack in every mode - computeVisibleSections is what narrows the report - so
    the first version of arbBuildDeck handed mapAppPicksToKb those picks and produced seventeen
    decision records for a stack the user was never shown. renderTokenBudgetHtml already carried
    the same guard for the same reason.
    """
    out = _js(
        """
        const s = detectSignals('We already have AI built and running in production. We only need our guardrails reviewed - PII redaction and prompt-injection defence on the existing chatbot.');
        const deck = arbBuildDeck(computeRecommendations(s), s);
        console.log(JSON.stringify({
          guardrailsOnly: !!s.brownfieldGuardrailsOnly,
          unavailable: deck.unavailable,
          records: deck.records.length,
        }));
        """
    )
    assert out["guardrailsOnly"], "the requirement stopped tripping the mode this test is about"
    assert out["records"] == 0
    assert out["unavailable"] and "no decision records" in out["unavailable"]


def test_review_is_a_third_view_and_the_other_two_are_untouched():
    text = _text()
    # The exact strings test_flow_default_view.py pins - Flow stays the default, Cards stays the
    # alternative, and adding a third button must not have quietly reordered them.
    assert 'id="viewFlowBtn" class="active icon-btn"' in text
    assert 'id="viewCardsBtn" class="icon-btn"' in text
    assert 'id="viewArbBtn" class="icon-btn"' in text
    assert "onclick=\"setView('arb')\"" in text
    for line in (
        "document.getElementById('viewArbBtn').classList.toggle('active', v==='arb');",
        "document.getElementById('arbWrap').style.display = v==='arb' ? 'block' : 'none';",
    ):
        assert line in text, line


@requires_node
def test_switching_views_shows_exactly_one_of_the_three():
    out = run_node_json(
        r"""
const els = {};
function el(id){
  if(!els[id]) els[id] = { id, style:{display:''}, classList:{
      _s:new Set(), add(c){this._s.add(c);}, remove(c){this._s.delete(c);},
      toggle(c,f){ f===undefined ? (this._s.has(c)?this._s.delete(c):this._s.add(c)) : (f?this._s.add(c):this._s.delete(c)); },
      contains(c){return this._s.has(c);} },
    addEventListener(){}, setAttribute(){}, getAttribute:()=>null, appendChild(){}, removeChild(){},
    click(){}, focus(){}, querySelector:()=>null, querySelectorAll:()=>[], innerHTML:'', textContent:'', value:'' };
  return els[id];
}
global.window = { innerWidth:1280, location:{search:''}, addEventListener(){}, matchMedia:()=>({matches:false,addEventListener(){}}) };
global.document = { documentElement:el('html'), body:el('body'), querySelector:()=>el('q'),
  querySelectorAll:()=>[], getElementById:(id)=>el(id), createElement:()=>el('new'), addEventListener(){} };
global.navigator = { clipboard:{} };
global.localStorage = { getItem:()=>null, setItem(){}, removeItem(){} };
global.fetch = () => Promise.resolve({ ok:false });
global.URL = { createObjectURL:()=>'', revokeObjectURL(){} };
global.requestAnimationFrame = (fn) => fn();
"""
        + _text().split("<script>")[2].split("</script>")[0]
        + r"""
const shown = () => ['results','flowWrap','arbWrap'].filter(id => el(id).style.display !== 'none');
const active = () => ['viewCardsBtn','viewFlowBtn','viewArbBtn'].filter(id => el(id).classList.contains('active'));
const seen = {};
for (const v of ['cards','flow','arb']) { setView(v); seen[v] = {shown: shown(), active: active()}; }
console.log(JSON.stringify(seen));
"""
    )
    assert out["cards"] == {"shown": ["results"], "active": ["viewCardsBtn"]}
    assert out["flow"] == {"shown": ["flowWrap"], "active": ["viewFlowBtn"]}
    assert out["arb"] == {"shown": ["arbWrap"], "active": ["viewArbBtn"]}


def test_the_signoff_roles_are_the_four_this_suite_signs_off_with():
    """test_signoffs_do_not_follow_you_to_a_different_analysis names these ids literally, because
    a `const` in an eval'd script block does not reach the harness. Adding a fifth reviewer role
    without updating that list would leave it silently signing three-quarters of the ledger."""
    block = re.search(r"const ARB_SIGNOFF_ROLES = \[(.*?)\n\];", _text(), re.S)
    assert block, "ARB_SIGNOFF_ROLES not found"
    assert re.findall(r"id:'([a-z]+)'", block.group(1)) == [
        "security", "architecture", "cloudops", "data"
    ]
