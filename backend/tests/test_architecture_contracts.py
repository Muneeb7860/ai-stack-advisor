"""
Architecture invariant test for the hexagonal graph refactor in index.html.

There's no JS test runner in this frameworkless project (AGENTS.md forbids adding a
build step), so this is a static-analysis contract test in the spirit of Swish_App's
HexagonalArchitectureTest.java: it reads index.html as text and asserts the core
domain function stays pure, and that outbound adapters consume the canonical graph
rather than re-deriving their own reduced topology.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"

# Skip decorator for runtime tests when Node isn't installed. The static-analysis
# tests in Layer A still run in pure Python on any platform.
requires_node = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="Node.js binary not found on PATH; skipping JS runtime tests",
)


def _read_source() -> str:
    assert INDEX_HTML.exists(), f"index.html not found at {INDEX_HTML}"
    return INDEX_HTML.read_text(encoding="utf-8")


def _extract_function_body(source: str, fn_name: str) -> str:
    """Grab a top-level `function fn_name(...) { ... }` body via brace counting."""
    m = re.search(rf"function\s+{re.escape(fn_name)}\s*\([^)]*\)\s*{{", source)
    assert m, f"function {fn_name} not found in index.html"
    start = m.end()
    depth = 1
    i = start
    while depth > 0:
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
        i += 1
    return source[start:i - 1]


FORBIDDEN_GLOBALS = ["document.", "window.", "localStorage", "sessionStorage", "fetch("]
FORBIDDEN_FORMAT_STRINGS = ["mxGraphModel", "graph TD", "<svg", ".drawio", ".mmd"]


def test_canonical_graph_builder_exists():
    source = _read_source()
    assert "function buildCanonicalArchitectureGraph(" in source, (
        "buildCanonicalArchitectureGraph(ctx, signals) is the domain core of the hexagonal "
        "refactor and must exist as a standalone function."
    )


def test_canonical_graph_builder_signature_supports_signals():
    source = _read_source()
    # Must accept both ctx and optional signals argument
    assert re.search(r"function\s+buildCanonicalArchitectureGraph\s*\(\s*ctx\s*(?:,\s*signals\s*(?:=\s*\{\})?)?\s*\)", source), (
        "buildCanonicalArchitectureGraph must support both ctx and optional signals parameter."
    )


def test_canonical_graph_builder_is_pure():
    source = _read_source()
    body = _extract_function_body(source, "buildCanonicalArchitectureGraph")
    for token in FORBIDDEN_GLOBALS:
        assert token not in body, (
            f"buildCanonicalArchitectureGraph references '{token}' — the domain core "
            "must stay free of browser globals so it's a pure function of ctx."
        )
    for token in FORBIDDEN_FORMAT_STRINGS:
        assert token not in body, (
            f"buildCanonicalArchitectureGraph contains format-specific string '{token}' "
            "— file-format concerns belong in outbound adapters, not the domain core."
        )


def test_canonical_graph_builder_has_no_layout_coordinates():
    source = _read_source()
    body = _extract_function_body(source, "buildCanonicalArchitectureGraph")
    # The domain core must not assign pixel positions — that's layoutFlowGraph's job.
    assert not re.search(r"\bx\s*:", body), "domain core must not embed x coordinates"
    assert not re.search(r"\by\s*:", body), "domain core must not embed y coordinates"
    assert "color:" not in body, "domain core must not embed theme colors"


def test_layout_adapter_exists_and_adds_coordinates():
    source = _read_source()
    assert "function layoutFlowGraph(" in source, (
        "layoutFlowGraph(graph) must exist to decorate the canonical graph with "
        "x/y/color for the Flow View canvas."
    )
    body = _extract_function_body(source, "layoutFlowGraph")
    # Accept both `x: expr` and ES6 shorthand `{ x, y }` property syntax.
    assert re.search(r"\bx\s*[,:}]", body), "layoutFlowGraph must assign x coordinates"
    assert re.search(r"\by\s*[,:}]", body), "layoutFlowGraph must assign y coordinates"


@pytest.mark.parametrize("adapter_fn", [
    "generateMermaidDiagram",
    "generateDrawioXml",
    "generateSvgDiagram",
])
def test_outbound_adapters_consume_canonical_graph(adapter_fn):
    source = _read_source()
    body = _extract_function_body(source, adapter_fn)
    assert "buildCanonicalArchitectureGraph(" in body, (
        f"{adapter_fn} must build off buildCanonicalArchitectureGraph(...) instead of "
        "re-deriving its own reduced node set via getPickVal/ad-hoc extraction."
    )


def test_flow_graph_wrapper_composes_core_and_layout():
    source = _read_source()
    body = _extract_function_body(source, "buildFlowGraph")
    assert "buildCanonicalArchitectureGraph(" in body
    assert "layoutFlowGraph(" in body


# ---------------------------------------------------------------------------
# Layer B — runtime execution tests
# ---------------------------------------------------------------------------

REQUIRED_NODE_FIELDS = ["id", "cat", "title", "sub", "conf", "why", "persona", "detail", "opportunities"]
REQUIRED_OPPORTUNITY_FIELDS = ["id", "name", "tier", "type", "complexity", "valueCategory", "tech", "prerequisites", "rationale"]

# Minimal DOM/window/fetch stub — enough for the whole inline <script> block to
# evaluate without throwing at parse time, without pulling in a real DOM library.
_NODE_HARNESS_TEMPLATE = r"""
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

