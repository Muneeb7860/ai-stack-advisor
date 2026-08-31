"""Harness Readiness evidence upload — implements docs/harness-engineering/
HARNESS_EVIDENCE_SCOPE.md. A hybrid of Shape A (guided self-report, shipped in
test_harness_readiness_feature.py) and Shape B (automated repo-scoring, which can't exist as
a literal browser-side crawl per that scope doc's own reasoning): one optional per-question
"attach evidence" file upload that client-side-regex/JSON-checks the file and flags — never
overrides — a mismatch against the user's self-selected score.

Tested here: the 5 pure checker functions (match/mismatch/silent for each component, using
small inline fixture strings, not real files) and the DOM-wiring/no-backend invariants the
rest of this feature area already holds itself to.
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

def test_evidence_toggle_and_file_input_exist_in_step_template():
    text = _text()
    start = text.index("function haRenderStep(){")
    section = text[start:start + 2500]
    assert "ha-evidence-toggle" in section
    assert "haEvidenceInput-" in section
    assert "haOnEvidenceFile(" in section


def test_evidence_toggle_is_gated_on_a_checker_existing_for_the_component():
    """Found during pre-merge review: the upload button used to render unconditionally for
    every question, so a future HARNESS_COMPONENTS entry with no matching checker would show a
    working-looking upload button that could never produce anything but permanent silence."""
    text = _text()
    start = text.index("function haRenderStep(){")
    section = text[start:start + 2500]
    assert "HA_EVIDENCE_CHECKERS[c.id] ?" in section


def test_no_backend_or_llm_call_anywhere_in_the_evidence_checker_code():
    """Same invariant the rest of Harness Readiness holds itself to — this feature reads one
    user-picked file client-side (FileReader), never transmits it anywhere."""
    text = _text()
    start = text.index("// ============ Harness Readiness evidence upload")
    end = text.index("let haCurrentStep = 1;")
    section = text[start:end]
    assert "checkObservabilityEvidence" in section, "sanity check: slice actually captured the feature"
    assert "fetch(" not in section
    assert "API_BASE" not in section


def test_uploads_never_change_the_score_or_selected_radio():
    """Evidence only confirms/flags — it must never assign to haAnswers[...] (picking a level
    on the user's behalf); reading the current selection to re-check evidence is fine."""
    text = _text()
    start = text.index("// ============ Harness Readiness evidence upload")
    end = text.index("let haCurrentStep = 1;")
    section = text[start:end]
    assert "haAnswers[componentId];" in section, "sanity check: the read this test allows is actually present"
    assert "haAnswers[" + "componentId] =" not in section
    assert "haAnswers[c.id] =" not in section


# ----------------------------------------------------------------- system_of_record checker

@requires_node
def test_system_of_record_evidence_silent_on_non_md_file():
    out = _js("""console.log(JSON.stringify(checkSystemOfRecordEvidence(2, 'hello', 'notes.txt')));""")
    assert out["verdict"] == "silent"


@requires_node
def test_system_of_record_evidence_mismatch_on_stub_file():
    out = _js("""console.log(JSON.stringify(checkSystemOfRecordEvidence(2, 'too short', 'AGENTS.md')));""")
    assert out["verdict"] == "mismatch"


@requires_node
def test_system_of_record_evidence_match_at_level_2_without_lesson_line():
    long_text = "A" * 250
    out = _js(f"""console.log(JSON.stringify(checkSystemOfRecordEvidence(2, {long_text!r}, 'AGENTS.md')));""")
    assert out["verdict"] == "match"


@requires_node
def test_system_of_record_evidence_mismatch_at_level_3_without_lesson_line():
    long_text = "A" * 250
    out = _js(f"""console.log(JSON.stringify(checkSystemOfRecordEvidence(3, {long_text!r}, 'AGENTS.md')));""")
    assert out["verdict"] == "mismatch"


@requires_node
def test_system_of_record_evidence_match_at_level_3_with_lesson_line():
    text = "A" * 250 + " Do not delete the cache directly — it broke prod last time."
    out = _js(f"""console.log(JSON.stringify(checkSystemOfRecordEvidence(3, {text!r}, 'AGENTS.md')));""")
    assert out["verdict"] == "match"


@requires_node
def test_system_of_record_evidence_a_short_stub_with_a_lesson_line_still_caps_at_level_1():
    """Found during pre-merge review: a lesson-line match used to grant ceiling 3 outright, so
    a 40-character stub containing one matching sentence outscored a real, substantial file
    with none. Both the length AND the lesson-line checks are now required for the top ceiling."""
    text = "Never delete cache directly, it broke prod once"  # 49 chars — well under the 200 floor
    out = _js(f"""console.log(JSON.stringify(checkSystemOfRecordEvidence(3, {text!r}, 'AGENTS.md')));""")
    assert out["verdict"] == "mismatch"
    assert "stub" in out["reason"]


# ----------------------------------------------------------------------------- tools checker

@requires_node
def test_tools_evidence_silent_on_unparseable_json():
    out = _js("""console.log(JSON.stringify(checkToolsEvidence(2, 'not json', 'mcp.json')));""")
    assert out["verdict"] == "silent"


@requires_node
def test_tools_evidence_match_at_level_2_with_configured_servers():
    payload = '{"mcpServers": {"filesystem": {}}}'
    out = _js(f"""console.log(JSON.stringify(checkToolsEvidence(2, {payload!r}, 'mcp.json')));""")
    assert out["verdict"] == "match"


@requires_node
def test_tools_evidence_mismatch_at_level_3_capped_at_2():
    payload = '{"mcpServers": {"filesystem": {}}}'
    out = _js(f"""console.log(JSON.stringify(checkToolsEvidence(3, {payload!r}, 'mcp.json')));""")
    assert out["verdict"] == "mismatch"


# ---------------------------------------------------------------------- verification checker

@requires_node
def test_verification_evidence_match_on_ci_yaml_with_known_tool():
    yaml_text = "steps:\n  - run: pytest\n"
    out = _js(f"""console.log(JSON.stringify(checkVerificationEvidence(2, {yaml_text!r}, 'ci.yml')));""")
    assert out["verdict"] == "match"


@requires_node
def test_verification_evidence_silent_on_ci_yaml_with_no_recognizable_check():
    yaml_text = "steps:\n  - run: echo hello\n"
    out = _js(f"""console.log(JSON.stringify(checkVerificationEvidence(2, {yaml_text!r}, 'ci.yml')));""")
    assert out["verdict"] == "silent"


@requires_node
def test_verification_evidence_match_at_level_3_with_blocking_hook():
    payload = '{"hooks": {"Stop": [{"command": "pytest"}]}}'
    out = _js(f"""console.log(JSON.stringify(checkVerificationEvidence(3, {payload!r}, 'settings.local.json')));""")
    assert out["verdict"] == "match"


@requires_node
def test_verification_evidence_mismatch_at_level_3_from_ci_yaml_alone():
    yaml_text = "steps:\n  - run: pytest\n"
    out = _js(f"""console.log(JSON.stringify(checkVerificationEvidence(3, {yaml_text!r}, 'ci.yml')));""")
    assert out["verdict"] == "mismatch"


# ------------------------------------------------------------------------ guardrails checker

@requires_node
def test_guardrails_evidence_silent_on_empty_permissions():
    payload = '{"permissions": {}}'
    out = _js(f"""console.log(JSON.stringify(checkGuardrailsEvidence(1, {payload!r}, 'settings.local.json')));""")
    assert out["verdict"] == "silent"


@requires_node
def test_guardrails_evidence_match_at_level_2_with_cred_deny_and_ask():
    payload = '{"permissions": {"allow": ["Bash(git *)"], "ask": ["Bash(git push)"], "deny": [".env"]}}'
    out = _js(f"""console.log(JSON.stringify(checkGuardrailsEvidence(2, {payload!r}, 'settings.local.json')));""")
    assert out["verdict"] == "match"


@requires_node
def test_guardrails_evidence_mismatch_at_level_2_with_allow_only():
    payload = '{"permissions": {"allow": ["Bash(git *)"], "ask": [], "deny": []}}'
    out = _js(f"""console.log(JSON.stringify(checkGuardrailsEvidence(2, {payload!r}, 'settings.local.json')));""")
    assert out["verdict"] == "mismatch"


@requires_node
def test_guardrails_evidence_mismatch_at_level_2_with_ask_rules_but_no_credential_deny():
    """Distinguishes the AND from an OR: ask rules alone, with no deny rule matching a
    credential pattern, must NOT be enough to confirm level 2 on their own."""
    payload = '{"permissions": {"allow": [], "ask": ["Bash(git push)"], "deny": []}}'
    out = _js(f"""console.log(JSON.stringify(checkGuardrailsEvidence(2, {payload!r}, 'settings.local.json')));""")
    assert out["verdict"] == "mismatch"


@requires_node
def test_guardrails_evidence_allow_only_reason_text_does_not_claim_deny_or_ask_rules():
    """Found during pre-merge review: the match/mismatch reason text used to be one static
    string reused across all 4 ceiling branches, so an allow-only file rendered "has a
    credential-path deny rule and ask rules" — false for a file with neither."""
    payload = '{"permissions": {"allow": ["Bash(git *)"], "ask": [], "deny": []}}'
    out = _js(f"""console.log(JSON.stringify(checkGuardrailsEvidence(1, {payload!r}, 'settings.local.json')));""")
    assert out["verdict"] == "match"
    assert "deny" not in out["reason"].lower() or "no deny" in out["reason"].lower()
    assert "ask" not in out["reason"].lower() or "no" in out["reason"].lower()


# --------------------------------------------------------------------- observability checker

@requires_node
def test_observability_evidence_silent_on_unrecognized_filename():
    out = _js("""console.log(JSON.stringify(checkObservabilityEvidence(2, '2026-01-01 broke', 'notes.md')));""")
    assert out["verdict"] == "silent"


@requires_node
def test_observability_evidence_zero_entries_reason_does_not_falsely_claim_entries_exist():
    """Found during pre-merge review: `entries || 'a'` treated the falsy 0 as the string 'a',
    so a file with zero recognizable entries rendered "has a dated/headed entries" — false."""
    text = "we had some issues last week, not writing them all down"  # no dates, no ## headings
    out = _js(f"""console.log(JSON.stringify(checkObservabilityEvidence(1, {text!r}, 'failures.md')));""")
    assert out["verdict"] == "match"
    assert "doesn't show any" in out["reason"]


@requires_node
def test_observability_evidence_match_at_level_3_with_multiple_dated_entries():
    text = "2026-01-01 broke build\n2026-01-05 fixed flaky test\n2026-01-10 timeout in CI"
    out = _js(f"""console.log(JSON.stringify(checkObservabilityEvidence(3, {text!r}, 'failures.md')));""")
    assert out["verdict"] == "match"


@requires_node
def test_observability_evidence_mismatch_at_level_3_with_single_entry():
    text = "2026-01-01 broke build"
    out = _js(f"""console.log(JSON.stringify(checkObservabilityEvidence(3, {text!r}, 'failures.md')));""")
    assert out["verdict"] == "mismatch"


# ------------------------------------------------------------------------------ dispatch table

@requires_node
def test_check_evidence_dispatches_to_the_right_component_checker():
    out = _js("""console.log(JSON.stringify(checkEvidence('observability', 1, 'x', 'notes.md').verdict));""")
    assert out == "silent"


@requires_node
def test_check_evidence_silent_for_unknown_component():
    out = _js("""console.log(JSON.stringify(checkEvidence('nonexistent', 1, 'x', 'y.md').verdict));""")
    assert out == "silent"


@requires_node
def test_harenderevidenceresult_clears_stale_match_class_when_hiding():
    """Found during pre-merge review: the silent branch used to clear text/display but leave a
    stale match/mismatch class behind on the (now-hidden) element."""
    out = _js("""
      const seenClassNames = [];
      const el = { set style(v){}, style:{}, set className(v){ seenClassNames.push(v); }, set textContent(v){} };
      global.document.getElementById = () => el;
      haRenderEvidenceResult('system_of_record', { verdict: 'match', reason: 'x' });
      haRenderEvidenceResult('system_of_record', { verdict: 'silent', reason: '' });
      console.log(JSON.stringify(seenClassNames));
    """)
    assert out[-1] == "ha-evidence-result", out


# ------------------------------------------------------------------- haRecheckEvidence (premature upload)

@requires_node
def test_harecheck_evidence_does_not_show_a_false_match_before_any_radio_is_selected():
    """Found during pre-merge review (independently, by 3 separate review angles): a sentinel
    of -1 for "no selection yet" always satisfied `level <= ceiling` (every real ceiling is
    0-3), so uploading a file before picking a radio option always rendered a false "match" —
    confirming a self-selected score that didn't exist yet."""
    out = _js("""
      let seen = null;
      haRenderEvidenceResult = (componentId, result) => { seen = result; };
      haAnswers = {};  // no selection made for system_of_record
      haEvidenceCache = { system_of_record: { text: 'A'.repeat(250), filename: 'AGENTS.md' } };
      haRecheckEvidence('system_of_record');
      console.log(JSON.stringify(seen));
    """)
    assert out["verdict"] == "silent"
