"""Serious regression found during a comprehensive live-QA testing pass across the whole
session's work — not from any pasted report, an automated test, or a specific PR's own review,
but from combining features in the real browser and noticing an unrelated positive signal
("agentic") silently vanish.

Root cause: unlike the active-voice negator regex (which stops at a subordinating/contrasting
conjunction via _CLAUSE_END/NEGATION_CLAUSE_END), the passive-voice negation prefix
(_PASSIVE_NEGATION_PREFIX) had NO boundary at all — it was a bare `[^.!?;\\n]{0,300}?`, unanchored
and free to cross "but"/"however"/etc. This meant ANY passive-negation phrase ("must not be
used", "is ruled out", "off the table", ...) occurring anywhere in a sentence could wipe out
EVERY positive signal earlier in that same sentence, as long as no period separated them.

Concretely: "We need an agentic system but Kubernetes is off the table." used to strip to
`" ."` — the entire sentence, not just the Kubernetes clause — silently erasing the agentic
signal this app's own Agent Framework category (this session's own work) depends on.

The bug predates "off the table" (idiomatic-negator PR) — "must not be used" has the exact same
failure, dating back to the original passive-voice negation fix. "off the table" just made it
far more likely to trigger in practice, since it commonly follows a "but"-style contrast — which
is how a comprehensive testing pass surfaced it now rather than in either of those earlier PRs'
own (narrower) test suites.

Asserted against BOTH engines (rule_engine.py and index.html's JS twin).
"""
import shutil
from pathlib import Path

import pytest

from app.rule_engine import detect_signals, strip_negations
from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)


def _main_script() -> str:
    return INDEX_HTML.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]


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


def _js(expr_body: str):
    return run_node_json(_STUBS + _main_script() + "\n" + expr_body)


OFF_THE_TABLE_CROSS_CLAUSE = "We need an agentic system but Kubernetes is off the table."
MUST_NOT_BE_USED_CROSS_CLAUSE = "We need an agentic system but Kubernetes must not be used."
HOWEVER_CROSS_CLAUSE = "We already run PostgreSQL in production, however Kubernetes must not be used."
NO_CONJUNCTION_SAME_SENTENCE = "Kubernetes is off the table for this project."


# ------------------------------------------------------------------------ the core regression

def test_off_the_table_no_longer_erases_an_unrelated_earlier_clause():
    assert strip_negations(OFF_THE_TABLE_CROSS_CLAUSE).startswith("We need an agentic system but")


def test_must_not_be_used_no_longer_erases_an_unrelated_earlier_clause():
    """The bug predates 'off the table' — this phrase alone reproduces it."""
    assert strip_negations(MUST_NOT_BE_USED_CROSS_CLAUSE).startswith("We need an agentic system but")


def test_however_conjunction_is_also_respected():
    assert strip_negations(HOWEVER_CROSS_CLAUSE).startswith("We already run PostgreSQL in production, however")


def test_agentic_signal_survives_a_same_sentence_off_the_table_exclusion():
    """The concrete, real-world case this was found from: this session's own Agent Framework
    category (pick_agent_framework_vendor) depends on the `agentic` signal surviving."""
    s = detect_signals(OFF_THE_TABLE_CROSS_CLAUSE)
    assert s["agentic"] is True


# --------------------------------------------------------------------------- still works right

def test_the_negated_clause_itself_is_still_correctly_removed():
    """This fix must not simply disable passive-negation stripping — the actual negated clause
    still needs to disappear, only the UNRELATED preceding clause must survive."""
    stripped = strip_negations(OFF_THE_TABLE_CROSS_CLAUSE)
    assert "off the table" not in stripped.lower()
    assert "kubernetes" not in stripped.lower()


def test_no_conjunction_in_the_way_still_strips_from_the_true_start():
    """Regression guard the other direction — when there's genuinely nothing to preserve before
    the phrase (no conjunction, no prior clause), stripping must still work as before."""
    stripped = strip_negations(NO_CONJUNCTION_SAME_SENTENCE)
    assert "kubernetes" not in stripped.lower()
    assert "off the table" not in stripped.lower()


# ------------------------------------------------------------------------------------ JS parity

@requires_node
def test_js_off_the_table_no_longer_erases_an_unrelated_earlier_clause():
    out = _js(f"console.log(JSON.stringify(stripNegations({OFF_THE_TABLE_CROSS_CLAUSE!r})));")
    assert out.startswith("We need an agentic system but")


@requires_node
def test_js_agentic_signal_survives_a_same_sentence_off_the_table_exclusion():
    out = _js(f"console.log(JSON.stringify(detectSignals({OFF_THE_TABLE_CROSS_CLAUSE!r}).agentic));")
    assert out is True
