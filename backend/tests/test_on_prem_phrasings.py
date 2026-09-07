"""Every way a person says "we run this ourselves" must reach the on-prem branch.

Reported by a user testing the live page: "i clearly says on premises and even i say on own
server still it recommends AWS cloud and serverless", and separately "why always aws?". Those are
the same bug. On-prem was detected by three literal spellings — "on-prem", "on premises",
"on-premise" — and measured against nineteen ordinary phrasings, sixteen missed. Every miss falls
through to pick_cloud's final default, which is AWS. So the answer to "why always AWS" is "because
on-prem almost never fires", and the answer to "why doesn't on-prem fire" is that it was a
three-item list nobody could see the holes in.

Replaced with a regex family, because the list is precisely what failed: any spelling nobody
thought to add was silently absent, and nothing anywhere reported a miss.
"""
import shutil
from pathlib import Path

import pytest

from app.rule_engine import detect_signals, recommend_stack
from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

# Ordinary ways of saying it. Every one of these was measured against the real engine; the three
# that already worked are kept so a future narrowing cannot quietly undo them either.
ON_PREM_PHRASINGS = [
    "on premise deployment",          # space, singular — the spelling the user typed
    "on-premise deployment",
    "on premises deployment",
    "on-prem deployment",
    "onpremise deployment",           # no separator at all
    "on premise only",
    "runs on premise",
    "we host it on our own hardware",
    "we run it on our own infrastructure",
    "deployed to our own data centre",  # en-GB
    "deployed in our own data center",  # en-US
    "installed in our datacenter",      # one word
    "our own physical servers",         # adjective between "own" and the noun
    "we run our own kit in a colo",
    "in-house servers only",
    "hosted in our colocation facility",
]

# Requirements that must keep their cloud. The two at the end are the ones that make this hard:
# a negated mention, and a hybrid link that names on-prem while explicitly reaching a cloud.
CLOUD_PHRASINGS = [
    "We deploy to AWS with serverless Lambda.",
    "A managed Kubernetes cluster on GKE.",
    "We use Azure and Entra ID for a web app.",
    "Our own team builds and maintains the React frontend.",
    "In-house engineers maintain our CI pipeline on GitHub Actions.",
    "Multi-region deployment across AWS regions.",
    "Our own domain name on Cloudflare with a static site.",
    "We want modern public cloud hosting on AWS, not on-prem or bare metal.",
    "Direct Connect to bridge our on-prem systems to AWS VPC workloads.",
]


@pytest.mark.parametrize("requirement", ON_PREM_PHRASINGS)
def test_ordinary_on_prem_phrasings_are_detected(requirement):
    assert detect_signals(requirement)["onPrem"], (
        f"{requirement!r} did not set onPrem — it falls through to the AWS default"
    )


@pytest.mark.parametrize("requirement", CLOUD_PHRASINGS)
def test_cloud_requirements_are_not_dragged_on_prem(requirement):
    """The widening must not cost anything in the other direction. "In-house engineers" is about
    staffing, "our own team" and "our own domain" are not hosting, and a negated or hybrid mention
    of on-prem is not an on-prem requirement."""
    assert not detect_signals(requirement)["onPrem"], f"{requirement!r} was wrongly read as on-prem"


def test_the_reported_case_no_longer_recommends_aws_and_serverless():
    """The user's own sentence, and the three picks they called out."""
    rec = recommend_stack("on premise deployment on our own hardware")["recommendations"]
    assert "On-premises" in rec["cloud"]["v"], rec["cloud"]["v"]
    assert "AWS" not in rec["cloud"]["v"]

    # Written twice as an absence check, and wrong both times. These picks state what they are NOT:
    #   compute:    "Self-managed Kubernetes on bare metal/VMware — no public-cloud serverless"
    #   containers: "Docker + self-managed Kubernetes (kubeadm/Rancher/RKE2 ...) — not EKS/GKE/AKS"
    # so `"serverless" not in ...` and `"EKS" not in ...` both fail against a perfectly correct
    # recommendation. Same family as this repo's standing rule about asserting on source text that
    # contains the very words explaining why they were not used. Assert the affirmative instead.
    assert "Self-managed" in rec["compute"]["v"], rec["compute"]["v"]
    assert "bare metal" in rec["compute"]["v"].lower(), rec["compute"]["v"]
    assert "self-managed Kubernetes" in rec["containers"]["v"], rec["containers"]["v"]
    assert "kubeadm" in rec["containers"]["v"], rec["containers"]["v"]


def test_bare_self_hosted_deliberately_does_not_mean_on_prem():
    """A judgement call worth pinning so it is not "fixed" later by someone reading the battery
    above and noticing the gap.

    onPrem means no public-cloud reachability at all — it rules out AWS/Azure/GCP entirely. A team
    self-hosting Postgres on EC2 says "self-hosted" and is emphatically on a public cloud, so
    firing onPrem there would destroy a correct pick. selfHostInfra already carries the weaker
    "you operate your own runtime" meaning, and that is the signal that should react to this.
    """
    s = detect_signals("We run a self-hosted deployment of the API.")
    assert not s["onPrem"], "bare 'self-hosted' must not imply no-public-cloud"


@requires_node
def test_both_engines_detect_the_same_phrasings():
    """Two hand-mirrored regexes now, one per engine. A phrase added to one side only is a browser
    that says on-prem while /api/refine and the MCP tool say AWS — the exact divergence class this
    file's own history is made of.
    """
    cases = ON_PREM_PHRASINGS + CLOUD_PHRASINGS
    stubs = r"""
const d = {style:{}, classList:{add(){},remove(){},toggle(){}}, addEventListener(){}, setAttribute(){},
  getAttribute:()=>null, appendChild(){}, removeChild(){}, click(){}, focus(){}, querySelector:()=>null,
  querySelectorAll:()=>[], innerHTML:'', textContent:'', value:''};
global.window = {location:{search:''}, addEventListener(){}, matchMedia:()=>({matches:false,addEventListener(){}})};
global.document = {documentElement:d, body:d, querySelector:()=>d, querySelectorAll:()=>[],
  createElement:()=>d, addEventListener(){}, getElementById:()=>d};
global.navigator = {clipboard:{}};
global.localStorage = {getItem:()=>null, setItem(){}, removeItem(){}};
global.fetch = () => Promise.resolve({ok:false});
global.URL = {createObjectURL:()=>'', revokeObjectURL(){}};
global.requestAnimationFrame = (f) => f();
"""
    main = INDEX_HTML.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]
    body = (
        "const out = {};\n"
        f"for (const t of {cases!r}) out[t] = !!detectSignals(t).onPrem;\n"
        "console.log(JSON.stringify(out));"
    ).replace("'", '"')
    js = run_node_json(stubs + main + "\n" + body)
    diffs = [c for c in cases if js[c] != bool(detect_signals(c)["onPrem"])]
    assert not diffs, f"engines disagree on onPrem for: {diffs}"
