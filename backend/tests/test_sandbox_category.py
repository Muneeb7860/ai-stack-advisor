"""Code Execution Sandbox as a vendor category (E2B / Vercel Sandbox / Modal / Daytona).

Added after web-verifying a market claim rather than accepting it. The prompting document turned
out to be accurate on every checkable point, including the benchmark figures encoded below, which
match independently published burst-concurrency testing.

Why this is a real category and not a restatement of `containers`: ORCHESTRATOR_VENDORS and
pick_compute run YOUR OWN trusted, long-lived services, and the isolation they provide is between
your workloads and your other workloads. This is the opposite problem — ephemeral, per-task
execution of code the operator did not write and cannot review, where the threat model is the code
itself. Same shape of distinction pick_realtime_analytics_vendor draws against pick_database's
warehouse branch.

The gate is an explicit code-execution signal, NOT `agentic`. An agentic workflow that only calls
read-only APIs has no untrusted-code problem, and firing on it would recommend cost and latency for
an absent threat.

The catalog ordering deliberately contradicts the vendors' own marketing, which is the reason the
category earns its place: published cold-start figures are measured sequentially, one create at a
time, while an agent that opens a sandbox per tool call creates in concurrent bursts. Under burst
the ranking inverts — the provider advertising the fastest start (~90ms sequential) has a failure
rate near 37%. Encoding only headline numbers would actively mislead.
"""
import json
import re
import shutil
from pathlib import Path

import pytest

from app.rule_engine import SANDBOX_VENDORS, pick_sandbox_vendor, recommend_stack
from tests.node_harness import run_node_json

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

CODE_EXEC = "An AI agent that must execute code the model generates against customer data."


def _signals(text: str):
    return recommend_stack(text)["signals"]


def _pick(text: str):
    return recommend_stack(text)["recommendations"]["sandbox"]


# ------------------------------------------------------------------------------- the gate

def test_no_code_execution_means_not_applicable():
    assert "Not applicable" in _pick("A CRUD web app for a dental practice.")["v"]


def test_agentic_alone_does_not_trigger_a_sandbox():
    """The over-firing case this category is most likely to get wrong. An agent calling read-only
    APIs has nothing untrusted to isolate — recommending a sandbox there is cost and latency for a
    threat that does not exist."""
    pick = _pick("A multi-agent workflow with tool use calling our internal read-only APIs.")
    assert _signals("A multi-agent workflow with tool use calling our internal read-only APIs.")["agentic"] is True
    assert "Not applicable" in pick["v"], (
        "an agentic requirement without code execution must not get a sandbox recommendation"
    )


@pytest.mark.parametrize("phrase", [
    "execute code", "untrusted code", "code interpreter", "run generated code",
    "sandboxed execution", "arbitrary code",
])
def test_each_gating_phrase_fires(phrase):
    assert _signals(f"Our product needs to {phrase} from users.")["codeExecution"] is True


def test_the_category_is_distinct_from_containers():
    """Both can be present at once and mean different things; neither should suppress the other."""
    rec = recommend_stack(CODE_EXEC + " Deployed on Kubernetes.")["recommendations"]
    assert "Not applicable" not in rec["sandbox"]["v"]
    assert rec["containers"]["v"] != rec["sandbox"]["v"]


# --------------------------------------------------------------------------------- branches

def test_default_pick_is_e2b():
    assert _pick(CODE_EXEC)["v"] == "E2B"


def test_security_or_enterprise_prefers_the_credential_isolating_option():
    """The deciding feature is that credentials never enter the model's context — the leak path
    prompt injection actually exploits — not raw isolation strength, which E2B matches."""
    pick = _pick("Enterprise agent running untrusted code for customers, PII in scope, strict security.")
    assert pick["v"] == "Vercel Sandbox"
    assert "context" in pick["why"]


def test_air_gapped_gets_a_self_hostable_answer_not_a_managed_one():
    """Every entry in this catalog is a hosted multi-tenant service. Naming one for an air-gapped
    requirement would recommend something the reader cannot deploy — the same bug class already
    fixed for Neon/Turso and Tinybird/ClickHouse."""
    pick = _pick("Air-gapped, no public cloud. The agent must execute untrusted code.")
    assert pick["primaryId"] is None
    assert "gVisor" in pick["v"] or "Firecracker" in pick["v"]
    for vendor in ("E2B", "Vercel Sandbox", "Modal", "Daytona"):
        assert vendor not in pick["v"]


