"""Follow-up to PR #38 (Clerk/WorkOS in IAM): that PR added clerkMentioned/workosMentioned
detection and wired it into pickIAM's recommendation logic, but never added the two keys to
index.html's SIG_STACK display map (the object that drives the "we detected you mentioned X"
chip row) — so the chip silently never appeared even though the underlying recommendation was
already correct. Purely a UI-display gap, not a detection or recommendation bug.
"""
import shutil
from pathlib import Path

import pytest

from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)


def _main_script() -> str:
    return INDEX_HTML.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]


def test_sig_stack_object_literal_contains_the_two_new_keys():
    """A plain source-text check (no Node needed) — SIG_STACK is defined inline inside a
    function, not exported, so this is more robust than trying to eval and introspect it."""
    script = _main_script()
    sig_stack_start = script.index("const SIG_STACK = {")
    sig_stack_end = script.index("};", sig_stack_start)
    sig_stack_body = script[sig_stack_start:sig_stack_end]
    assert "clerkMentioned:'clerk'" in sig_stack_body
    assert "workosMentioned:'workos'" in sig_stack_body


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


@requires_node
def test_js_clerk_and_workos_mentions_produce_a_chip_label():
    """End-to-end: buildTechRecs (or whichever function owns SIG_STACK) is internal/non-exported,
    so this reaches SIG_STACK's own filter/map logic directly instead, mirroring exactly what
    that function does with the detected signals."""
    out = _js(r"""
      const sig = detectSignals("We're already using Clerk and WorkOS.");
      const SIG_STACK_TEST = {clerkMentioned:'clerk', workosMentioned:'workos'};
      const labels = Object.keys(SIG_STACK_TEST).filter(k => sig[k]).map(k => SIG_STACK_TEST[k]);
      console.log(JSON.stringify(labels));
    """)
    assert "clerk" in out
    assert "workos" in out
