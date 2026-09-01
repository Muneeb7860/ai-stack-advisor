"""Document ingestion (PRD / BRD / spec) — ports and adapters.

Implements docs/design/DOCUMENT_INGESTION_SCOPE.md. The scope exists because the obvious
implementation — extract the text, feed it to the engine — makes recommendations dramatically
WORSE on exactly the documents it targets. Measured before any code was written: appending the
sections every real PRD has (Alternatives Rejected, Non-Goals, Glossary) to a correct requirement
took fired signals from 6 to 13, all seven extras false, and flipped 24 picks — turning an
AWS/serverless/EKS stack into on-premises bare metal, silently.

The cause was one sentence: "an on-premise air-gapped deployment ... is explicitly out of scope."
`stripNegations` handles adjacent negation and nothing else, correctly, because it was built for
short prompts where that is the right scope.

So the feature is not extraction, it is deciding which parts of a document are requirements.
The split follows the line where the two jobs actually differ:

    ADAPTER (format-specific, pluggable) : bytes  -> blocks [{heading, text}]
    DOMAIN  (format-blind, the real work): blocks -> which blocks are requirements

The port returns BLOCKS rather than a flat string, and that is the load-bearing decision: a flat
string forces classification into every adapter, written once per format and missing entirely from
any adapter added later.

The assertion that matters here is test_an_ingested_document_matches_the_equivalent_short_prompt.
A test that only checked "headings were detected" would pass while every pick stayed wrong.
"""
import json
import re
import shutil
from pathlib import Path

import pytest

from tests.node_harness import run_node_json

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

_STUBS = r"""
const d={style:{},classList:{add(){},remove(){},toggle(){},contains:()=>false},addEventListener(){},
  setAttribute(){},getAttribute:()=>null,querySelector:()=>d,querySelectorAll:()=>[],innerHTML:'',textContent:''};
global.window={innerWidth:1280,location:{search:''},addEventListener(){},matchMedia:()=>({matches:false,addEventListener(){}})};
global.document={documentElement:d,body:d,querySelector:()=>d,querySelectorAll:()=>[],
  getElementById:()=>d,createElement:()=>d,addEventListener(){}};
global.navigator={clipboard:{}};global.localStorage={getItem:()=>null,setItem(){},removeItem(){}};
global.fetch=()=>Promise.resolve({ok:false});global.URL={createObjectURL:()=>'',revokeObjectURL(){}};
global.requestAnimationFrame=(fn)=>fn();
"""


def _text() -> str:
    return INDEX.read_text(encoding="utf-8")


def _js(body: str):
    return run_node_json(_STUBS + _text().split("<script>")[2].split("</script>")[0] + "\n" + body)


SHORT = ("A healthcare patient portal. HIPAA compliance required. "
         "Peak traffic 25,000 concurrent users during enrollment. Team of 4 Python engineers.")

PRD = SHORT + """

Section 7 — Alternatives Considered and Rejected
We evaluated Kafka for the event bus but rejected it as operationally heavy for our team size.
We considered a multi-region active-active deployment and decided against it for v1.
An on-premise air-gapped deployment was discussed but is explicitly out of scope.

## Non-Goals
This release will not support real-time streaming analytics.

GLOSSARY
PCI DSS: payment card standard, not applicable to this product.
"""


# ------------------------------------------------------ the property the feature has to hold

@requires_node
def test_an_ingested_document_matches_the_equivalent_short_prompt():
    """The load-bearing assertion, and the reason this feature is worth building.

    Not "were headings found" — that can pass while every recommendation is wrong. The property is
    that a document carrying the same requirements as a short prompt produces the same answer.
    """
    out = _js("""
      const SHORT = %s, PRD = %s;
      const ing = ingestDocument(PRD, 'Healthcare_PRD.md');
      const p = t => computeRecommendations(detectSignals(t));
      const diff = (x, y) => Object.keys(x).filter(k => x[k] && x[k].v && y[k] && x[k].v !== y[k].v);
      console.log(JSON.stringify({
        rawWrong: diff(p(SHORT), p(PRD)).length,
        ingestedWrong: diff(p(SHORT), p(ing.text)),
        cloudRaw: p(PRD).cloud.v, cloudIngested: p(ing.text).cloud.v
      }));
    """ % (json.dumps(SHORT), json.dumps(PRD)))
    assert out["rawWrong"] > 20, (
        "the raw-text regression this feature exists to prevent no longer reproduces — if the "
        "engine changed, re-measure before trusting the rest of this file"
    )
    assert out["ingestedWrong"] == [], (
        f"ingestion did not recover the correct recommendation; still wrong: {out['ingestedWrong']}"
    )
    assert out["cloudIngested"] == "AWS" and "On-prem" in out["cloudRaw"]


