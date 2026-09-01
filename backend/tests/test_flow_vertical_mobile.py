"""Flow View: single-column layout on narrow screens.

Measured before writing any code: the six-tier horizontal layout spans ~1300px of canvas, so at
375px it auto-fit to scale 0.25 and every node label was unreadable. That is not a styling
problem — a 20-node horizontal graph cannot fit a phone legibly at any zoom that shows its shape.

This is a prerequisite for making Flow the default view (the agreed sequence: fix mobile first,
switch the desktop default second), because defaulting to an unreadable canvas would make the
first impression worse than the boring option.

Nodes reflow into one column ordered by tier, so the pipeline still reads top-to-bottom
(client → edge → compute → data → ai → ops) — the same information the horizontal tiers carry.
Implemented as a layout MODE rather than conditionals through the renderer: edges, canvas size
and the minimap all derive from node x/y, so they follow automatically.
"""
import re
import shutil
from pathlib import Path

import pytest

from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)


def _text() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _main_script() -> str:
    return _text().split("<script>")[2].split("</script>")[0]


def _js(body: str, width: int):
    stubs = f"""
const dummyEl = {{ style:{{}}, classList:{{add(){{}},remove(){{}},toggle(){{}}}}, addEventListener(){{}},
  setAttribute(){{}}, getAttribute:()=>null, appendChild(){{}}, removeChild(){{}}, click(){{}}, focus(){{}},
  querySelector:()=>null, querySelectorAll:()=>[], innerHTML:'', textContent:'', value:'' }};
global.window = {{ innerWidth:{width}, location:{{search:''}}, addEventListener(){{}},
  matchMedia:()=>({{matches:false,addEventListener(){{}}}}) }};
global.document = {{ documentElement:dummyEl, body:dummyEl, querySelector:()=>dummyEl,
  querySelectorAll:()=>[], getElementById:()=>dummyEl, createElement:()=>dummyEl, addEventListener(){{}} }};
global.navigator = {{ clipboard:{{}} }};
global.localStorage = {{ getItem:()=>null, setItem(){{}}, removeItem(){{}} }};
global.fetch = () => Promise.resolve({{ ok:false }});
global.URL = {{ createObjectURL:()=>'', revokeObjectURL(){{}} }};
"""
    return run_node_json(stubs + _main_script() + "\n" + body)


# ------------------------------------------------------------------------- layout mode choice

@requires_node
def test_narrow_viewport_selects_the_vertical_layout():
    assert _js("console.log(JSON.stringify(flowShouldUseVerticalLayout()));", width=375) is True


@requires_node
def test_wide_viewport_keeps_the_horizontal_layout():
    assert _js("console.log(JSON.stringify(flowShouldUseVerticalLayout()));", width=1280) is False


@requires_node
def test_breakpoint_boundary_is_inclusive():
    assert _js("console.log(JSON.stringify(flowShouldUseVerticalLayout()));", width=860) is True
    assert _js("console.log(JSON.stringify(flowShouldUseVerticalLayout()));", width=861) is False


# ------------------------------------------------------------------------- the vertical layout

@requires_node
def test_vertical_layout_stacks_every_node_in_one_column():
    out = _js("""
      const g = {nodes:[
        {id:'frontend', cat:'client'}, {id:'gateway', cat:'edge'},
        {id:'cloud', cat:'compute'}, {id:'db', cat:'data'}
      ], edges:[]};
      const laid = layoutFlowGraphVertical(g);
      console.log(JSON.stringify({xs: laid.nodes.map(n=>n.x), ys: laid.nodes.map(n=>n.y)}));
    """, width=375)
    assert set(out["xs"]) == {0}, "a single column means one x for every node"
    assert out["ys"] == sorted(out["ys"]), "nodes must descend the column, never overlap"
    assert len(set(out["ys"])) == len(out["ys"]), "no two nodes may share a row"


