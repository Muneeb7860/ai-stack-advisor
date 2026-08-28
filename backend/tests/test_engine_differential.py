"""
Behavioural differential between the two rule engines.

index.html and app/rule_engine.py are independent implementations of the same rules (v1 must
stay fully client-side per PRD NFR-1/NFR-5, so neither can import the other). test_engine_parity.py
compares the SET of category functions, which catches a whole function landing in one engine and
not the other. It cannot see divergence INSIDE a function — a missing branch, or a keyword absent
from one side's list — and that is where the expensive bugs have actually been:

  * `strong_on_prem` was missing six keywords here, so "we run our own servers in-house and cannot
    move to cloud" was on-prem in the browser and not on-prem in the backend. One signal, nine
    wrong picks, including recommending AWS to an air-gapped customer.
  * The Huawei Cloud pick branches existed only in index.html (9 references vs 1), so a Huawei
    customer got Huawei Cloud on screen and AWS from /api/refine, /api/ask and the MCP tool.

Both were found by running this comparison, and both had been open long enough to be logged in
PRD Section 12 as accepted scope. This file is that comparison, committed. The project has now
written an ad-hoc version of it three times — ADR-0001's throwaway Node harness, the 24-fixture
check when pickHybridConnectivity was ported, and the run that found the two bugs above — and
thrown it away each time.

Extend `engine_corpus.json` whenever a bug is found in one engine.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app import rule_engine as py_engine
from app.rule_engine import recommend_stack
from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
CORPUS = json.loads((Path(__file__).parent / "engine_corpus.json").read_text(encoding="utf-8"))["requirements"]
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

# index.html's camelCase rec keys -> rule_engine.py's snake_case recommendation keys.
KEYMAP = {
    "cloud": "cloud", "gw": "gateway", "iam": "iam", "lang": "languages", "arch": "architecture",
    "compute": "compute", "msg": "messaging", "mesh": "mesh", "cache": "cache", "db": "database",
    "containers": "containers", "obs": "observability", "fe": "frontend", "cicd": "cicd",
    "dns": "dns", "hybridConnectivity": "hybrid_connectivity", "hosting": "hosting_location",
    "runtime": "runtime",
    "auditLogging": "audit_logging", "privilegedAccess": "privileged_access",
    "testingStrategy": "testing_strategy", "networkBoundary": "network_boundary",
    "multiCloudBridging": "multi_cloud_bridging", "securityGates": "security_gates",
}

# Rationale prose still differs in this many (requirement, category) pairs out of 450. Ratcheted
# rather than gated: porting the remaining strings is a separate job from stopping the drift
# getting worse, and a number stated here is a number someone can drive down. It started at 38 and
# fell to 28 when the missing pick branches were ported — the test refuses to pass silently on an
# improvement, so the gain gets locked in rather than leaving slack for future drift.
# `v`, `conf`, signals and the keyword tables are all gated at zero.
#
# Dropped 28 -> 3 when pick_languages() turned out to be missing its entire node/dotnet/ruby/php
# team-skill block (found by this ratchet, when new minimalProject corpus cases exercised the
# path and exposed it). The remaining 3 are containers/database team-skill-note wording drift,
# unrelated to that fix — left as the tracked number rather than chased further here.
KNOWN_RATIONALE_DRIFT = 3

_STUBS = r"""
const fs = require('fs');
const src = fs.readFileSync(INDEX_PATH, 'utf8');
const dummyEl = { style:{}, classList:{add(){},remove(){},toggle(){}}, addEventListener(){},
  setAttribute(){}, getAttribute:()=>null, querySelector:()=>null, querySelectorAll:()=>[] };