# --------------------------------------------------------------------- heading detection

@requires_node
@pytest.mark.parametrize("heading,style", [
    ("Section 7 — Alternatives Considered and Rejected", "Section N — em dash"),
    ("## Non-Goals", "markdown"),
    ("GLOSSARY", "all caps"),
    ("7.1 Alternatives Considered", "numbered"),
    ("Appendix B — Prior Art", "appendix"),
])
def test_each_heading_style_is_recognised(heading, style):
    """Enumerated rather than folded into one clever regex, because two earlier prototypes each
    caught a DIFFERENT subset and one broke a style the other handled. Every style found in the
    wild is added here rather than the regex being tuned by eye."""
    out = _js(f"console.log(JSON.stringify(docDetectHeading({json.dumps(heading)})));")
    assert out is not None, f"{style} heading not recognised: {heading!r}"


@requires_node
@pytest.mark.parametrize("line", [
    "PCI DSS: payment card standard, not applicable to this product.",
    "We evaluated Kafka for the event bus but rejected it as operationally heavy for our team.",
    "The system must retain audit logs for seven years to satisfy HIPAA.",
])
def test_ordinary_prose_is_not_mistaken_for_a_heading(line):
    """The opposite failure, and the more damaging one: a sentence treated as a heading splits a
    requirement in half. The glossary line below genuinely matched the all-caps pattern on its
    first words during development."""
    out = _js(f"console.log(JSON.stringify(docDetectHeading({json.dumps(line)})));")
    assert out is None, f"prose misread as a heading: {line!r}"


# ------------------------------------------------------------------------- classification

@requires_node
@pytest.mark.parametrize("heading", [
    "Non-Goals", "Out of Scope", "Glossary", "Alternatives Considered and Rejected",
    "Future Work", "Appendix A", "Revision History",
])
def test_non_requirement_sections_are_excluded(heading):
    out = _js(f"console.log(JSON.stringify(isRequirementBlock({{heading: {json.dumps(heading)}, text: 'x'}})));")
    assert out is False


@requires_node
@pytest.mark.parametrize("heading", [
    "Functional Requirements", "Scale and Performance", "Compliance", "Security Requirements",
])
def test_requirement_sections_are_kept(heading):
    out = _js(f"console.log(JSON.stringify(isRequirementBlock({{heading: {json.dumps(heading)}, text: 'x'}})));")
    assert out is True


@requires_node
def test_untitled_prose_counts_as_a_requirement():
    """A document with no headings at all must not be classified into nothing."""
    out = _js("console.log(JSON.stringify(isRequirementBlock({heading: null, text: 'We need HIPAA.'})));")
    assert out is True


@requires_node
def test_classification_reads_the_heading_not_the_body():
    """A requirements section may legitimately discuss what was rejected — "we need Postgres, not
    MySQL". Matching bodies would drop real requirements for containing the word."""
    out = _js("""
      console.log(JSON.stringify(isRequirementBlock(
        {heading: 'Database Requirements', text: 'We rejected MySQL and are out of scope for Oracle.'})));
    """)
    assert out is True


# ------------------------------------------------------------------------ what was dropped

