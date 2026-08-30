"""
Regression tests for the "Challenge This Pick" widget (docs/challenge-this-pick-spec.md).

Two kinds of check here:
1. A Node-harness round-trip test for getChallengeLog()/saveChallengeEntry() — same real
   in-memory localStorage pattern as test_analysis_history.py, since this suite also tests
   actual persistence, not just presence of the functions.
2. A static regression lock (plain regex/string checks against index.html, no Node needed)
   confirming CATEGORY_VENDORS reuses the SAME per-category vendor array identifiers
   (CLOUD_VENDORS, DATABASE_VENDORS, etc.) that renderAltToggle() already renders as "See N
   alternatives" on every card — fails if someone duplicates vendor data instead of reusing it.
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


# Same stub shape as test_analysis_history.py's _STUBS — real in-memory localStorage, no full
# DOM rendering needed since getChallengeLog/saveChallengeEntry are pure localStorage helpers.
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


# --------------------------------------------------------------------------- round-trip

@requires_node
def test_saving_a_challenge_entry_and_reading_it_back():
    out = _js("""
      saveChallengeEntry({cardKey:'stack-0', category:'cloud', currentPick:'AWS', proposedAlt:'GCP', reason:'Team already on GCP.'});
      const log = getChallengeLog();
      console.log(JSON.stringify({count: log.length, entry: log[0]}));
    """)
    assert out["count"] == 1
    assert out["entry"]["currentPick"] == "AWS"
    assert out["entry"]["proposedAlt"] == "GCP"
    assert out["entry"]["reason"] == "Team already on GCP."
    assert "id" in out["entry"] and "ts" in out["entry"]


@requires_node
def test_multiple_challenges_are_all_kept_not_overwritten():
    """Unlike analysis history, challenge entries are never de-duped/moved-to-front — every
    disagreement is its own fact, matching the backend Disagreement model's append-only design."""
    out = _js("""
      saveChallengeEntry({cardKey:'stack-0', category:'cloud', currentPick:'AWS', proposedAlt:'GCP', reason:'Reason A'});
      saveChallengeEntry({cardKey:'stack-0', category:'cloud', currentPick:'AWS', proposedAlt:'Azure', reason:'Reason B'});
      const log = getChallengeLog();
      console.log(JSON.stringify({count: log.length, newestFirst: log[0].reason}));
    """)
    assert out["count"] == 2
    assert out["newestFirst"] == "Reason B"


@requires_node
def test_get_challenge_log_tolerates_missing_localstorage_key():
    out = _js("console.log(JSON.stringify({log: getChallengeLog()}));")
    assert out["log"] == []


# ------------------------------------------------------------------- static regression lock

def test_category_vendors_reuses_the_same_arrays_render_alt_toggle_uses():
    """Must fail if someone duplicates vendor data instead of pointing CATEGORY_VENDORS at the
    SAME identifiers (CLOUD_VENDORS, DATABASE_VENDORS, ...) that renderAltToggle() already
    renders as "See N alternatives" on every card — one source of truth for "alternatives to
    this pick", used by two different UI surfaces."""
    text = _text()
    m = re.search(r"const CATEGORY_VENDORS = \{(.*?)\n\};", text, re.S)
    assert m, "CATEGORY_VENDORS not found"
    body = m.group(1)
    expected = {
        "cloud": "CLOUD_VENDORS", "gateway": "GATEWAY_VENDORS", "iam": "IAM_VENDORS",
        "compute": "COMPUTE_VENDORS", "cache": "CACHE_VENDORS", "messaging": "MESSAGING_VENDORS",
        "database": "DATABASE_VENDORS", "containers": "ORCHESTRATOR_VENDORS",
        "observability": "OBSERVABILITY_VENDORS", "frontend": "FRONTEND_VENDORS", "cicd": "CICD_VENDORS",
    }
    for key, array_name in expected.items():
        # The value must be EXACTLY the bare identifier (followed only by a comma/whitespace/
        # closing brace) — not the identifier plus a method call like .slice(), which would
        # silently break the "same array reference, not a copy" guarantee the spec requires.
        assert re.search(rf"\b{key}:\s*{array_name}\s*[,\n}}]", body), \
            f"{key} must map to the bare {array_name} identifier, not a copy/derivative of it"
    # No inline array literal (a `[` anywhere) should appear in this dict — that would mean
    # someone pasted vendor data in instead of reusing an existing const.
    assert "[" not in body, "CATEGORY_VENDORS must only reference existing vendor consts, never inline new arrays"


def test_challenge_button_and_form_exist_on_every_card_via_attach_refine_to_card():
    """buildChallengeButtonHtml()/buildChallengeBoxHtml() hold the actual markup (factored out
    so the Flow View integration can reuse it — see attachChallengeToFlowNode) — this test
    checks attachRefineToCard still wires both into every card's trigger row and zone."""
    text = _text()
    body_start = text.index("function attachRefineToCard(card, category, label, cardKey){")
    body_end = text.index("\n}\n", body_start)
    body = text[body_start:body_end]
    assert "cardPickByKey[cardKey]" in body
    assert "buildChallengeButtonHtml(cardKey)" in body
    assert "buildChallengeBoxHtml(cardKey, category)" in body

    button_start = text.index("function buildChallengeButtonHtml(cardKey){")
    button_end = text.index("\n}\n", button_start)
    button_body = text[button_start:button_end]
    assert "onChallengeToggleClick" in button_body
    assert "challenge-toggle-btn" in button_body

    box_start = text.index("function buildChallengeBoxHtml(cardKey, category){")
    box_end = text.index("\n}\n", box_start)
    box_body = text[box_start:box_end]
    assert "challenge-box" in box_body


def test_challenge_dropdown_falls_back_to_free_text_when_no_vendor_array_exists():
    text = _text()
    body_start = text.index("function buildChallengeBoxHtml(cardKey, category){")
    body_end = text.index("\n}\n", body_start)
    body = text[body_start:body_end]
    assert "const categoryVendors = CATEGORY_VENDORS[category];" in body
    assert "challengeSelectHtml" in body
    # The ternary's falsy branch must be an empty string, not a fabricated hardcoded list.
    assert re.search(r"const challengeSelectHtml = categoryVendors\s*\n?\s*\?", body)


def test_submit_never_force_creates_an_analysis_just_to_log_a_disagreement():
    """Per the spec's NFR-1 reasoning: onChallengeSubmit must gate its backend POST on
    currentAnalysisId already existing, never call ensureAnalysisId() to manufacture one."""
    text = _text()
    body_start = text.index("async function onChallengeSubmit(cardKey){")
    body_end = text.index("\n}\n", body_start)
    body = text[body_start:body_end]
    assert "if (currentAnalysisId)" in body
    assert "ensureAnalysisId" not in body


def test_backend_post_failure_never_throws_or_blocks():
    text = _text()
    body_start = text.index("async function onChallengeSubmit(cardKey){")
    body_end = text.index("\n}\n", body_start)
    body = text[body_start:body_end]
    assert "try {" in body and "catch(e)" in body
    # The local save must happen unconditionally, before the network attempt.
    save_idx = body.index("saveChallengeEntry(entry)")
    fetch_idx = body.index("fetch(")
    assert save_idx < fetch_idx, "local save must happen before the best-effort backend POST"
