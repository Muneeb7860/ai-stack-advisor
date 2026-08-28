"""
The knowledge-base corpus directory and the corpus that actually gets indexed must be the same set.

Deliberately NOT Ollama-gated. Everything in test_retrieval_eval.py needs a live embedding daemon
and therefore skips in CI; these checks are pure filesystem and string work, and they guard the
failure mode that has the least visible symptom — so they need to run everywhere.

The failure they exist for: app/retrieval.py used to carry a hardcoded DOC_FILES list. Adding a
document to docs/use-case-knowledge-base/ indexed nothing and raised nothing — the file simply
could never be retrieved. Three documents were contributed and were invisible to every query until
someone thought to check. There was no error, no warning, and the retrieval eval passed the whole
time, because every existing case still routed correctly.
"""
import json
import re
from pathlib import Path

from app.retrieval import DOC_FILES, KB_DIR

CORPUS_DIR = Path(__file__).resolve().parents[2] / "docs" / "use-case-knowledge-base"
DOMAIN_DOC = re.compile(r"^(?!00-)\d{2}-.+\.md$")


def _domain_docs_on_disk() -> set[str]:
    return {p.name for p in CORPUS_DIR.iterdir() if DOMAIN_DOC.match(p.name)}


def test_every_domain_document_on_disk_is_indexed():
    """A document nobody indexed is a document nobody can retrieve, and nothing else fails."""
    on_disk, indexed = _domain_docs_on_disk(), set(DOC_FILES)
    assert on_disk == indexed, (
        f"corpus directory and indexed corpus disagree — "
        f"on disk but not indexed: {sorted(on_disk - indexed)}; "
        f"indexed but missing from disk: {sorted(indexed - on_disk)}"
    )


def test_corpus_is_discovered_not_enumerated():
    """Regression lock on the mechanism, not just this moment's result: a hardcoded list would pass
    the test above on the day it was written and rot silently afterwards."""
    source = (Path(KB_DIR).resolve().parents[1] / "backend" / "app" / "retrieval.py")
    if not source.exists():  # KB_DIR is relative to app/, resolve from the module instead
        import app.retrieval as r
        source = Path(r.__file__)
    text = source.read_text(encoding="utf-8")
    assert "_discover_doc_files" in text, "corpus must be discovered from the directory"
    assert not re.search(r"DOC_FILES\s*=\s*\[\s*\n\s*\"\d\d-", text), (
        "DOC_FILES is a literal list again — adding a corpus document will silently index nothing"
    )


def test_non_corpus_files_are_not_indexed():
    """The same directory holds the index/meta doc, the eval set, a prototype script and its JSON
    results. None of them is retrievable content, and a stray tooling file must not become corpus."""
    indexed = set(DOC_FILES)
    for excluded in ["00-INDEX-AND-INGESTION-GUIDE.md", "RETRIEVAL-EVAL-SET.md",
                     "RETRIEVAL-PROTOTYPE-FINDINGS.md", "eval_cases.json",
                     "retrieval_prototype.py", "retrieval_prototype_results.json"]:
        assert excluded not in indexed, f"{excluded} is tooling/meta, not retrievable content"


def test_every_indexed_document_has_a_signals_section():
    """Per 00-INDEX §2, Signals sections drive the first-stage routing pass. A document without one
    is reachable only by accidental content overlap — which is how an analytics question routed to
    the networking document rather than the layering one that actually answered it."""
    missing = [
        name for name in DOC_FILES
        if not re.search(r"^##\s+Signals?\s*/?\s*triggers?", (CORPUS_DIR / name).read_text(encoding="utf-8"), re.I | re.M)
    ]
    assert not missing, f"no Signals/triggers section (unroutable): {missing}"


def test_every_indexed_document_is_listed_in_the_index_guide():
    """00-INDEX's domain table is what a human reads to know what the corpus covers. A document
    absent from it is invisible to people even once it is visible to the retriever."""
    index_text = (CORPUS_DIR / "00-INDEX-AND-INGESTION-GUIDE.md").read_text(encoding="utf-8")
    missing = [name for name in DOC_FILES if f"`{name}`" not in index_text]
    assert not missing, f"indexed but undocumented in 00-INDEX's domain table: {missing}"


def test_eval_set_expectations_reference_documents_that_exist():
    """An eval case pointing at a renamed or deleted document passes vacuously or fails obscurely."""
    cases = json.loads((CORPUS_DIR.parent.parent / "backend" / "tests" / "eval_cases.json").read_text(encoding="utf-8"))["cases"]
    on_disk = _domain_docs_on_disk()
    dangling = sorted({doc for c in cases for doc in c.get("expected_docs", []) if doc not in on_disk})
    assert not dangling, f"eval cases expect documents that do not exist: {dangling}"


# --------------------------------------------------------------------------- corpus conventions
# A rule split across two documents is a rule /api/ask can answer half of. Measured: a query
# spanning documents 13 and 14 — the one pair joined by a prose cross-reference — returned only
# document 13, because routing scores Signals + preamble only and a pointer inside a content chunk
# has no routing weight at all. So a shared rule is stated verbatim in every document that touches
# it, and this asserts the copies have not drifted. Same trade as the two rule engines: duplication
# is fine when something fails the moment the copies diverge.
CANONICAL_RULES = {
    "one backend per signal class — never two backends for the same signal": [
        "14-request-path-layer-ordering.md",
        "15-observability-and-audit-logging.md",
    ],
}

