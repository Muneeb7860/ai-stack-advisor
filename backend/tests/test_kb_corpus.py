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