@pytest.mark.parametrize("text,expected", [
    ("We run untrusted code on E2B today.", "e2b"),
    ("We use Vercel Sandbox to execute code.", "vercelsandbox"),
    ("Our modal sandbox executes generated code.", "modal"),
])
def test_an_explicitly_named_vendor_is_kept(text, expected):
    assert _pick(text)["primaryId"] == expected


def test_naming_daytona_keeps_it_but_states_the_concurrency_caveat():
    """Deliberately not an override — the user's existing choice stands. But the one fact that
    would change their mind is not discoverable from the vendor's own materials, so it is stated:
    the headline cold start is sequential, and burst behaviour is far worse."""
    pick = _pick("We already use Daytona to run generated code.")
    assert pick["primaryId"] == "daytona"
    assert "37" in pick["why"], "the burst failure rate is the actionable fact here"
    assert "sequential" in pick["why"]


# --------------------------------------------------------------------------------- catalog

def test_the_catalog_encodes_burst_behaviour_not_just_headline_latency():
    """The reason this category is worth shipping. A comparison repeating the vendors' sequential
    numbers would rank Daytona first and be actively misleading for the workload agents produce."""
    daytona = next(v for v in SANDBOX_VENDORS if v["id"] == "daytona")
    assert "37" in daytona["drawback"]
    assert "one-create-at-a-time" in daytona["drawback"] or "sequential" in daytona["drawback"]


def test_every_vendor_states_a_real_drawback():
    """A catalog where one option has no downside is a recommendation wearing a comparison's
    clothes."""
    for v in SANDBOX_VENDORS:
        assert v["drawback"].strip(), f"{v['name']} has no stated drawback"
        assert len(v["drawback"]) > 40, f"{v['name']}'s drawback is too thin to be useful"


def test_vendor_ids_are_unique_and_referenced():
    ids = [v["id"] for v in SANDBOX_VENDORS]
    assert len(ids) == len(set(ids))
    for text in (CODE_EXEC, "Enterprise agent running untrusted code, PII, strict security."):
        pid = _pick(text)["primaryId"]
        if pid is not None:
            assert pid in ids


# ----------------------------------------------------------------------------- dual engine

@requires_node
def test_both_engines_agree_across_the_branches():
    """Belt-and-braces alongside test_engine_differential.py, which now covers this category —
    it did not when this was written, and a deliberate JS-only change to the default pick passed
    silently. See that file's KEYMAP comment."""
    script = INDEX.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]
    cases = [
        CODE_EXEC,
        "A CRUD web app for a dental practice.",
        "Enterprise agent running untrusted code for customers, PII in scope, strict security.",
        "Air-gapped, no public cloud. The agent must execute untrusted code.",
        "We already use Daytona to run generated code.",
    ]
    stubs = """
const dummyEl={style:{},classList:{add(){},remove(){},toggle(){},contains:()=>false},addEventListener(){},
  setAttribute(){},getAttribute:()=>null,querySelector:()=>dummyEl,querySelectorAll:()=>[],innerHTML:'',textContent:''};
global.window={innerWidth:1280,location:{search:''},addEventListener(){},matchMedia:()=>({matches:false,addEventListener(){}})};
global.document={documentElement:dummyEl,body:dummyEl,querySelector:()=>dummyEl,querySelectorAll:()=>[],
  getElementById:()=>dummyEl,createElement:()=>dummyEl,addEventListener(){}};
global.navigator={clipboard:{}};global.localStorage={getItem:()=>null,setItem(){},removeItem(){}};
global.fetch=()=>Promise.resolve({ok:false});global.URL={createObjectURL:()=>'',revokeObjectURL(){}};
global.requestAnimationFrame=(fn)=>fn();
"""
    body = (
        "const cases = " + json.dumps(cases) + ";\n"
        "console.log(JSON.stringify(cases.map(c => {"
        "  const p = pickSandboxVendor(detectSignals(c));"
        "  return {v: p.v, primaryId: p.primaryId, conf: p.conf};"
        "})));"
    )
    js = run_node_json(stubs + script + "\n" + body)
    for text, js_pick in zip(cases, js):
        py = pick_sandbox_vendor(_signals(text))
        assert js_pick["v"] == py["v"], f"engines disagree on {text!r}"
        assert js_pick["primaryId"] == py["primaryId"], f"primaryId differs on {text!r}"
        assert js_pick["conf"] == py["conf"], f"conf differs on {text!r}"