VALID_STATUSES = ("implemented", "partial", "target design")


def test_canonical_rules_are_stated_verbatim_in_every_document_that_shares_them():
    for rule, docs in CANONICAL_RULES.items():
        for name in docs:
            text = (CORPUS_DIR / name).read_text(encoding="utf-8").lower()
            assert rule.lower() in text, (
                f"{name} is registered as sharing a canonical rule but does not state it verbatim: "
                f"{rule!r}. A cross-reference is not a substitute — routing cannot follow one."
            )


def test_canonical_rules_are_not_replaced_by_a_cross_reference():
    """The specific regression: doc 13 used to point at doc 14 §E instead of stating the rule, and
    a spanning query returned 13 alone. Pointers of that shape are the thing being prevented."""
    for name in {d for docs in CANONICAL_RULES.values() for d in docs}:
        text = (CORPUS_DIR / name).read_text(encoding="utf-8")
        assert not re.search(r"is covered in `\d\d-[a-z-]+\.md`", text), (
            f"{name} defers a rule to another document by prose reference — state it verbatim "
            "instead, or drop it entirely if the other document owns it"
        )


def test_every_document_declares_implemented_versus_target_design():
    """A corpus that cannot tell what the engine DOES from what its author thinks it SHOULD do will
    state aspirations as facts. /api/ask answering 'yes, the tool handles that' about target design
    is a worse failure than not answering — so the distinction is a parseable field, not prose."""
    bad = {}
    for name in DOC_FILES:
        m = re.search(r"^\*\*Status:\*\*\s*([a-z ]+?)\s*—", (CORPUS_DIR / name).read_text(encoding="utf-8"), re.M)
        if not m:
            bad[name] = "no **Status:** line under the title"
        elif m.group(1).strip() not in VALID_STATUSES:
            bad[name] = f"status {m.group(1).strip()!r} not in {VALID_STATUSES}"
    assert not bad, f"Status field problems: {bad}"


def test_target_design_documents_say_so_in_their_implementation_section():
    """The Status line and the 'As implemented' prose must agree — two places to state the same
    thing is two places to be wrong, so they are checked against each other."""
    for name in DOC_FILES:
        text = (CORPUS_DIR / name).read_text(encoding="utf-8")
        m = re.search(r"^\*\*Status:\*\*\s*([a-z ]+?)\s*—", text, re.M)
        if not m or m.group(1).strip() != "target design":
            continue
        section = text.split("## As implemented")[-1][:400].lower()
        assert "not yet implemented" in section or "nothing of this document is implemented" in section, (
            f"{name} declares Status 'target design' but its 'As implemented' section does not say so"
        )


# --------------------------------------------------------------- "Revisit triggers" (Step 3)
# Several documents stated, in free prose scattered across their decision points, the condition
# under which a recommendation should flip — e.g. doc 17: "reconsider if a single-vendor outage
# has caused a business-critical incident more than once." /api/ask and /api/refine could only
# ever paraphrase that condition out of a larger chunk, never quote it reliably. This is the same
# problem the **Status:** field solves for "is this implemented" — a fact stated once in prose is
# a fact an LLM will eventually paraphrase into something subtly wrong.
#
# Deliberately placed as a real "## " content section (not a **bolded:** line in the preamble,
# unlike Status) — app/retrieval.py's two-stage design treats preamble text as ROUTING-only,
# never returned as citable content (see that module's docstring). A "## Revisit triggers"
# section is a normal content chunk: it participates in the same embedding+BM25 hybrid ranking as
# every other decision point, with zero changes needed to retrieval.py itself.
REVISIT_TRIGGERS_HEADER = re.compile(r"^## Revisit triggers\s*$", re.M)


def test_every_domain_document_has_a_revisit_triggers_section():
    """Regression lock for Step 3 of the RAG-derivation-engine plan: every domain document must
    state its own revisit condition(s) as a dedicated, greppable section — not leave them
    scattered across decision-point prose for an LLM to paraphrase out."""
    missing = [name for name in DOC_FILES if not REVISIT_TRIGGERS_HEADER.search((CORPUS_DIR / name).read_text(encoding="utf-8"))]
    assert not missing, f"no '## Revisit triggers' section: {missing}"


def test_revisit_triggers_sections_have_at_least_one_bullet():
    """A header with no content under it is worse than no header — it would look formalized while
    conveying nothing. Every 'Revisit triggers' section must have at least one real `- ` bullet
    before the next '## ' header."""
    empty = []
    for name in DOC_FILES:
        text = (CORPUS_DIR / name).read_text(encoding="utf-8")
        m = REVISIT_TRIGGERS_HEADER.search(text)
        if not m:
            continue  # caught by the presence test above; don't double-report here
        section = text[m.end():]
        next_header = re.search(r"^## ", section, re.M)
        section = section[: next_header.start()] if next_header else section
        if not re.search(r"^- ", section, re.M):
            empty.append(name)
    assert not empty, f"'## Revisit triggers' section has no bullets: {empty}"