const s = detectSignals("We're a fintech startup building a mobile + web app for real-time fraud detection on card transactions with a chatbot answering questions from our internal policy documents, SOC2/PCI compliant, small team.");
const rec = computeRecommendations(s);
const graph = buildCanonicalArchitectureGraph(rec, s);
const flowGraph = layoutFlowGraph(graph);

// Extract all opportunities across all nodes
const allOpportunities = [];
graph.nodes.forEach(n => {
  if (Array.isArray(n.opportunities)) {
    n.opportunities.forEach(opp => allOpportunities.push(opp));
  }
});

console.log(JSON.stringify({
  nodeCount: graph.nodes.length,
  edgeCount: graph.edges.length,
  nodeFieldSets: graph.nodes.map(n => Object.keys(n).sort()),
  flowNodesHaveXYColor: flowGraph.nodes.every(n =>
    typeof n.x === "number" && typeof n.y === "number" && typeof n.color === "string"),
  allOpportunities,
  dbNodeOpportunities: (graph.nodes.find(n => n.id === "db") || {}).opportunities || [],
  mermaid: generateMermaidDiagram(rec, s),
  drawio: generateDrawioXml(rec, s),
  svg: generateSvgDiagram(rec, s),
}));
"""


def _extract_main_script(source: str) -> str:
    # index.html has three bare `<script>` tags (line ~10, ~1060, ~14143) plus one
    # `<script type="application/json" ...>` data block that this split does not
    # match. The domain/adapter functions live in the second bare block.
    parts = source.split("<script>")
    assert len(parts) >= 3, "expected at least 3 bare <script> blocks in index.html"
    return parts[2].split("</script>")[0]


@pytest.fixture(scope="module")
def js_runtime_result():
    source = _read_source()
    script = _extract_main_script(source)
    node_script = _NODE_HARNESS_TEMPLATE % {"script": script}
    proc = subprocess.run(
        ["node", "-e", node_script], capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == 0, f"Node execution failed:\n{proc.stderr}"
    return json.loads(proc.stdout)


@requires_node
def test_runtime_canonical_graph_schema(js_runtime_result):
    assert 18 <= js_runtime_result["nodeCount"] <= 20, (
        f"expected 18-20 nodes for a scenario with RAG+vectorDB active, "
        f"got {js_runtime_result['nodeCount']}"
    )
    for field_set in js_runtime_result["nodeFieldSets"]:
        assert field_set == sorted(REQUIRED_NODE_FIELDS), (
            f"node missing required fields: {set(REQUIRED_NODE_FIELDS) - set(field_set)}"
        )


@requires_node
def test_runtime_opportunities_schema_and_attachment(js_runtime_result):
    opps = js_runtime_result["allOpportunities"]
    assert len(opps) >= 3, f"expected at least 3 active opportunities on fintech scenario, got {len(opps)}"
    for opp in opps:
        assert set(REQUIRED_OPPORTUNITY_FIELDS).issubset(set(opp.keys())), (
            f"opportunity missing fields: {set(REQUIRED_OPPORTUNITY_FIELDS) - set(opp.keys())}"
        )
        assert opp["type"] in ["gap", "optimization"], f"invalid opportunity type: {opp.get('type')}"
        assert opp["complexity"] in ["Low", "Medium", "High"], f"invalid complexity: {opp.get('complexity')}"
        assert isinstance(opp["prerequisites"], list) and len(opp["prerequisites"]) > 0


@requires_node
def test_runtime_compliance_guardrails_on_text_to_sql(js_runtime_result):
    # Regression guard: an earlier version of data-text-to-sql's trigger referenced
    # phantom signal keys (s.fintech instead of the real s.finance, plus s.analytics/
    # s.saas/s.reporting which don't exist at all) so it silently never fired on the
    # fintech-PCI scenario this harness uses — and this assertion used to be gated
    # behind `if sql_opp:`, so it passed vacuously instead of catching that. Assert
    # presence first, unconditionally, so a regression fails loudly instead of skipping.
    db_opps = js_runtime_result["dbNodeOpportunities"]
    sql_opp = next((o for o in db_opps if o["id"] == "data-text-to-sql"), None)
    assert sql_opp is not None, (
        "data-text-to-sql must attach to the db node for the fintech-PCI scenario "
        "this harness uses — if this fails, check the trigger's signal keys against "
        "the real detectSignals() output (s.finance, not s.fintech; no s.analytics/"
        "s.saas/s.reporting keys exist)"
    )
    assert sql_opp["complexity"] == "High"
    prereqs_str = " ".join(sql_opp["prerequisites"]).lower()
    assert "read-only" in prereqs_str or "replica" in prereqs_str
    assert "pii" in prereqs_str or "tokenization" in prereqs_str or "masking" in prereqs_str


@requires_node
def test_runtime_layout_adds_xy_color_to_every_node(js_runtime_result):
    assert js_runtime_result["flowNodesHaveXYColor"] is True


@requires_node
def test_runtime_drawio_xml_validity(js_runtime_result):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(js_runtime_result["drawio"])  # raises if malformed
    assert root.tag == "mxfile"


@requires_node
def test_runtime_svg_validity(js_runtime_result):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(js_runtime_result["svg"])  # raises if malformed
    assert root.tag.endswith("svg")


@requires_node
def test_runtime_mermaid_subgraphs_and_edges(js_runtime_result):
    mermaid = js_runtime_result["mermaid"]
    for tier in ["client", "edge", "compute", "data", "ai", "ops"]:
        assert f"subgraph {tier}Tier" in mermaid, f"missing {tier}Tier subgraph"
    assert "-->" in mermaid, "expected at least one topological edge"