def test_the_js_catalog_matches_the_python_catalog():
    text = INDEX.read_text(encoding="utf-8")
    m = re.search(r"const SANDBOX_VENDORS = \[(.*?)\n\];", text, re.S)
    assert m, "SANDBOX_VENDORS not found in index.html"
    js_ids = re.findall(r"id:'([^']+)'", m.group(1))
    assert js_ids == [v["id"] for v in SANDBOX_VENDORS], "vendor order/ids differ between engines"


# ------------------------------------------------------------------------------------ UI

def test_the_card_is_wired_into_the_stack_grid():
    text = INDEX.read_text(encoding="utf-8")
    assert "'Code Execution Sandbox', sandboxVendorPick.v" in text
    assert "'Code Execution Sandbox':'sandbox'" in text, (
        "without the STACK_CARD_CATEGORY entry the card renders but Refine/Ask/Challenge cannot "
        "look it up, unlike every other stack card"
    )


def test_refine_accepts_the_new_category():
    """VALID_CATEGORIES gates the LLM's allowed adjustments; omitting it makes the card the one
    the backend silently refuses to refine."""
    from app.routers.refine import VALID_CATEGORIES
    assert "sandbox" in VALID_CATEGORIES


def test_the_alternatives_note_carries_the_burst_caveat():
    """The note is what a reader sees when comparing options, so it is where the sequential-vs-
    burst distinction has to live, not only in one vendor's drawback field."""
    text = INDEX.read_text(encoding="utf-8")
    m = re.search(r"const SANDBOX_NOTE = '([^']*(?:\\'[^']*)*)'", text)
    assert m, "SANDBOX_NOTE not found"
    note = m.group(1).lower()
    assert "sequential" in note and "burst" in note

# --------------------------------------------------------------------- domain floors

@pytest.mark.parametrize("text,label", [
    ("A local CLI tool that executes untrusted code snippets.", "cliTool"),
    ("A browser extension that runs untrusted user scripts.", "browserExtension"),
])
def test_a_stack_with_no_provisioned_infrastructure_gets_no_hosted_sandbox(text, label):
    """Found in review.

    The domain-floor blocks already said, for these stacks, "no server-side hosting", "nothing
    runs server-side to containerize" and "compute: not applicable" — and the sandbox category
    still answered E2B, a hosted multi-tenant SaaS. The engine was contradicting itself inside one
    set of recommendations.

    It is the same reasoning pick_sandbox_vendor's own on-prem branch already applied, just not
    applied here, because the floors enumerate categories by hand and this one was added after
    they were written. Fourth instance in this codebase of "a new category missed a place that
    enumerates categories" — see test_category_wiring.py for the other three.
    """
    rec = recommend_stack(text)["recommendations"]
    pick = rec["sandbox"]
    assert "Not applicable" in pick["v"], (
        f"{label}: compute is {rec['compute']['v'][:40]!r} but sandbox recommends "
        f"{pick['v'][:40]!r} — a hosted service for a stack with nothing to host it against"
    )
    for vendor in ("E2B", "Vercel Sandbox", "Modal", "Daytona"):
        assert vendor not in pick["v"]


def test_the_floor_still_names_a_real_local_alternative():
    """"Not applicable" alone would be unhelpful here: the user genuinely does run untrusted code,
    they just have nowhere hosted to run it. The answer is local isolation, not silence."""
    pick = recommend_stack("A local CLI tool that executes untrusted code snippets.")["recommendations"]["sandbox"]
    assert "gVisor" in pick["v"] or "Firecracker" in pick["v"] or "container" in pick["v"]


def test_the_floor_does_not_fire_for_an_ordinary_service():
    """Guards the opposite error — a floor that swallows the normal case."""
    assert recommend_stack(CODE_EXEC)["recommendations"]["sandbox"]["v"] == "E2B"
