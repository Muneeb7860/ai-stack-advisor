"""The architecture diagram must draw the decisions this requirement actually has.

Reported by a user: "flow diagram never matches with cards" and "flow diagram is not minimal but
unnecessary cluster of worthless additions". Both correct, and the second causes the first —
every N() in buildCanonicalArchitectureGraph ran unconditionally, so the graph was a fixed
18-node template. Verified byte-identical for an on-prem requirement with four explicit
exclusions, a CLI tool, and a static marketing site. The cards said "Not applicable — a static
site has no application architecture"; the diagram drew the node anyway, beside AWS API Gateway,
FastAPI/Spring Boot, GPT-4o, MCP servers and Terraform+Kubernetes, for a page of HTML and CSS.

This graph is the single source for the Flow view, the SVG export, the Mermaid export and the
Draw.io export, so these assertions cover all four.
"""
import shutil
from pathlib import Path

import pytest

from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

_STUBS = r"""
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

AI_NODES = {"llm", "mcp", "guardrails", "rag", "vectordb"}

STATIC_SITE = "A simple static marketing website, no backend, just HTML and CSS. Solo developer."
CLI_TOOL = "A command line tool in Python that analyses local log files. Solo developer."
PLAIN_APP = "A B2B web application with Postgres and 500 concurrent users on AWS."
CHATBOT = "A customer support chatbot with RAG over our policy documents."


def _graph(requirement: str) -> dict:
    body = (
        f'const s = detectSignals({requirement!r});\n'
        "const g = buildCanonicalArchitectureGraph(computeRecommendations(s), s);\n"
        "console.log(JSON.stringify({nodes: g.nodes.map(n => ({id:n.id, title:n.title, sub:n.sub})),"
        " edges: g.edges}));"
    ).replace("'", '"')
    main = INDEX_HTML.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]
    return run_node_json(_STUBS + main + "\n" + body)


@requires_node
@pytest.mark.parametrize("requirement", [STATIC_SITE, CLI_TOOL])
def test_the_diagram_draws_no_not_applicable_nodes(requirement):
    """A node whose whole content is "Not applicable" is a decision that does not exist."""
    g = _graph(requirement)
    offenders = [n["id"] for n in g["nodes"]
                 if "not applicable" in (str(n.get("title", "")) + " " + str(n.get("sub", ""))).lower()]
    assert not offenders, f"diagram drew nodes for non-existent decisions: {offenders}"


@requires_node
@pytest.mark.parametrize("requirement", [STATIC_SITE, CLI_TOOL, PLAIN_APP])
def test_a_requirement_with_no_ai_gets_no_ai_nodes(requirement):
    """Gated on the AI signal, not the domain floor — the plain web app is in this list precisely
    because it is not a floor case and was getting an LLM node anyway."""
    ids = {n["id"] for n in _graph(requirement)["nodes"]}
    assert not (ids & AI_NODES), f"diagram drew AI nodes with no AI requirement: {sorted(ids & AI_NODES)}"


@requires_node
def test_an_ai_requirement_keeps_its_ai_nodes():
    ids = {n["id"] for n in _graph(CHATBOT)["nodes"]}
    assert AI_NODES <= ids, f"an AI requirement lost diagram nodes: {sorted(AI_NODES - ids)}"


@requires_node
@pytest.mark.parametrize("requirement", [STATIC_SITE, CLI_TOOL, PLAIN_APP, CHATBOT])
def test_pruning_contracts_edges_rather_than_orphaning_nodes(requirement):
    """The load-bearing property, and the one a naive `nodes.filter(...)` would break.

    The graph is a spine — frontend → gateway → cloud → arch → computemodel → everything else —
    so deleting a node mid-chain strands every node below it with no path in. Each removal
    rewires in-edges to out-edges instead. Two things must hold afterwards: no edge may reference
    a node that is gone, and no node may be unreachable from a root.
    """
    g = _graph(requirement)
    ids = {n["id"] for n in g["nodes"]}

    dangling = [e for e in g["edges"] if e["from"] not in ids or e["to"] not in ids]
    assert not dangling, f"edges reference removed nodes: {dangling}"

    # Reachability alone does NOT catch this, and the first version of this test proved it: an
    # orphaned node has no incoming edge, so a root-first traversal counts it as a root and calls
    # it reached. Deleting the contraction line passed all eleven tests.
    #
    # The property that does catch it: only nodes that legitimately never had a parent may be
    # parentless. `frontend` is the spine head, `gateway` becomes it when frontend is floored
    # away, `dns` has no edges at all (true of the original 18-node graph too), and `guardrails`
    # points INTO llm rather than being pointed at. Anything else with no parent is a node whose
    # parent was pruned without rewiring.
    LEGITIMATELY_PARENTLESS = {"frontend", "gateway", "dns", "guardrails"}
    targets = {e["to"] for e in g["edges"]}
    orphans = {i for i in ids if i not in targets} - LEGITIMATELY_PARENTLESS
    assert not orphans, (
        f"nodes lost their parent without being rewired to its parent: {sorted(orphans)} — "
        "edges were deleted rather than contracted"
    )


@requires_node
def test_the_diagram_shrinks_with_the_requirement():
    """The complaint in one assertion: a static page must not get the same diagram as a chatbot."""
    sizes = {label: len(_graph(req)["nodes"])
             for label, req in [("static", STATIC_SITE), ("cli", CLI_TOOL),
                                ("plain", PLAIN_APP), ("chatbot", CHATBOT)]}
    assert sizes["static"] < sizes["plain"] < sizes["chatbot"], sizes
    assert sizes["cli"] < sizes["plain"], sizes
    # It was 18 for all of them; anything near that for a static page means the prune stopped working.
    assert sizes["static"] <= 10, f"static site still gets {sizes['static']} nodes"
