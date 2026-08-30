"""Regression tests for two real gaps found in an external QA report's own reproduction steps
(verified directly against this codebase before any fix was written — see the conversation, not
just trusted from the report):

1. **Passive voice** ("Kubernetes must not be used") — the active-voice negation regexes
   (`no|not|without|...`) only look FORWARD from the negator word, so a subject placed BEFORE
   the negation phrase was never seen. "We must not use Kubernetes" worked (Kubernetes comes
   after "not"); "Kubernetes must not be used" did not.
2. **Comma-separated exclusion lists** ("I do not need a website, API, database, ..., or a
   vector database.") — the negated-clause capture stopped at the first comma, so only the
   first listed item was ever recorded as excluded; everything after the first comma was read
   as a positive mention instead.

Both are asserted against BOTH engines (rule_engine.py and index.html's JS twin — independent
implementations, see test_engine_parity.py) since the fix touches stripNegations()/
detectExclusions() in each file separately, by design (v1 must stay fully client-side).
"""
import shutil
from pathlib import Path

import pytest

from app.rule_engine import detect_exclusions, recommend_stack, strip_negations
from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

_STUBS = r"""
const dummyEl = { style:{}, classList:{add(){},remove(){},toggle(){}}, addEventListener(){},
  setAttribute(){}, getAttribute:()=>null, appendChild(){}, removeChild(){}, click(){}, focus(){},
  querySelector:()=>null, querySelectorAll:()=>[], innerHTML:'', textContent:'', value:'' };
global.window = { location:{search:''}, addEventListener(){}, matchMedia:()=>({matches:false,addEventListener(){}}) };
global.document = { documentElement:dummyEl, body:dummyEl, querySelector:()=>dummyEl,
  querySelectorAll:()=>[], getElementById:()=>dummyEl, createElement:()=>dummyEl, addEventListener(){} };
global.navigator = { clipboard:{} };
global.localStorage = { getItem:()=>null, setItem(){}, removeItem(){} };
global.fetch = () => Promise.resolve({ ok:false });
global.URL = { createObjectURL:()=>'', revokeObjectURL(){} };
"""


def _main_script() -> str:
    return INDEX_HTML.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]


def _js(expr_body: str):
    return run_node_json(_STUBS + _main_script() + "\n" + expr_body)


T1 = (
    "Build a small internal application for ten employees. Kubernetes must not be used "
    "because the team does not know how to operate it and we do not have a DevOps engineer."
)
T2 = (
    "I want to develop only a heart-disease prediction model in a Jupyter Notebook using a "
    "labelled CSV dataset. We will need data cleaning, exploratory data analysis, "
    "train-test splitting, cross-validation, Logistic Regression, Random Forest and SVM. "
    "We compare the models using precision, recall, F1-score, ROC-AUC and a confusion matrix. "
    "I do not need a website, API, database, cloud deployment, Docker, Kubernetes, "
    "microservices, RAG, an LLM or a vector database."
)


# --------------------------------------------------------------------- passive voice (Python)

def test_passive_voice_negation_is_detected_as_an_exclusion():
    assert detect_exclusions(T1).get("kubernetes") is True


def test_passive_voice_negation_is_stripped_so_it_is_not_also_a_positive_mention():
    assert "kubernetes" not in strip_negations(T1).lower()


def test_passive_voice_exclusion_flows_through_to_the_final_recommendation():
    containers = recommend_stack(T1)["recommendations"]["containers"]
    assert containers.get("excluded") is True
    assert "Kubernetes" not in containers["v"] or "not Kubernetes" in containers["v"]


# ------------------------------------------------------------------ comma lists (Python)

def test_comma_separated_exclusion_list_records_every_item_not_just_the_first():
    out = detect_exclusions(T2)
    for key in ("frontend", "api", "database", "cloud", "containers", "kubernetes",
                "microservices", "rag", "llm"):
        assert out.get(key) is True, f"{key!r} missing from {out}"


def test_comma_separated_exclusion_list_flows_through_to_final_recommendations():
    recs = recommend_stack(T2)["recommendations"]
    assert recs["containers"].get("excluded") is True
    assert recs["database"].get("excluded") is True
    assert recs["cloud"].get("excluded") is True
    assert recs["frontend"].get("excluded") is True
    assert recs["rag"].get("excluded") is True
    assert recs["llm"][0]["name"].startswith("Not recommended")


# ------------------------------------------------------------- the fix must stay conservative

def test_a_later_unrelated_positive_clause_after_but_is_not_swept_in():
    """The comma-list fix widens how far the negated clause can run — it must still stop at a
    contrasting conjunction, or "we don't need Redis, but we do need Postgres" would wrongly
    exclude the database the user just asked for."""
    out = detect_exclusions("We don't need Redis or Memcached, but we do need Postgres for durability.")
    assert out == {"cache": True}


def test_qualifying_negations_still_survive_the_wider_clause_window():
    """Existing NON_EXCLUSION_QUALIFIERS coverage (only/just/merely/more than...) must keep
    working now that the clause can run past the first comma."""
    assert detect_exclusions("We need not only a website but also a mobile app.") == {}
    assert detect_exclusions(
        "This is not just a database problem, we need real-time streaming."
    ) == {}


# --------------------------------------------------------------------------- JS parity

@requires_node
def test_js_passive_voice_negation_is_detected_as_an_exclusion():
    out = _js(f"console.log(JSON.stringify(detectExclusions({T1!r})));")
    assert out.get("kubernetes") is True


@requires_node
def test_js_comma_separated_exclusion_list_records_every_item():
    out = _js(f"console.log(JSON.stringify(detectExclusions({T2!r})));")
    for key in ("frontend", "api", "database", "cloud", "containers", "kubernetes",
                "microservices", "rag", "llm"):
        assert out.get(key) is True, f"{key!r} missing from {out}"


@requires_node
def test_js_later_unrelated_positive_clause_after_but_is_not_swept_in():
    text = "We don't need Redis or Memcached, but we do need Postgres for durability."
    out = _js(f"console.log(JSON.stringify(detectExclusions({text!r})));")
    assert out == {"cache": True}


@requires_node
def test_js_qualifying_negations_still_survive_the_wider_clause_window():
    text = "We need not only a website but also a mobile app."
    out = _js(f"console.log(JSON.stringify(detectExclusions({text!r})));")
    assert out == {}
