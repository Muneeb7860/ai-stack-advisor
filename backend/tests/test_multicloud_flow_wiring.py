"""
Regression tests found via review (not part of the original KB-promotion pass, #6): two real
gaps in index.html that were invisible to every existing test because nothing exercised
renderRecommendations()'s buildFlowGraph() call or diffRecommendations() against the six
categories promoted in #6.

1. multiCloudBridging (unlike the other five promoted categories) represents an actual
   diagrammable connectivity concept — a physical/logical bridge between two clouds, following
   the identical conditional `needed:true/false` shape as pickHybridConnectivity(), which DOES
   get a Flow View node. multiCloudBridging was wired into every card/refine surface but never
   into buildCanonicalArchitectureGraph() — so a multi-cloud requirement's Flow View, and every
   exporter derived from it (SVG/Mermaid/Draw.io), silently omitted the one thing about that
   requirement most worth drawing.

2. Once multiCloudBridging's node/edge existed, its EDGE_LABELS entry ('Cross-cloud bridge')
   turned out to be silently unreachable: generateSvgDiagram()'s labelBetween() returned on the
   FIRST edge crossing a given tier boundary with a registered label — and gateway->cloud's
   'Routes to' always crosses edge->compute before hybridconnectivity->cloud or
   multicloudbridging->cloud do, permanently shadowing both. Not a regression introduced here —
   hybridConnectivity's own 'Dedicated link' label had been silently dead code since it shipped,
   just never checked against the actual rendered SVG until this review.
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
  const svg = generateSvgDiagram(rec, s);
  const mmd = generateMermaidDiagram(rec, s);
  return {
    multiCloudSignal: s.multiCloudMentioned,
    pickNeeded: rec.multiCloudBridging.needed,
    nodePresent: graph.nodes.some(n => n.id === 'multicloudbridging'),
    edgePresent: graph.edges.some(e => e.from === 'multicloudbridging' && e.to === 'cloud'),
    svgHasNode: svg.includes('Multi-Cloud Bridging'),
    svgHasCrossCloudLabel: svg.includes('Cross-cloud bridge'),
    svgHasRoutesToLabel: svg.includes('Routes to'),
    mmdHasNode: mmd.includes('multicloudbridging'),
    mmdHasBothLabels: mmd.includes('Routes to') && mmd.includes('Cross-cloud bridge'),
    overrideEffectCardsHasAllSix: ['auditLogging','privilegedAccess','testingStrategy',
      'networkBoundary','multiCloudBridging','securityGates'].every(k => k in OVERRIDE_EFFECT_CARDS),
  };
}

console.log(JSON.stringify({
  singleCloud: scenario("AWS shop building an e-commerce recommendation engine."),
  multiCloud: scenario("GCP compute plane and Azure data plane, PCI compliance, high traffic."),
  multiCloudOnPrem: scenario("We run our own servers in-house and cannot move to cloud, though we evaluated AWS and Azure before deciding against it."),
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
def test_single_cloud_has_no_multicloud_node_anywhere(scenarios):
    r = scenarios["singleCloud"]
    assert r["multiCloudSignal"] is not True
    assert r["pickNeeded"] is False
    assert r["nodePresent"] is False
    assert r["edgePresent"] is False
    assert r["svgHasNode"] is False


@requires_node
def test_two_distinct_providers_gets_a_flow_view_node_and_edge(scenarios):
    r = scenarios["multiCloud"]
    assert r["multiCloudSignal"] is True
    assert r["pickNeeded"] is True
    assert r["nodePresent"] is True, "multiCloudBridging was reachable from every card/refine surface but never wired into buildCanonicalArchitectureGraph()"
    assert r["edgePresent"] is True


@requires_node
def test_onprem_override_still_suppresses_the_node_even_with_two_providers_named(scenarios):
    """The onPrem override takes priority in pickMultiCloudBridging() itself — Flow View must
    agree, not just the card text."""
    r = scenarios["multiCloudOnPrem"]
    assert r["pickNeeded"] is False
    assert r["nodePresent"] is False


@requires_node
def test_svg_export_shows_both_the_node_and_its_edge_label_uncollapsed(scenarios):
    """Regression lock for the labelBetween() shadowing bug: gateway->cloud's 'Routes to' must
    not silently swallow multicloudbridging->cloud's 'Cross-cloud bridge' just because it's
    reached first while scanning edges crossing the same tier boundary."""
    r = scenarios["multiCloud"]
    assert r["svgHasNode"] is True
    assert r["svgHasRoutesToLabel"] is True
    assert r["svgHasCrossCloudLabel"] is True, "gateway->cloud's label shadowed multicloudbridging->cloud's — labelBetween() only returned the first match"


@requires_node
def test_mermaid_export_was_never_affected_by_the_shadowing_bug(scenarios):
    """Mermaid labels per-edge, not per-tier-boundary, so it was never susceptible to the SVG
    exporter's specific bug — this locks that down so a future refactor can't accidentally
    introduce the same shadowing there too."""
    r = scenarios["multiCloud"]
    assert r["mmdHasNode"] is True
    assert r["mmdHasBothLabels"] is True


@requires_node
def test_override_effect_cards_includes_all_six_promoted_categories(scenarios):
    """Regression lock for the second review finding: OVERRIDE_EFFECT_CARDS (drives
    toggleInference()'s diff summary when a user toggles a detected assumption) was missing all
    six categories promoted in #6, so toggling e.g. 'compliance' could silently change up to six
    picks with the diff UI reporting none of it."""
    for key in ("singleCloud", "multiCloud"):
        assert scenarios[key]["overrideEffectCardsHasAllSix"] is True