@requires_node
def test_vertical_layout_orders_nodes_by_tier():
    """Top-to-bottom must still read as the pipeline — that ordering IS the information the
    horizontal tiers carried, so losing it would make the mobile view a list rather than a flow."""
    out = _js("""
      const g = {nodes:[
        {id:'observability', cat:'ops'}, {id:'db', cat:'data'},
        {id:'frontend', cat:'client'}, {id:'llm', cat:'ai'},
        {id:'cloud', cat:'compute'}, {id:'gateway', cat:'edge'}
      ], edges:[]};
      const laid = layoutFlowGraphVertical(g);
      console.log(JSON.stringify(laid.nodes.sort((a,b)=>a.y-b.y).map(n=>n.cat)));
    """, width=375)
    assert out == ["client", "edge", "compute", "data", "ai", "ops"]


@requires_node
def test_vertical_layout_still_attaches_the_tier_colour():
    out = _js("""
      const laid = layoutFlowGraphVertical({nodes:[{id:'db', cat:'data'}], edges:[]});
      console.log(JSON.stringify(!!laid.nodes[0].color));
    """, width=375)
    assert out is True


@requires_node
def test_edges_are_preserved_through_the_vertical_layout():
    out = _js("""
      const laid = layoutFlowGraphVertical({nodes:[{id:'a',cat:'client'},{id:'b',cat:'edge'}],
                                            edges:[{from:'a',to:'b'}]});
      console.log(JSON.stringify(laid.edges.length));
    """, width=375)
    assert out == 1


# --------------------------------------------------------- ports and connectors follow the axis

def test_node_anchors_branch_on_the_layout_axis():
    """Connecting a stacked column through left/right ports would send every edge looping out to
    the side and back."""
    text = _text()
    m = re.search(r"function flowNodeAnchor\(id, side\)\{(.*?)\n\}", text, re.S)
    assert m, "flowNodeAnchor not found"
    assert "flowState.vertical" in m.group(1)


def test_edge_curves_branch_on_the_layout_axis():
    """A horizontal control-point offset in the vertical layout would bow every edge sideways
    out of the column instead of flowing down it."""
    text = _text()
    assert "flowState.vertical" in text
    assert re.search(r"C\$\{s\.x\},\$\{s\.y\+dy\}", text), "vertical bezier control points missing"


# ------------------------------------------------------ the fit bug that caused the 0.25 scale

@requires_node
def test_fit_uses_width_only_in_the_vertical_layout():
    """The actual root cause of the illegible render: setView('flow') calls flowFit(), which fit
    BOTH axes — dividing a ~2200px-tall column into a ~560px viewport gave scale 0.25. A column
    is meant to be scrolled, not shrunk to fit.

    Exercises flowFit rather than grepping its body: a first attempt at this test asserted only
    that the string "flowState.vertical" appeared, which a mutation restoring the both-axes fit
    passed cleanly. Behaviour, not tokens."""
    out = _js("""
      // 20 nodes in one column: 270 wide, ~2200 tall — the real mobile shape.
      const nodes = Array.from({length:20}, (_,i)=>({id:'n'+i, cat:'compute', x:0, y:i*110}));
      flowState.graph = {nodes, edges:[]};
      flowState.vertical = true;
      const vp = { clientWidth: 341, clientHeight: 558 };
      global.document.getElementById = (id) => id === 'flowViewport' ? vp : dummyEl;
      flowFit();
      console.log(JSON.stringify({zoom: flowState.zoom, panY: flowState.panY}));
    """, width=375)
    # Fitting height too would give ~558/2200 = 0.25, which is what made every label unreadable.
    assert out["zoom"] > 0.9, f"vertical fit must not shrink to fit height, got {out['zoom']}"
    assert out["panY"] < 60, "a column should be anchored near the top, not vertically centred"


@requires_node
def test_horizontal_fit_still_fits_both_axes():
    """The desktop behaviour must be untouched — there, fitting both axes is correct."""
    out = _js("""
      const nodes = [{id:'a',cat:'client',x:0,y:0},{id:'b',cat:'ops',x:1200,y:900}];
      flowState.graph = {nodes, edges:[]};
      flowState.vertical = false;
      const vp = { clientWidth: 900, clientHeight: 500 };
      global.document.getElementById = (id) => id === 'flowViewport' ? vp : dummyEl;
      flowFit();
      console.log(JSON.stringify({zoom: flowState.zoom}));
    """, width=1280)
    # 500-60 over a ~970-tall graph is the binding constraint — well under 1.
    assert out["zoom"] < 0.6, f"horizontal fit must still respect height, got {out['zoom']}"