global.window = { location:{search:''}, addEventListener(){} };
global.document = { documentElement:dummyEl, querySelectorAll:()=>[], getElementById:()=>dummyEl, addEventListener(){} };
global.navigator = { clipboard:{} };
global.localStorage = { getItem:()=>null, setItem(){}, removeItem(){} };
global.fetch = () => Promise.resolve({ ok:false });
"""


def _js_results():
    body = _STUBS + src_main() + """
      const out = {};
      for (const t of CORPUS){ const s = detectSignals(t); out[t] = {signals: s, rec: computeRecommendations(s)}; }
      console.log(JSON.stringify(out));
    """
    return run_node_json(f"const INDEX_PATH = {str(INDEX_HTML)!r};\nconst CORPUS = {json.dumps(CORPUS)};\n" + body)


def src_main():
    return INDEX_HTML.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]


@pytest.fixture(scope="module")
def js():
    return _js_results()


@requires_node
def test_boolean_signal_sets_are_identical(js):
    """A signal detected on one side and not the other cascades: the `strong_on_prem` gap turned
    one missing keyword into nine wrong recommendations."""
    diffs = []
    for text in CORPUS:
        j = {k for k, v in js[text]["signals"].items() if v is True}
        p = {k for k, v in recommend_stack(text)["signals"].items() if v is True}
        if j != p:
            diffs.append(f"{text[:60]!r}: JS-only={sorted(j - p)} PY-only={sorted(p - j)}")
    assert not diffs, "signal divergence:\n  " + "\n  ".join(diffs)


@requires_node
def test_pick_values_are_identical(js):
    diffs = []
    for text in CORPUS:
        pyr = recommend_stack(text)["recommendations"]
        for jk, pk in KEYMAP.items():
            a = (js[text]["rec"].get(jk) or {}).get("v")
            b = (pyr.get(pk) or {}).get("v")
            if a != b:
                diffs.append(f"{text[:50]!r} [{pk}]\n      JS: {a}\n      PY: {b}")
    assert not diffs, f"{len(diffs)} pick divergence(s):\n  " + "\n  ".join(diffs)


@requires_node
def test_confidence_levels_are_identical(js):
    """Confidence drives the `basis` label the user reads, so a divergence here means the two
    surfaces disagree about how sure they are."""
    diffs = []
    for text in CORPUS:
        pyr = recommend_stack(text)["recommendations"]
        for jk, pk in KEYMAP.items():
            a = (js[text]["rec"].get(jk) or {}).get("conf")
            b = (pyr.get(pk) or {}).get("conf")
            if a != b:
                diffs.append(f"{text[:50]!r} [{pk}]: JS={a} PY={b}")
    assert not diffs, "confidence divergence:\n  " + "\n  ".join(diffs)


@requires_node
def test_numeric_targets_are_identical(js):
    for text in CORPUS:
        p = recommend_stack(text)["signals"]
        j = js[text]["signals"]
        for key in ("latencyTarget", "concurrencyTarget", "timeline"):
            assert (j.get(key) or None) == (p.get(key) or None), f"{key} differs for {text[:60]!r}"


@requires_node
def test_exclusion_and_ownership_reads_are_identical(js):
    for text in CORPUS:
        p = recommend_stack(text)["signals"]
        j = js[text]["signals"]
        assert j.get("excluded") == p.get("excluded"), f"excluded differs for {text[:60]!r}"
        assert j.get("known") == p.get("known"), f"known differs for {text[:60]!r}"


@requires_node
def test_rationale_drift_does_not_grow(js):
    """Not gated at zero — the remaining rationale strings are their own porting job. This stops
    the number rising, and fails on a DECREASE too so an improvement is locked in rather than
    leaving headroom for the next drift."""
    drift = 0
    for text in CORPUS:
        pyr = recommend_stack(text)["recommendations"]
        for jk, pk in KEYMAP.items():
            if (js[text]["rec"].get(jk) or {}).get("why") != (pyr.get(pk) or {}).get("why"):
                drift += 1
    assert drift <= KNOWN_RATIONALE_DRIFT, (
        f"rationale drift grew from {KNOWN_RATIONALE_DRIFT} to {drift} — port the prose alongside "
        "the logic, or raise the ratchet deliberately with a reason"
    )
    if drift < KNOWN_RATIONALE_DRIFT:
        pytest.fail(f"drift dropped to {drift}; lower KNOWN_RATIONALE_DRIFT to lock the gain in")


@requires_node
def test_shared_keyword_tables_are_identical():
    """The heuristics both engines run on are hand-mirrored lists. A term added to one side only
    is invisible to every other test here unless a corpus case happens to use it."""
    tables = ["EXCLUSION_TERMS", "KNOWN_TERMS", "EXPERIENCE_BEFORE", "EXPERIENCE_AFTER",
              "EXPERIENCE_DISCLAIMERS", "NON_EXCLUSION_QUALIFIERS", "TIMELINE_CUES",
              "TIMELINE_DISQUALIFIERS"]
    js_tables = run_node_json(
        f"const INDEX_PATH = {str(INDEX_HTML)!r};\n" + _STUBS + src_main()
        + "\nconsole.log(JSON.stringify({" + ",".join(f"{t}:{t}" for t in tables) + "}));"
    )
    for name in tables:
        j, p = js_tables[name], getattr(py_engine, name)
        if isinstance(p, dict):
            j = {k: sorted(v) for k, v in j.items()}
            p = {k: sorted(v) for k, v in p.items()}
        else:
            j, p = sorted(j), sorted(p)
        assert j == p, f"{name} differs between engines"


def test_on_prem_keywords_cover_owning_your_own_servers():
    """Regression lock for the specific gap this file was written to find."""
    s = recommend_stack("We run our own servers in-house and cannot move to cloud.")["signals"]
    assert s["onPrem"] is True


def test_huawei_pick_logic_is_ported_not_just_the_signal():
    """PRD Section 12 logged this as signal-only parity; the picks are now ported too."""
    recs = recommend_stack("Huawei Cloud shop building an e-commerce recommendation engine.")["recommendations"]
    assert recs["cloud"]["v"] == "Huawei Cloud"
    assert "Huawei" in recs["gateway"]["v"]
    assert "CCE" in recs["containers"]["v"]
    assert "Cloud Eye" in recs["observability"]["v"]
    assert "CodeArts" in recs["cicd"]["v"]
    assert "Huawei Cloud DNS" in recs["dns"]["v"]
