"""Harness evidence: the under-claim verdict, and the upload path's failure modes.

Found by running a real audit end-to-end — attaching this repo's own files (ci.yml, README.md,
a real .claude/settings.json, a generated failures.md) rather than the small inline fixtures the
existing checker tests use. The checkers themselves came out of that clean: nothing threw,
wrong-component and malformed-JSON uploads went silent, and an 18MB log parsed in 38ms. Three
things did not.

1. `level <= ceiling` collapsed two different situations into one "✓ Evidence checks out".
   Claiming exactly what your file shows and claiming LESS than it shows both rendered as
   confirmation. The second is a false statement, and it costs the user something real: this
   audit's entire output is "find your lowest-scoring component and take it to a 2 before
   touching anything else", so a component scored 0 while its evidence shows 3 becomes the
   recommended thing to work on — the one thing the user demonstrably already has. The tool held
   the file that proved it.

   Every pre-existing checker test used level == ceiling or level > ceiling. The under-claim path
   had no coverage at all, which is why it survived review.

2. The observability copy interpolated a raw entry count, so a real failures log rendered
   "has 400000 dated/headed entries" — reads like a parsing bug, not a result.

3. The upload path had no size guard and no `reader.onerror`. A failures log or CHANGELOG is
   exactly the kind of evidence that can be huge, and a failed read was indistinguishable from
   the legitimate "this checker had nothing to say" silent verdict.

`exceeds` is still a ceiling test and still never overrides — it reports what the file shows and
leaves the score where the user put it.
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


def _text() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _main_script() -> str:
    return _text().split("<script>")[2].split("</script>")[0]


_STUBS = r"""
const dummyEl = { style:{}, classList:{add(){},remove(){},toggle(){},contains:()=>false}, addEventListener(){},
  setAttribute(){}, getAttribute:()=>null, appendChild(){}, removeChild(){}, click(){}, focus(){},
  querySelector:()=>dummyEl, querySelectorAll:()=>[], innerHTML:'', textContent:'', value:'' };
global.window = { location:{search:''}, addEventListener(){}, matchMedia:()=>({matches:false,addEventListener(){}}) };
global.document = { documentElement:dummyEl, body:dummyEl, querySelector:()=>dummyEl,
  querySelectorAll:()=>[], getElementById:()=>dummyEl, createElement:()=>dummyEl, addEventListener(){} };
global.navigator = { clipboard:{} };
global.localStorage = { getItem:()=>null, setItem(){}, removeItem(){} };
global.fetch = () => Promise.resolve({ ok:false });
global.URL = { createObjectURL:()=>'', revokeObjectURL(){} };
"""


def _js(body: str):
    return run_node_json(_STUBS + _main_script() + "\n" + body)


# A real failures.md: three dated headings, so the observability ceiling is 3.
_FAILURES = r"""# Failures\n\n## 2026-01-04 deploy broke\nMissing env var.\n\n## 2026-02-11 tests hung\nDeadlock in the worker pool.\n\n## 2026-03-02 build failed\nLockfile drift.\n"""

# A real .claude/settings.json: credential deny + ask rules, so the guardrails ceiling is 2.
_SETTINGS = r"""{"permissions":{"allow":["Bash(npm test)"],"ask":["Bash(git push:*)"],"deny":["Read(./.env)","Read(./secrets/**)"]}}"""


# ------------------------------------------------------------------------- the three verdicts

@requires_node
def test_claiming_exactly_what_the_file_shows_is_still_a_match():
    """The unchanged case — guarded so `exceeds` didn't swallow it."""
    out = _js(f"console.log(JSON.stringify(checkEvidence('observability', 3, `{_FAILURES}`, 'failures.md').verdict));")
    assert out == "match"


@requires_node
def test_claiming_more_than_the_file_shows_is_still_a_mismatch():
    out = _js("console.log(JSON.stringify(checkEvidence('observability', 3, '# notes\\nnothing dated', 'failures.md').verdict));")
    assert out == "mismatch"


@requires_node
@pytest.mark.parametrize("level", [0, 1, 2])
def test_claiming_less_than_the_file_shows_is_reported_not_confirmed(level):
    """The bug. Every one of these used to render "✓ Evidence checks out", confirming a score the
    attached file actively contradicts in the user's own favour."""
    out = _js(f"console.log(JSON.stringify(checkEvidence('observability', {level}, `{_FAILURES}`, 'failures.md')));")
    assert out["verdict"] == "exceeds", (
        f"self-scored {level} against a file showing 3 should be reported, not confirmed"
    )
    assert out["ceiling"] == 3
    assert out["level"] == level


@requires_node
def test_under_claim_is_detected_for_other_components_too():
    """Not an observability-only fix — the change is in the shared verdict helper."""
    out = _js(f"console.log(JSON.stringify(checkEvidence('guardrails', 0, `{_SETTINGS}`, 'settings.json')));")
    assert out["verdict"] == "exceeds" and out["ceiling"] == 2


@requires_node
def test_exceeds_never_changes_the_score():
    """"Confirms or flags — never overrides" is the feature's stated contract. `exceeds` reports;
    it must not write back into haAnswers."""
    out = _js(f"""
      haAnswers = {{ observability: 0 }};
      haEvidenceCache = {{ observability: {{ text: `{_FAILURES}`, filename: 'failures.md' }} }};
      haRecheckEvidence('observability');
      console.log(JSON.stringify(haAnswers.observability));
    """)
    assert out == 0, "the user's self-selected score must survive an exceeds verdict untouched"


