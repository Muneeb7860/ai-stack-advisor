"""
Architecture invariant test for the hexagonal graph refactor in index.html.

There's no JS test runner in this frameworkless project (AGENTS.md forbids adding a
build step), so this file has two layers:

  Layer A — static-analysis contract tests, in the spirit of Swish_App's
  HexagonalArchitectureTest.java: read index.html as text and assert the core domain
  function stays pure, and that outbound adapters at least reference the canonical
  graph builder rather than re-deriving their own reduced topology. These are cheap
  and always run, but they can't catch a function that calls
  buildCanonicalArchitectureGraph(...) and then still produces broken output.

  Layer B — runtime execution tests: actually run the extracted <script> block in
  Node with a minimal DOM/window/fetch stub, call the real functions against a live
  scenario, and validate the real output (node schema, XML/SVG parseability, Mermaid
  subgraph presence). These require a `node` binary on PATH and are skipped — not
  failed — when one isn't available, so the pure-Python pytest baseline in AGENTS.md
  still passes on a machine without Node installed.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
NODE_AVAILABLE = shutil.which("node") is not None
requires_node = pytest.mark.skipif(
    not NODE_AVAILABLE, reason="Node.js runtime required for frontend JavaScript execution"
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
        "buildCanonicalArchitectureGraph(ctx) is the domain core of the hexagonal "
        "refactor and must exist as a standalone function."
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

REQUIRED_NODE_FIELDS = ["id", "cat", "title", "sub", "conf", "why", "persona", "detail"]

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
const graph = buildCanonicalArchitectureGraph(rec);
const flowGraph = layoutFlowGraph(graph);

console.log(JSON.stringify({
  nodeCount: graph.nodes.length,
  edgeCount: graph.edges.length,
  nodeFieldSets: graph.nodes.map(n => Object.keys(n).sort()),
  flowNodesHaveXYColor: flowGraph.nodes.every(n =>
    typeof n.x === "number" && typeof n.y === "number" && typeof n.color === "string"),
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
