"""Harness Readiness — a new, 4th entry mode implementing docs/harness-engineering/
HARNESS_READINESS_SCOPE.md. Unlike every other feature this session, this is v1-only (pure
client-side JS, no Python equivalent) and doesn't recommend a vendor — it scores a team's own
agent-development practices against Appendix B of the Harness Engineering Build Guide via a
guided 5-question radio flow, not free-text signal detection (see the scope doc for why).

Tested here: the scoring math (band boundaries, fix-order sort/cap, edge cases) and DOM wiring
(mode card, screens, the deliberate absence of any guardrails/observability vendor name — the
market research behind this scope found that exact vendor market got bought out or archived in
2026, so this feature teaches the practice instead of naming a product).
"""
import shutil
from pathlib import Path

import pytest

from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)


def _text() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _main_script() -> str:
    return _text().split("<script>")[2].split("</script>")[0]


_STUBS = r"""
const dummyEl = { style:{}, classList:{add(){},remove(){},toggle(){},contains:()=>false}, addEventListener(){},
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


# ------------------------------------------------------------------------------- DOM wiring

def test_fourth_mode_card_exists():
    assert 'onclick="startHarnessAudit()"' in _text()


def test_two_new_screens_exist_with_correct_default_hidden_css():
    text = _text()
    assert 'id="screenHarnessAudit"' in text
    assert 'id="screenHarnessResults"' in text
    assert '#screenHarnessAudit{display:none;}' in text
    assert '#screenHarnessResults{display:none;}' in text


def test_show_screen_array_includes_both_new_screens():
    assert "'screenHarnessAudit','screenHarnessResults'" in _text()


def test_radio_group_has_accessible_role():
    """Found during pre-merge review: the individual radios already got role="radio" via JS,
    but the container never got the matching role="radiogroup" a screen reader needs to
    announce the set as one group (the wizard's own equivalent group does this)."""
    text = _text()
    start = text.index("function haRenderStep(){")
    section = text[start:start + 2000]
    assert 'role="radiogroup"' in section


def test_start_harness_audit_clears_stale_product_analysis_state():
    """Found during pre-merge review: a user with a real product analysis already showing who
    then opens "Audit your harness" would otherwise see the old report rendered alongside the
    new harness screens, since #resultsShell's 'active' class is independent of showScreen()'s
    screen array."""
    text = _text()
    start = text.index("function startHarnessAudit(){")
    section = text[start:start + 800]
    assert "resultsShell" in section and "remove('active')" in section
    assert "setSidebarThisAnalysisVisible(false)" in section
    assert "closeContextPanel()" in section


def test_no_backend_or_llm_call_anywhere_in_the_harness_audit_code():
    """Matches the scope's own stated invariant: pure client-side, no API involvement."""
    text = _text()
    start = text.index("// ============ Harness Readiness audit ============")
    section = text[start:start + 10000]  # comfortably covers the whole feature block
    assert "function haFinish(){" in section, "sanity check: slice actually captured the feature"
    assert "fetch(" not in section
    assert "API_BASE" not in section


# --------------------------------------------------------------------------- vendor discipline

def test_no_guardrails_or_observability_vendor_names_anywhere_in_fix_text():
    """The single most important scope discipline check: the market research this scope is
    built on found the guardrails vendor market (Lakera, Protect AI, Guardrails AI) got bought
    out or archived in 2026 — naming one as "the" tool would recommend something that may not
    exist standalone by the time someone reads it."""
    text = _text()
    start = text.index("const HARNESS_COMPONENTS = [")
    end = text.index("const HA_SCORE_BANDS")
    block = text[start:end]
    for banned in ("Lakera", "Protect AI", "Guardrails AI", "NeMo Guardrails", "Datadog", "Splunk"):
        assert banned not in block, f"{banned!r} must not appear in HARNESS_COMPONENTS fix text"


def test_verification_fix_names_real_current_tools():
    text = _text()
    start = text.index("const HARNESS_COMPONENTS = [")
    end = text.index("const HA_SCORE_BANDS")
    block = text[start:end]
    for tool in ("Ruff", "pytest", "ESLint", "Vitest", "Playwright"):
        assert tool in block


# ----------------------------------------------------------------------------- JS parity / logic

@requires_node
def test_js_score_bands_boundaries():
    out = _js("""
      console.log(JSON.stringify([0,4,5,9,10,13,14,15].map(t => HA_SCORE_BANDS.find(b => t <= b.max).label)));
    """)
    assert out == [
        "Harness consumer", "Harness consumer",
        "Real harness exists", "Real harness exists",
        "Production grade", "Production grade",
        "Mature", "Mature",
    ]


@requires_node
def test_js_score_harness_audit_all_zeros():
    out = _js("""
      const r = scoreHarnessAudit({});
      console.log(JSON.stringify({ total: r.total, band: r.band.label }));
    """)
    assert out["total"] == 0
    assert out["band"] == "Harness consumer"


@requires_node
def test_js_score_harness_audit_all_threes():
    out = _js("""
      const answers = {};
      HARNESS_COMPONENTS.forEach(c => answers[c.id] = 3);
      const r = scoreHarnessAudit(answers);
      console.log(JSON.stringify({ total: r.total, band: r.band.label }));
    """)
    assert out["total"] == 15
    assert out["band"] == "Mature"


@requires_node
def test_js_fix_order_is_sorted_lowest_first_and_capped_at_three():
    """Found during pre-merge review: fixOrder used to always return exactly 3 components
    regardless of score, so a component scoring 2 (already fine per the per-component card's
    own <=1 threshold for showing "Fix:" text) would still show up here. guardrails scores 2
    in this input, so it's correctly excluded — only verification (0) and tools (1) qualify."""
    out = _js("""
      const answers = { system_of_record: 3, tools: 1, verification: 0, guardrails: 2, observability: 3 };
      const r = scoreHarnessAudit(answers);
      console.log(JSON.stringify(r.fixOrder.map(c => c.id)));
    """)
    assert out == ["verification", "tools"]


@requires_node
def test_js_fix_order_is_empty_when_nothing_scores_0_or_1():
    """A perfect (or near-perfect) score shouldn't produce a padded, contradictory fix list."""
    out = _js("""
      const answers = { system_of_record: 3, tools: 2, verification: 3, guardrails: 2, observability: 3 };
      const r = scoreHarnessAudit(answers);
      console.log(JSON.stringify(r.fixOrder.length));
    """)
    assert out == 0


@requires_node
def test_js_fix_order_never_exceeds_three_even_with_five_components():
    out = _js("""
      const answers = { system_of_record: 0, tools: 0, verification: 0, guardrails: 0, observability: 0 };
      const r = scoreHarnessAudit(answers);
      console.log(JSON.stringify(r.fixOrder.length));
    """)
    assert out == 3


@requires_node
def test_js_missing_answers_default_to_zero_in_scoring():
    """A partially-completed state (shouldn't reach scoreHarnessAudit via the real UI, since
    Continue is disabled until a selection is made, but the scoring function itself should be
    defensive rather than throwing on a missing key)."""
    out = _js("""
      const r = scoreHarnessAudit({ system_of_record: 3 });
      console.log(JSON.stringify(r.total));
    """)
    assert out == 3
