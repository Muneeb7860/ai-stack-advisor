"""
Static contract test for the n8n-style visual pass on Flow View (drawFlowEdges, .flow-node,
#flowCanvas). Deliberately NOT a runtime/DOM test — this file's job is only to lock in the
specific CSS/SVG properties the visual pass introduced, so a future edit that quietly reverts
one (e.g. someone "cleaning up" the port-nub pseudo-elements without realising they're load-
bearing for the look) fails loudly instead of just looking different in a screenshot nobody
runs in CI.

Verified visually in a real browser before this was written: category dot badges, port nubs at
each node edge, tinted bezier connectors with endpoint markers, and the dot-grid canvas all
render correctly and are not clipped by node overflow.
"""
import re
from pathlib import Path

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"


def _source() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def test_flow_canvas_has_a_dot_grid_background():
    """The dot grid lives on #flowCanvas (not #flowViewport) so it pans/zooms WITH the nodes —
    putting it on the fixed viewport instead would make the canvas feel static underneath moving
    nodes rather than giving a real sense of position."""
    src = _source()
    canvas_block = src[src.index("#flowCanvas{"):]
    canvas_block = canvas_block[:canvas_block.index("}") + 1]
    assert "radial-gradient" in canvas_block
    assert "background-size" in canvas_block


def test_flow_node_has_port_nubs_on_both_sides():
    src = _source()
    assert ".flow-node::before, .flow-node::after{" in src
    before_after = src[src.index(".flow-node::before, .flow-node::after{"):]
    before_after = before_after[:before_after.index("}") + 1]
    assert "border-radius:50%" in before_after
    # Left and right nubs must not be clipped — .flow-node must not set overflow:hidden, or the
    # negative-offset ::before/::after (sitting half outside the node's own box) disappear.
    node_rule = re.search(r"\.flow-node\{([^}]*)\}", src)
    assert node_rule and "overflow:hidden" not in node_rule.group(1)


def test_flow_node_category_badge_is_a_dot_not_a_bar():
    """Replaced the old flat border-left accent stripe with a small rounded-square swatch next to
    the category label — closer to n8n's per-node icon tile."""
    src = _source()
    assert ".flow-node .fn-cat::before{" in src
    assert "border-left:3px solid var(--cat-color" not in src


def test_flow_edges_are_tinted_by_source_category_with_endpoint_markers():
    src = _source()
    body = src[src.index("function drawFlowEdges(){"):]
    body = body[:body.index("\nfunction attachFlowNodeHandlers")]
    assert "srcNode.color" in body or "srcNode && srcNode.color" in body
    assert body.count("<circle") >= 2, "each edge should mark both its start and end point"
    assert "pointer-events:none" in src[src.index("#flowSvg{"):src.index("#flowSvg{") + 200], (
        "edges are decoration only — this must stay true or click-through to nodes underneath breaks"
    )
