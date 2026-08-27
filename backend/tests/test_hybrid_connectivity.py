"""
Hybrid Connectivity category — a genuinely new stack card (not a branch added to an
existing one), covering dedicated private links (Direct Connect/ExpressRoute/Cloud
Interconnect-class connectivity) between on-prem and cloud. Distinct from `onPrem`,
which means NO public cloud reachability at all — hybrid connectivity is the
opposite case: some workloads on each side, needing a private link between them.

Conditionally rendered content, not a conditionally rendered card (matches the
existing pattern used by Service Mesh/DNS/etc — the card always appears in the
15/16-card grid, its content honestly says "not required" when no signal fires).
The canonical-graph NODE, by contrast, IS conditional (like rag/vectordb) — it
only appears in Flow View / exports when there's a real hybrid-connectivity need.
"""
import shutil
from pathlib import Path

import pytest

from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
NODE_AVAILABLE = shutil.which("node") is not None
requires_node = pytest.mark.skipif(
    not NODE_AVAILABLE, reason="Node.js runtime required for frontend JavaScript execution"
)

_HARNESS = r"""
const dummyEl = {
  style: {}, classList: { add: () => {}, remove: () => {}, toggle: () => {} },
  addEventListener: () => {}, setAttribute: () => {}, getAttribute: () => null,
};
global.window = { location: { search: "" }, addEventListener: () => {} };
global.document = {
  documentElement: dummyEl,
  querySelectorAll: () => [],
  getElementById: () => dummyEl,
  addEventListener: () => {},
};
global.navigator = { clipboard: {} };
global.fetch = () => Promise.resolve({ ok: false });

%(script)s

function scenario(text) {
  const s = detectSignals(text);
  const rec = computeRecommendations(s);
  const graph = buildCanonicalArchitectureGraph(rec, s);
  return {
    hybridConnectivitySignal: s.hybridConnectivity,
    onPrem: s.onPrem,
    pick: rec.hybridConnectivity.v,
    pickNeeded: rec.hybridConnectivity.needed,
    nodePresent: graph.nodes.some(n => n.id === 'hybridconnectivity'),
    edgePresent: graph.edges.some(e => e.from === 'hybridconnectivity' && e.to === 'cloud'),
  };
}

console.log(JSON.stringify({
  noSignal: scenario("We're a small startup building a web app, nothing special about our infrastructure."),
  awsHybrid: scenario("We run AWS in the cloud but need a Direct Connect link back to our on-prem data center for latency-sensitive workloads."),
  azureHybrid: scenario("Enterprise team, need ExpressRoute connectivity between our on-prem servers and Azure."),
  gcpHybrid: scenario("We need Cloud Interconnect between our data center and GCP for a hybrid deployment."),
  huaweiHybrid: scenario("We're on Huawei Cloud and need a dedicated link back to our own data center, hybrid cloud setup."),
  onPremOnly: scenario("Air-gapped environment, no public cloud, cannot use any public cloud services at all."),
  genericHybrid: scenario("We have a hybrid cloud setup connecting our on-prem systems to the cloud."),
}));
"""


def _extract_main_script(source: str) -> str:
    parts = source.split("<script>")
    assert len(parts) >= 3, "expected at least 3 bare <script> blocks in index.html"
    return parts[2].split("</script>")[0]


@pytest.fixture(scope="module")
def scenarios():
    source = INDEX_HTML.read_text(encoding="utf-8")
    script = _extract_main_script(source)
    node_script = _HARNESS % {"script": script}
    return run_node_json(node_script)


@requires_node
def test_no_signal_means_not_required_and_no_node(scenarios):
    r = scenarios["noSignal"]
    assert r["hybridConnectivitySignal"] is False
    assert r["pickNeeded"] is False
    assert "Not required" in r["pick"]
    assert r["nodePresent"] is False


@requires_node
def test_onprem_means_not_applicable_and_no_node(scenarios):
    r = scenarios["onPremOnly"]
    assert r["onPrem"] is True
    assert r["pickNeeded"] is False
    assert "Not applicable" in r["pick"]
    assert r["nodePresent"] is False


@requires_node
@pytest.mark.parametrize("scenario_key,expected_substring", [
    ("awsHybrid", "AWS Direct Connect"),
    ("azureHybrid", "Azure ExpressRoute"),
    ("gcpHybrid", "GCP Cloud Interconnect"),
    ("huaweiHybrid", "Huawei Cloud Direct Connect"),
])
def test_vendor_specific_dedicated_link_pick(scenarios, scenario_key, expected_substring):
    r = scenarios[scenario_key]
    assert r["hybridConnectivitySignal"] is True
    assert r["pickNeeded"] is True
    assert expected_substring in r["pick"], f"expected '{expected_substring}' in {r['pick']!r}"
    assert r["nodePresent"] is True
    assert r["edgePresent"] is True


@requires_node
def test_generic_hybrid_phrasing_without_named_vendor_still_triggers(scenarios):
    # "hybrid cloud" text alone (no explicit vendor keyword, no named cloud) should still
    # detect the need and fall back to the vendor-agnostic guidance, not silently miss it.
    r = scenarios["genericHybrid"]
    assert r["hybridConnectivitySignal"] is True
    assert r["pickNeeded"] is True
    assert r["nodePresent"] is True


def test_python_signal_parity_for_hybrid_connectivity():
    """Signal-only parity, same scope boundary as Huawei support: rule_engine.py doesn't
    replicate pickHybridConnectivity's logic, only the detection signal."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
    from rule_engine import detect_signals

    s = detect_signals("We need Direct Connect to bridge our on-prem systems to AWS.")
    assert s.get("hybridConnectivity") is True