def test_fit_and_minimap_use_the_layout_aware_node_width():
    """Both hardcoded the horizontal 208px node width, which understates the graph's extent in
    the vertical layout where nodes are wider."""
    text = _text()
    assert "function flowNodeWidth()" in text
    assert text.count("flowNodeWidth()") >= 3, "flowFit, the minimap and the anchor all need it"


# --------------------------------------------------------------------- overlays that collided

def test_legend_and_toolbar_are_hidden_on_narrow_screens():
    """Both are absolutely positioned over the canvas, and in the vertical layout the column
    spans nearly the full viewport width — so there is no free corner and they rendered on top of
    nodes. The legend is also redundant there: each node prints its own tier as text."""
    text = _text()
    # There are several 860px media blocks in this file; anchor to the flow-view one the same way
    # test_phase5c_flowview_mobile.py does, rather than matching whichever comes first.
    m = re.search(r"\.flow-hint\{[^}]*\}\s*(?:/\*.*?\*/\s*)?@media \(max-width:860px\)\{(.*?)\n  \}", text, re.S)
    assert m, "the flow-view 860px media block was not found"
    block = m.group(1)
    assert "#flowLegend{display:none;}" in block
    assert ".flow-toolbar{display:none;}" in block
    # Additive only — the base rules (declared earlier) must keep their own declarations.
    for sel in (r"#flowLegend", r"\.flow-toolbar"):
        base = re.search(sel + r"\{([^}]*)\}", text)
        assert base and "position:absolute" in base.group(1), f"{sel} base rule was altered"


# ------------------------------------------------------------------------- long node titles

@requires_node
def test_node_titles_embedding_a_pick_are_shortened_but_keep_their_label():
    """Three nodes carry "Label — pick" as the title rather than splitting across title/sub, so
    the whole pick with its caveats became the heading — 114 characters for IAM, four wrapped
    lines on a phone. Running essentialName over the whole string would drop the pick entirely
    for exactly the nodes that have nowhere else to show it."""
    out = _js("""
      console.log(JSON.stringify([
        flowNodeTitle('Identity & Access — OneLogin (One Identity) — or cloud-native (AWS Cognito / Firebase Auth) for the simplest cases'),
        flowNodeTitle('LLM — OpenAI GPT (mid tier, e.g. GPT-4o class)'),
        flowNodeTitle('Cloud Provider'),
        flowNodeTitle(null)
      ]));
    """, width=375)
    assert out[0] == "Identity & Access — OneLogin"
    assert out[1] == "LLM — OpenAI GPT"
    assert out[2] == "Cloud Provider", "a title with no embedded pick must pass through untouched"
    assert out[3] == ""


def test_node_render_actually_uses_the_shortened_title():
    """Wiring, not just the unit. A first pass tested flowNodeTitle() in isolation and a mutation
    reverting the renderer back to raw n.title passed cleanly — the helper was correct and
    unused."""
    assert "${flowNodeTitle(n.title)}" in _text()


def test_node_render_actually_uses_the_shortened_sub():
    """Same wiring gap for the sub line, which is what made nodes average 76 characters."""
    assert "truncateFlowText(essentialName(n.sub),30)" in _text()


# --------------------------------------------------------------- crossing the breakpoint live

def test_a_resize_across_the_breakpoint_relayouts():
    """The flow layout is now viewport-dependent, which it never was before — so rotating a phone
    or dragging a window wider would otherwise strand the graph in the wrong layout until the
    next analysis. Guarded to fire only when the mode actually flips, not on every resize tick."""
    text = _text()
    assert "window.addEventListener('resize'" in text
    m = re.search(r"window\.addEventListener\('resize', \(\) => \{(.*?)\n  \}\);", text, re.S)
    assert m, "resize handler not found"
    body = m.group(1)
    assert "flowShouldUseVerticalLayout() === !!flowState.vertical) return" in body, \
        "must no-op unless the layout mode actually changed"
    assert "renderFlow(layoutFlowGraph(flowState.graph))" in body
