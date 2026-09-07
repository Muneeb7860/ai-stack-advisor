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

    # Reachability alone does NOT catch a failed contraction, and the first version of this test
    # proved it: an orphaned node has no incoming edge, so a root-first traversal counts it as a
    # root and calls it reached. Removing the contraction line passed all eleven tests.
    #
    # A "nothing may be parentless" rule was the second attempt and was also wrong — once the
    # floors deepened, a CLI tool legitimately reduces to {lang, cicd} with no edges at all,
    # because every node above them was pruned. Being parentless is fine; losing a connection to
    # a surviving ancestor is not.
    #
    # test_contraction_reconnects_across_pruned_nodes below is the assertion that actually bites.


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


@requires_node
def test_contraction_reconnects_across_pruned_nodes():
    """The assertion that separates contraction from deletion, on a case where both ends survive.

    For a static marketing site the spine prunes in the middle: `gateway` sits between `frontend`
    and `cloud`, and `arch` + `computemodel` sit between `cloud` and `lang`. All three are floored
    away. Contraction must therefore produce edges that did not exist in the original graph:

        frontend -> cloud      (gateway removed between them)
        cloud    -> lang       (arch AND computemodel removed between them)

    A naive `nodes.filter(...)` leaves this graph with zero edges, which is exactly what the
    surviving mutation did. Checked on the static site rather than the CLI tool because the CLI
    prunes its whole spine — {lang, cicd} with no edges is correct there and proves nothing.
    """
    g = _graph(STATIC_SITE)
    ids = {n["id"] for n in g["nodes"]}
    assert {"frontend", "cloud", "lang"} <= ids, f"fixture drifted; nodes are {sorted(ids)}"

    pairs = {(e["from"], e["to"]) for e in g["edges"]}
    for a, b in [("frontend", "cloud"), ("cloud", "lang")]:
        assert (a, b) in pairs, (
            f"{a} -> {b} is missing: the node(s) between them were deleted rather than "
            f"contracted, so the graph fell apart. edges={sorted(pairs)}"
        )


@requires_node
def test_the_no_server_floor_does_not_reach_a_server_backed_app():
    """The over-reach direction, and it was missing: widening noServerTier() to return true for
    everything passed every other test in this file. A normal web app must keep the categories
    the floor removes — it has a backend to front, services to mesh, and a tier to cache."""
    ids = {n["id"] for n in _graph(PLAIN_APP)["nodes"]}
    for essential in ("gateway", "mesh", "cache", "db", "containers"):
        assert essential in ids, (
            f"a server-backed app lost its {essential} node — the no-server floor is firing on "
            f"projects that do run a server. nodes={sorted(ids)}"
        )


@requires_node
def test_a_static_site_keeps_its_dns_decision():
    """DNS is floored for a CLI, a desktop app and a browser extension, and deliberately NOT for a
    static site: a marketing page is served from a domain, so where that domain points is a real
    decision. Applying the floor to all four shapes passed every other test here."""
    assert "dns" in {n["id"] for n in _graph(STATIC_SITE)["nodes"]}, (
        "the static site lost its DNS node — a site served from a domain needs that decision"
    )
    assert "dns" not in {n["id"] for n in _graph(CLI_TOOL)["nodes"]}, (
        "a CLI tool has no hostname of its own and should not be shown a DNS pick"
    )


@requires_node
@pytest.mark.parametrize("requirement", [STATIC_SITE, CLI_TOOL])
def test_no_server_shapes_get_no_server_tier_nodes(requirement):
    """Absence-of-"Not applicable" is not enough on its own, and two mutations proved it.

    Removing the mesh or cache floor does not reintroduce a "Not applicable" node — those picks
    fall back to "Not needed yet (revisit past ~10-15 services)" and "Not required yet", which are
    perfectly good advice for an app that has services and a database, and pure noise on a static
    page. They are not caught by the prefix prune, and the node-count bound is loose enough to
    absorb two extra nodes. So the categories themselves are named here.
    """
    ids = {n["id"] for n in _graph(requirement)["nodes"]}
    forbidden = {"gateway", "mesh", "cache", "iam", "computemodel", "containers", "db", "messaging"}
    present = ids & forbidden
    assert not present, (
        f"a shape that runs no server was drawn server-tier nodes: {sorted(present)}"
    )
