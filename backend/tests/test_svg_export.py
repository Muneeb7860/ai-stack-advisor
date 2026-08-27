"""
The SVG export is a document artefact — it gets pasted into a design doc or a deck, where nobody
can hover a node to recover what a clipped label said. So the properties worth testing are layout
correctness and honesty about provenance, not just "it parses".

It replaced a 28-line renderer that stacked every node in one 400px column with no edges, no
grouping and no legend, on a near-black background behind light-filled tier boxes. The layout is
modelled on diagrams/reference-architecture/architecture-layers.svg, and driven entirely by
buildCanonicalArchitectureGraph() so it cannot drift from Flow View, Mermaid and Draw.io.

Text overflow is the failure this file exists for: SVG does not wrap or clip text, so an
over-long label runs silently across the whole canvas. The first version truncated node subtitles
and not titles, and a 109-character IAM title ran clear across the diagram — valid XML, correct
node count, unreadable output. Every assertion about width below is there because that happened.
"""
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
SVG_NS = "{http://www.w3.org/2000/svg}"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

# Scenarios chosen to move the layout: none, all-excluded, on-prem, minimal, and one with a title
# long enough to have broken the first implementation.
SCENARIOS = {
    "rich": "Enterprise fintech platform, high traffic, PCI compliance, real-time fraud detection, RAG chatbot over policy documents.",
    "zero_signals": "12345",
    "everything_excluded": "I only need a heart-disease model in a Jupyter Notebook. No website, no API, no database, no cloud, no microservices, no RAG, no LLM is needed.",
    "air_gapped": "Government defense contractor, air-gapped, cannot use any public cloud, team of 20.",
    "minimal": "Early-stage startup, 3 engineers, MVP web app.",
    "long_titles": "Enterprise platform needing Ping Identity and ForgeRock with SOC2 and PCI compliance and multi-region.",
}