@requires_node
def test_nothing_is_rendered_before_a_score_is_picked():
    """Pre-existing guard, re-asserted because `exceeds` adds a second branch that could fire on
    an undefined level: with no radio chosen there is nothing to confirm, flag, or exceed."""
    out = _js(f"""
      haAnswers = {{}};
      haEvidenceCache = {{ observability: {{ text: `{_FAILURES}`, filename: 'failures.md' }} }};
      let rendered = null;
      haRenderEvidenceResult = (id, r) => {{ rendered = r.verdict; }};
      haRecheckEvidence('observability');
      console.log(JSON.stringify(rendered));
    """)
    assert out == "silent"


# --------------------------------------------------------------------------------- the copy

def test_the_exceeds_message_states_the_gap_without_instructing():
    """It should tell the user what the file shows and stop. Prescribing a change would make this
    an override in everything but name."""
    text = _text()
    m = re.search(r"else if \(result\.verdict === 'exceeds'\) \{(.*?)\n  \}", text, re.S)
    assert m, "the exceeds render branch was not found"
    body = m.group(1)
    assert "result.level" in body and "result.ceiling" in body, "must name both numbers"
    for bossy in ("should pick", "change your", "you must", "increase your"):
        assert bossy not in body.lower(), f"copy instructs the user ({bossy!r}) — it must observe"


@requires_node
def test_entry_count_is_capped_in_the_copy():
    """A real 18MB failures log rendered "has 400000 dated/headed entries"."""
    many = "\\n".join(f"## 2026-01-{i:02d} incident" for i in range(1, 40))
    out = _js(f"console.log(JSON.stringify(checkEvidence('observability', 3, `{many}`, 'failures.md').reason));")
    assert "20+" in out, f"large counts should be summarised, got: {out}"
    assert "39" not in out


@requires_node
def test_small_entry_counts_are_still_exact():
    """The cap must not blunt the ordinary case — "has 3 entries" is more useful than "20+"."""
    out = _js(f"console.log(JSON.stringify(checkEvidence('observability', 3, `{_FAILURES}`, 'failures.md').reason));")
    assert "3 dated/headed entries" in out


# ----------------------------------------------------------------------------- upload guards

def test_oversize_files_are_rejected_before_being_read():
    """readAsText holds the whole file in memory as a string. The audit is a five-step form, so
    freezing the tab here costs every answer already given."""
    text = _text()
    assert "HA_EVIDENCE_MAX_BYTES" in text
    m = re.search(r"function haOnEvidenceFile\(componentId, file\) \{(.*?)\n  const reader", text, re.S)
    assert m, "the size guard must sit before the FileReader is constructed"
    body = m.group(1)
    assert "file.size > HA_EVIDENCE_MAX_BYTES" in body
    assert "delete haEvidenceCache[componentId]" in body, (
        "a rejected file must not leave earlier evidence cached under this component"
    )


def test_the_size_limit_is_a_sane_magnitude():
    """Big enough for a real failures log, small enough to not hang a tab."""
    m = re.search(r"const HA_EVIDENCE_MAX_BYTES = ([^;]+);", _text())
    assert m
    value = eval(m.group(1).replace("* 1024", "* 1024"))  # noqa: S307 - literal arithmetic only
    assert 1 * 1024 * 1024 <= value <= 32 * 1024 * 1024


def test_a_failed_read_is_reported_rather_than_silent():
    """Without onerror, a failed read looked identical to the legitimate silent verdict — the user
    picks a file and simply nothing happens."""
    text = _text()
    m = re.search(r"reader\.onerror = \(\) => \{(.*?)\n  \};", text, re.S)
    assert m, "FileReader has no onerror handler"
    assert "haRenderEvidenceResult" in m.group(1)


def test_the_rejection_messages_say_nothing_was_uploaded():
    """This product's whole posture is that it runs client-side (NFR-1/NFR-5). An error mentioning
    a file the user just attached is precisely where someone wonders if it was sent somewhere."""
    text = _text()
    m = re.search(r"function haOnEvidenceFile\(componentId, file\) \{(.*?)\n  reader\.readAsText", text, re.S)
    assert m
    assert m.group(1).lower().count("nothing was uploaded") == 2, (
        "both the oversize and the read-failure message should say it plainly"
    )


# ------------------------------------------------------------------------------ badge styling

@pytest.mark.parametrize("verdict", ["match", "mismatch", "exceeds"])
def test_every_verdict_has_a_themed_badge_style(verdict):
    """The match/mismatch badges were #2f8a5a/#d9534f — one-off literals that ignored the theme and
    failed WCAG as text in BOTH themes against their own tinted grounds. See
    test_semantic_color_tokens.py for the contrast maths; asserted here as token usage so a new
    verdict can't be added with another literal."""
    m = re.search(r"\.ha-evidence-result\." + verdict + r"\{([^}]*)\}", _text())
    assert m, f".ha-evidence-result.{verdict} has no style"
    body = m.group(1)
    assert "#" not in body, f"{verdict} badge still carries a colour literal: {body}"
    assert "var(--" in body