@requires_node
def test_suppressed_signals_exclude_ones_the_kept_text_still_establishes():
    """A first version listed every signal the excluded blocks produced, which included
    `compliance` — fired by the glossary, but also by "HIPAA compliance required" in the actual
    requirement. Reporting that as suppressed claims an effect the classification did not have,
    which is the same over-claim this whole feature exists to avoid."""
    out = _js("""
      const ing = ingestDocument(%s, 'prd.md');
      console.log(JSON.stringify({suppressed: ing.suppressedSignals,
                                  keptHasCompliance: Object.keys(ing.provenance).includes('compliance')}));
    """ % json.dumps(PRD))
    assert "onPrem" in out["suppressed"], "the on-prem false positive should be reported as removed"
    assert out["keptHasCompliance"] is True
    assert "compliance" not in out["suppressed"], (
        "compliance still fires from the kept text, so listing it as suppressed over-claims"
    )


@requires_node
def test_provenance_names_the_block_a_signal_came_from():
    """Obtained by re-running detectSignals per block rather than exposing its keyword tables, so
    it stays correct automatically when a keyword list changes."""
    out = _js("""
      const ing = ingestDocument(%s, 'prd.md');
      console.log(JSON.stringify(ing.provenance.compliance || null));
    """ % json.dumps(PRD))
    assert out, "compliance has no recorded provenance"
    assert "excerpt" in out[0] and "heading" in out[0]


@requires_node
def test_the_dropped_sections_are_reported_not_silently_discarded():
    out = _js("""
      const ing = ingestDocument(%s, 'prd.md');
      console.log(JSON.stringify(ing.excludedBlocks.map(b => b.heading)));
    """ % json.dumps(PRD))
    assert set(out) == {"Alternatives Considered and Rejected", "Non-Goals", "GLOSSARY"}


# ----------------------------------------------------------------------------- the port

def test_the_port_returns_blocks_not_a_flat_string():
    """The load-bearing architectural decision. A flat string would force classification into every
    adapter — written once per format, and absent from any adapter added later."""
    m = re.search(r"registerDocumentAdapter\(\{(.*?)\n\}\);", _text(), re.S)
    assert m, "no built-in adapter registered"
    body = m.group(1)
    assert "blocks:" in body and "wordCount:" in body, "extract() must return blocks, not text"


@requires_node
def test_an_adapter_must_declare_the_full_port():
    """A half-implemented adapter should fail at registration, not at the first upload."""
    out = _js("""
      let threw = false;
      try { registerDocumentAdapter({id: 'broken'}); } catch (e) { threw = true; }
      console.log(JSON.stringify(threw));
    """)
    assert out is True


@requires_node
def test_a_broken_adapter_does_not_take_down_the_registry():
    """Third-party adapters are the point of the extension seam; one throwing in accepts() must
    not make every other format unusable."""
    out = _js("""
      registerDocumentAdapter({id:'boom', accepts(){ throw new Error('nope'); }, extract(){ return {blocks:[],wordCount:0}; }});
      const ing = ingestDocument('A healthcare portal. HIPAA required.', 'prd.md');
      console.log(JSON.stringify(ing !== null && ing.text.length > 0));
    """)
    assert out is True


@requires_node
def test_the_builtin_adapter_claims_extensionless_and_unknown_files():
    """Otherwise parseDiagramInput's raw-line fallback keeps them, and a PRD becomes fifteen chips
    of prose."""
    out = _js("""
      console.log(JSON.stringify(['prd.md','spec.txt','REQUIREMENTS','notes.rst']
        .map(f => { const a = documentAdapterFor(f, 'hello'); return a ? a.id : null; })));
    """)
    assert out == ["plaintext"] * 4

# --------------------------------------------------------------------------- wiring

@requires_node
def test_a_document_routes_to_the_document_path_not_the_raw_line_fallback():
    """The routing collision found while reviewing the scope: parseDiagramInput's old fallback
    turned the first 15 lines of anything into chips, so a PRD arrived as fifteen chips of prose.
    Order is deliberate — manifests on exact filenames, diagrams on extension or opening syntax,
    documents last."""
    out = _js("""
      const r = parseDiagramInput(%s, 'Healthcare_PRD.md');
      console.log(JSON.stringify({type: r.type, hasDoc: !!r.document, chips: r.entities.length}));
    """ % json.dumps(PRD))
    assert out["type"] == "document" and out["hasDoc"] is True
    assert out["chips"] == 0, "a document must not also produce component chips"