# Same approximation the exporter uses to fit text (see CHAR_W there). Both are estimates of the
# same unmeasurable quantity, so the test can only catch gross overflow — which is the failure
# mode that matters. A label 3px over is invisible; one running the width of the canvas is not.
CHAR_W = 0.55

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
for (const b of src.split('<script>').slice(1).map(b => b.split('</script>')[0])) {
  try { (0, eval)(b); } catch (e) {}
}
"""


@pytest.fixture(scope="module")
def svgs():
    out = run_node_json(
        f"const INDEX_PATH = {str(INDEX_HTML)!r};\n" + _STUBS + f"""
        const SCENARIOS = {__import__('json').dumps(SCENARIOS)};
        const out = {{}};
        for (const [name, text] of Object.entries(SCENARIOS)) {{
          const s = detectSignals(text);
          out[name] = generateSvgDiagram(computeRecommendations(s), s);
        }}
        console.log(JSON.stringify(out));
        """
    )
    return {k: ET.fromstring(v) for k, v in out.items()}


def _canvas(root):
    return [float(v) for v in root.get("viewBox").split()[2:]]


@requires_node
@pytest.mark.parametrize("name", list(SCENARIOS))
def test_svg_is_well_formed_and_sized(name, svgs):
    root = svgs[name]
    assert root.tag == f"{SVG_NS}svg"
    w, h = _canvas(root)
    assert w > 0 and h > 0


@requires_node
@pytest.mark.parametrize("name", list(SCENARIOS))
def test_no_text_runs_off_the_canvas(name, svgs):
    """The defect this suite exists for. SVG neither wraps nor clips, so an unfitted label is
    silently unreadable rather than loudly broken."""
    root = svgs[name]
    w, _ = _canvas(root)
    offenders = []
    for el in root.iter(f"{SVG_NS}text"):
        if el.get("text-anchor") == "end":
            continue
        text, size = el.text or "", float(el.get("font-size") or 12)
        est = float(el.get("x") or 0) + len(text) * size * CHAR_W
        if est > w - 12:
            offenders.append((round(est), text[:60]))
    assert not offenders, f"text estimated past the {w}px canvas: {offenders}"


@requires_node
@pytest.mark.parametrize("name", list(SCENARIOS))
def test_nothing_is_drawn_below_the_canvas(name, svgs):
    root = svgs[name]
    _, h = _canvas(root)
    spill = [
        (el.get("y"), el.get("height")) for el in root.iter(f"{SVG_NS}rect")
        if float(el.get("y") or 0) + float(el.get("height") or 0) > h
    ]
    assert not spill, f"rects extend past the {h}px canvas: {spill}"


@requires_node
def test_every_component_from_the_graph_appears(svgs):
    """A diagram that silently drops nodes is worse than one that is ugly — the reader cannot tell
    the difference between 'not recommended' and 'did not fit'."""
    root = svgs["rich"]
    desc = root.find(f"{SVG_NS}desc").text
    stated = int(re.search(r"(\d+) components", root.find(f"{SVG_NS}title").text).group(1))
    # One titled pill per component, plus band headings; count the bold 12.5px titles.
    pills = [el for el in root.iter(f"{SVG_NS}text") if el.get("font-size") == "12.5" and el.get("font-weight") == "700"]
    assert len(pills) == stated, f"title says {stated} components, {len(pills)} pills drawn"
    assert "request path" in desc


@requires_node
def test_layers_are_numbered_and_named_from_the_tier_model(svgs):
    root = svgs["rich"]
    labels = [el.text for el in root.iter(f"{SVG_NS}text") if (el.get("letter-spacing") or "") == "0.6"]
    assert "CLIENT" in labels and "COMPUTE" in labels and "DATA" in labels
    assert "CROSS-CUTTING" in labels, "the ops tier wraps every layer and is drawn beside the flow"
    assert "OPS" not in labels, "ops must not also appear as a numbered band in the request path"


@requires_node
def test_inter_layer_labels_come_from_the_graph_not_from_prose(svgs):
    """Arrow labels are looked up in EDGE_LABELS by the edge's own from->to key, so the picture
    cannot claim a relationship the canonical graph does not contain."""
    root = svgs["rich"]
    texts = {el.text for el in root.iter(f"{SVG_NS}text")}
    source = INDEX_HTML.read_text(encoding="utf-8")
    known = set(re.findall(r"'[a-z]+->[a-z]+': '([^']+)'", source))
    drawn = {t for t in texts if t in known}
    assert drawn, "no inter-layer edge labels were drawn"


@requires_node
@pytest.mark.parametrize("name", list(SCENARIOS))
def test_accessibility_metadata_is_present(name, svgs):
    """Criticised the source diagrams for lacking this; the generated one should not."""
    root = svgs[name]
    assert root.get("role") == "img"
    assert root.find(f"{SVG_NS}title") is not None and root.find(f"{SVG_NS}title").text
    assert root.find(f"{SVG_NS}desc") is not None and root.find(f"{SVG_NS}desc").text


@requires_node
def test_export_states_what_it_is(svgs):
    """The product's standing disclaimer — a heuristic advisor, not an architecture review — has to
    survive being pasted into someone else's document, because that is where it stops being obvious."""
    root = svgs["rich"]
    texts = " ".join(el.text or "" for el in root.iter(f"{SVG_NS}text"))
    assert "heuristic" in texts and "validate" in texts


def test_exporter_still_consumes_the_canonical_graph():
    """Duplicated from the hexagon contract on purpose: this is the property that stops the export
    becoming a second, hand-maintained picture of the same architecture."""
    source = INDEX_HTML.read_text(encoding="utf-8")
    body = source[source.index("function generateSvgDiagram("):]
    body = body[:body.index("\n}")]
    assert "buildCanonicalArchitectureGraph(" in body
    assert "TIER_ORDER" in body and "EDGE_LABELS" in body
