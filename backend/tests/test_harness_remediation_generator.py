"""Turnkey Harness Remediation Generator — exports an AGENTS.md, .claude/settings.json and
FAILURES.md tailored to the gaps the user's own audit found.

The word doing the work in that sentence is "tailored", and the first version of this file did not
test it. It asserted that a low-scoring audit produced text containing "Security Deny List" — which
was true, but true for every input, because four of the five score lookups read component ids that
do not exist.

HARNESS_COMPONENTS defines exactly five: system_of_record, tools, verification, guardrails,
observability. The generator read `grounding`, `scope`, `tool_governance` and `memory`. Each
resolved to undefined, which the `!== undefined ? : 0` guard turned into a score of 0, so those
four sections always emitted their worst-case advice. Measured: a user scoring a perfect 3 on
every component was still told to add a security deny list and a loop circuit-breaker. Only
`verification` was reading a real answer.

So the tests below compare a perfect audit against a zero audit and require the outputs to
DIFFER, per section. An assertion that some text is present cannot distinguish a generator that
tailors from one that emits everything unconditionally — which is precisely how the bug survived
its own test suite.
"""
import json
import pytest
from pathlib import Path
from tests.node_harness import run_node_json

ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "index.html"


def _main_script() -> str:
    # Extracts the main script tag (index 2)
    return INDEX_HTML.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]


_STUBS = r"""
const dummyEl = { style:{}, classList:{add(){},remove(){},toggle(){}}, addEventListener(){},
  setAttribute(){}, getAttribute:()=>null, appendChild(){}, removeChild(){}, click(){}, focus(){},
  querySelector:()=>null, querySelectorAll:()=>[], innerHTML:'', textContent:'', value:'',
  scrollIntoView(){} };
global.window = { location:{search:''}, addEventListener(){}, matchMedia:()=>({matches:false,addEventListener(){}}) };
global.document = { documentElement:dummyEl, body:dummyEl, querySelector:()=>dummyEl,
  querySelectorAll:()=>[], getElementById:()=>dummyEl, createElement:()=>dummyEl, addEventListener(){} };
global.navigator = { clipboard:{ writeText: async () => true } };
global.localStorage = { getItem:()=>null, setItem(){}, removeItem(){} };
global.fetch = () => Promise.resolve({ ok:false });
global.URL = { createObjectURL:()=>'blob:mock', revokeObjectURL(){} };
global.requestAnimationFrame = (fn) => fn();
"""


def _js(expr_body: str):
    return run_node_json(_STUBS + _main_script() + "\n" + expr_body)


PERFECT = {"system_of_record": 3, "tools": 3, "verification": 3, "guardrails": 3, "observability": 3}
ZERO = {"system_of_record": 0, "tools": 0, "verification": 0, "guardrails": 0, "observability": 0}


def _generate(answers):
    return _js(f"""
      const md = generateTurnkeyAgentsMd({json.dumps(answers)});
      const settings = generateTurnkeyClaudeSettings({json.dumps(answers)});
      console.log(JSON.stringify({{md: md, settings: settings}}));
    """)


def test_remediation_generator_functions_exist():
    out = _js("""
      console.log(JSON.stringify({
        hasGenerateAgentsMd: typeof generateTurnkeyAgentsMd === 'function',
        hasGenerateClaudeSettings: typeof generateTurnkeyClaudeSettings === 'function',
        hasGenerateFailuresMd: typeof generateTurnkeyFailuresMd === 'function',
        hasDownloadPack: typeof downloadTurnkeyHarnessPack === 'function'
      }));
    """)
    assert all(out.values())


# ------------------------------------------------ the assertion the original file was missing

@pytest.mark.parametrize("marker,component", [
    ("Strict TDD Mandate", "verification"),
    ("Filesystem Ground Truth Contract", "system_of_record"),
    ("Security Deny List", "guardrails"),
    ("10-Iteration Circuit Breaker", "observability"),
    ("AST Caller/Callee Verification", "tools"),
])
def test_each_section_responds_to_its_own_component_score(marker, component):
    """One case per section, because the bug affected four of five and a single spot-check would
    have found only the one that worked.

    Each marker must appear for a user who scored that component 0 and be absent for one who
    scored it 3. Anything else means the section is not reading its score.
    """
    low = dict(PERFECT); low[component] = 0
    assert marker in _generate(low)["md"], (
        f"scoring {component} 0 should produce the {marker!r} remediation"
    )
    assert marker not in _generate(PERFECT)["md"], (
        f"{marker!r} is emitted even at a perfect {component} score — the section is not reading it"
    )


def test_a_perfect_audit_and_a_failing_audit_do_not_produce_the_same_file():
    """The blunt version of the same property. If these ever match, "tailored" is false whatever
    the individual sections say."""
    assert _generate(PERFECT)["md"] != _generate(ZERO)["md"]


def test_an_unknown_component_id_fails_loudly():
    """The bug was silent: an unknown id degraded to score 0 and produced worst-case advice that
    looked deliberate. A rename should break the build instead."""
    out = _js("""
      let threw = false;
      try { haRemediationScore({}, 'tool_governance'); } catch (e) { threw = true; }
      console.log(JSON.stringify(threw));
    """)
    assert out is True


def test_every_id_the_generator_reads_is_a_real_component():
    """Derived from HARNESS_COMPONENTS rather than listed, so a new or renamed component is caught
    here rather than silently reverting a section to worst-case advice."""
    out = _js("""
      const real = HARNESS_COMPONENTS.map(c => c.id);
      console.log(JSON.stringify({
        real: real,
        declared: HA_REMEDIATION_SCORES,
        unknown: HA_REMEDIATION_SCORES.filter(id => real.indexOf(id) === -1)
      }));
    """)
    assert out["unknown"] == [], f"generator reads ids no component has: {out['unknown']}"
    assert set(out["declared"]) == set(out["real"])


# ------------------------------------------------------------------------ settings.json

def test_settings_json_is_valid_and_its_deny_list_tracks_the_guardrails_score():
    perfect = json.loads(_generate(PERFECT)["settings"])
    zero = json.loads(_generate(ZERO)["settings"])
    assert "permissions" in perfect and "deny" in perfect["permissions"]
    assert len(zero["permissions"]["deny"]) > len(perfect["permissions"]["deny"]), (
        "a user with no guardrails should get a stricter deny list than one scoring 3/3"
    )


def test_failures_md_is_generated_with_a_usable_template():
    out = _js("console.log(JSON.stringify(generateTurnkeyFailuresMd({})));")
    assert "Incident Template" in out and "Root Cause" in out