@requires_node
@pytest.mark.parametrize("filename,content,expected", [
    ("package.json", '{"dependencies":{"pg":"^8"}}', "manifest"),
    ("arch.mmd", "graph TD\n  A[API] --> B[DB]\n", "mermaid"),
    ("prd.md", "# Requirements\nWe need HIPAA compliance.\n", "document"),
])
def test_routing_precedence_is_preserved(filename, content, expected):
    """Adding documents must not steal files the other two entry modes already claimed."""
    out = _js(f"console.log(JSON.stringify(parseDiagramInput({json.dumps(content)}, {json.dumps(filename)}).type));")
    assert out == expected


@requires_node
def test_unchecking_a_signal_records_a_correction_in_the_requirement_text():
    """The correction is appended as an explicit statement rather than applied by editing the
    user's document. The file stays the source of truth, and the change is visible in the text the
    engine actually receives instead of being silently subtracted."""
    out = _js("""
      uploadedDocument = ingestDocument(%s, 'prd.md');
      documentSignalOptOut = {};
      onDocumentSignalToggle('compliance', false);
      const captured = {};
      setAnalysis = (text) => { captured.text = text; };
      document.getElementById = () => ({ value:'', scrollIntoView(){}, style:{} });
      analyzeDiagramEntities();
      console.log(JSON.stringify({
        mentionsCorrection: /Corrections confirmed by the reader/.test(captured.text),
        namesSignal: /compliance/.test(captured.text)
      }));
    """ % json.dumps(PRD))
    assert out["mentionsCorrection"] is True and out["namesSignal"] is True


@requires_node
def test_a_new_upload_does_not_inherit_the_previous_corrections():
    doc = json.dumps("# Requirements\nWe need HIPAA compliance.")
    out = _js("""
      documentSignalOptOut = {onPrem: true};
      displayDiagramPreview('b.md', 'document', [], ingestDocument(%s, 'b.md'));
      console.log(JSON.stringify(Object.keys(documentSignalOptOut)));
    """ % doc)
    assert out == []


@requires_node
def test_the_confirm_step_shows_provenance_and_what_was_dropped():
    """Both halves matter. Provenance is what makes a wrong inference visible; the dropped list is
    what stops classification being a silent edit of the user's document.

    Renders the actual HTML rather than searching the function source. A first version asserted
    that the word "provenance" appeared in the body, which stayed true when the rendered output
    was changed to show signals with no source at all — the exact string-presence trap this suite
    keeps relearning.
    """
    out = _js("""
      const ing = ingestDocument(%s, 'prd.md');
      const html = renderDocumentConfirmHtml(ing);
      console.log(JSON.stringify({
        showsSourceHeading: html.includes('Alternatives Considered') || /from\s*[“"]/.test(html),
        showsExcerpt: html.includes('HIPAA'),
        listsDropped: html.includes('Non-Goals') && html.includes('GLOSSARY'),
        namesSuppressed: html.includes('onPrem'),
        everySignalRemovable: (html.match(/onDocumentSignalToggle/g) || []).length
                              >= Object.keys(ing.provenance).length
      }));
    """ % json.dumps(PRD))
    assert out["showsExcerpt"], "the confirm step must quote the wording that produced a signal"
    assert out["listsDropped"], "the dropped sections must be named, not silently removed"
    assert out["namesSuppressed"], "must state what the dropped sections would have contributed"
    assert out["everySignalRemovable"], "every inferred signal needs its own control"


def test_the_confirm_step_escapes_document_text():
    """Document content is untrusted input rendered into innerHTML — a PRD containing markup must
    not become markup."""
    m = re.search(r"function renderDocumentConfirmHtml\(doc\)\{(.*?)\n\}", _text(), re.S)
    body = m.group(1)
    assert "&amp;" in body and "&lt;" in body, "no HTML escaping in the confirm renderer"
    assert re.search(r"esc\(\(?src\.excerpt", body) or "esc((src.excerpt" in body, \
        "the document excerpt must be escaped"
