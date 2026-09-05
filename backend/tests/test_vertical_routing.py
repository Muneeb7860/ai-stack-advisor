"""Each vertical must route to the verticals document, not just the ones with rare vocabulary.

Doc 20 covers eighteen verticals. Its Signals section was written as one flat list, and a single
routing chunk spanning eighteen unrelated industries embeds to the centroid of healthcare, banking,
telecom, hospitality, defence and agriculture at once — which points nowhere.

Measured, not inferred. For "Guests book rooms across several OTAs and rates must stay in sync":

    routing candidates (top 4)      05-multi-tenant-saas, 02-video-audio, 01-realtime, 17-multi-cloud
    doc 20                          absent from the top 6 entirely

Narrowing the Signals section to hospitality terms alone moved doc 20 from unrouted to routing
rank 1 and result rank 1. That experiment is what identified dilution as the cause, rather than
content ranking or the abstention gate — both of which had already been suspected and neither of
which was responsible.

The fix splits Signals into `###` subsections by vertical cluster. ROUTING_HEADER_PATTERN matches
any header containing "signals/triggers", and the chunker splits on ##/###, so each subsection
becomes its own routing chunk: several coherent centroids inside one document, rather than one
meaningless average. No change to retrieval.py was needed.
"""
import pytest

from app.retrieval import retrieve

from ollama_gate import requires_ollama


@requires_ollama
@pytest.mark.parametrize("query", [
    "Guests book rooms across several OTAs and rates must stay in sync.",
    "Track shipments and consignments across carriers with customs paperwork.",
    "Scheduling portal for a hospital group where clinicians book patient appointments.",
    "Core banking ledger with ISO 20022 settlement and reconciliation.",
])
def test_a_vertical_requirement_routes_to_the_verticals_document(query):
    """The hospitality one is the reported case; the other three are different clusters, included
    so a fix that only helped hospitality would not pass."""
    hits = retrieve(query, top_k=3)
    assert hits, f"{query!r} returned nothing"
    assert hits[0]["doc"] == "20-industry-verticals.md", [h["doc"] for h in hits]


@requires_ollama
@pytest.mark.parametrize("query,expected", [
    ("real-time collaborative document editing with presence cursors",
     "01-realtime-collaborative-editing.md"),
    ("which sync transport for concurrent edits, websockets or webrtc",
     "01-realtime-collaborative-editing.md"),
    ("how do we stop SMS pumping and AIT fraud", "19-cpaas-communications.md"),
    ("which database for a multi-tenant SaaS with strict tenant isolation",
     "05-multi-tenant-saas.md"),
])
def test_other_documents_still_win_their_own_queries(query, expected):
    """Doc 20's Signals is the largest in the corpus. Broadening its routing surface could easily
    make it win everything; the two collaborative-editing queries are the specific risk, since
    'sync' is the word the hospitality query and doc 01 both reach for."""
    hits = retrieve(query, top_k=3)
    assert hits and hits[0]["doc"] == expected, [h["doc"] for h in hits] if hits else "no hits"


@requires_ollama
def test_the_signals_section_is_split_into_multiple_routing_surfaces():
    """The mechanism, asserted directly: if someone flattens this back into one list the queries
    above regress, and this says why before they have to re-derive it."""
    import pathlib
    from app.retrieval import KB_DIR
    text = (pathlib.Path(KB_DIR) / "20-industry-verticals.md").read_text(encoding="utf-8")
    subsections = [l for l in text.split("\n") if l.startswith("### Signals / triggers")]
    assert len(subsections) >= 5, f"only {len(subsections)} routing surfaces: {subsections}"
