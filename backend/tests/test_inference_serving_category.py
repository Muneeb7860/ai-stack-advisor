"""New vendor category: Inference Serving Engine (vLLM / SGLang).

Third genuinely-new category this session, after GitOps CD (PR #44) and Agent Framework
(PR #45). Explicit user choice of "vLLM (+ TGI)" from a shortlist — but TGI (Hugging Face's
Text Generation Inference) turned out to be a stale suggestion once checked: HF's own docs
(huggingface.co/docs/text-generation-inference) state the project is now in maintenance mode
and explicitly recommend migrating to vLLM or SGLang. SGLang was substituted as the second
vendor instead of silently building a comparison against a project its own maintainer is
deprecating. tgiMentioned is still detected — a user naming it gets steered toward vLLM/SGLang
with an explanation, rather than either recommending a dead-end tool or staying silent.

Architectural note: this is NOT a restatement of the existing Runtime card (pick_runtime, which
already recommends Ollama for self-hosting). Ollama (llama.cpp-based) fits dev-machine
prototyping and light self-hosting; vLLM/SGLang's continuous-batching architecture is a
genuinely different tier, for production serving at real request volume. The category is gated
on BOTH self-hosting being relevant AND production scale, not just self-hosting alone — a
sensitive-data small team still gets routed to plain Ollama, matching pick_runtime's own
reasoning for that case.

Rendered as an additional sub-block inside the existing 'Hosting' section (right after the
Runtime sub-block), not a new top-level section — mirrors how Compute Tier and Runtime already
share that one section.

Asserted against BOTH engines (rule_engine.py and index.html's JS twin).
"""
import shutil
from pathlib import Path

import pytest

from app.rule_engine import INFERENCE_SERVING_VENDORS, detect_signals, recommend_stack
from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)


def _main_script() -> str:
    return INDEX_HTML.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]


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


def _js(expr_body: str):
    return run_node_json(_STUBS + _main_script() + "\n" + expr_body)


PRODUCTION_SELF_HOST_TEXT = "A large enterprise platform, self-hosted on our own GPUs and infrastructure, high traffic."
SMALL_SENSITIVE_TEXT = "A small team, compliance-sensitive healthcare data, low volume."
NO_SELF_HOST_TEXT = "A simple marketing website, using the OpenAI API for a small chat feature."


# ------------------------------------------------------------------------- explicit mentions

def test_vllm_mention_is_detected_and_recommended():
    s = detect_signals("We already use vLLM. " + PRODUCTION_SELF_HOST_TEXT)
    assert s["vllmMentioned"] is True
    rec = recommend_stack("We already use vLLM. " + PRODUCTION_SELF_HOST_TEXT)["recommendations"]
    assert rec["inference_serving_vendor"]["v"] == "vLLM"


def test_sglang_mention_is_detected_and_recommended():
    s = detect_signals("We already use SGLang. " + PRODUCTION_SELF_HOST_TEXT)
    assert s["sglangMentioned"] is True
    rec = recommend_stack("We already use SGLang. " + PRODUCTION_SELF_HOST_TEXT)["recommendations"]
    assert rec["inference_serving_vendor"]["v"] == "SGLang"


# --------------------------------------------------------------------------- the TGI correction

def test_tgi_mention_is_detected_but_steered_to_vllm_with_an_explanation():
    """The core finding from scoping this category: TGI is in maintenance mode per Hugging
    Face's own docs. A user naming it must be told why, not silently redirected or recommended
    a deprecated tool."""
    s = detect_signals("We were planning to use Text Generation Inference. " + PRODUCTION_SELF_HOST_TEXT)
    assert s["tgiMentioned"] is True
    rec = recommend_stack("We were planning to use Text Generation Inference. " + PRODUCTION_SELF_HOST_TEXT)["recommendations"]
    v = rec["inference_serving_vendor"]["v"]
    why = rec["inference_serving_vendor"]["why"]
    assert "vLLM" in v
    assert "not Text Generation Inference" in v
    assert "maintenance mode" in why


def test_bare_tgi_substring_does_not_false_positive():
    """"tgi" alone is deliberately excluded from the trigger phrase (too short/common a
    substring) — only "text generation inference" should ever set tgiMentioned."""
    assert detect_signals("We are budgeting for next quarter.")["tgiMentioned"] is False


# --------------------------------------------------------------------- gating: self-host + scale

def test_small_sensitive_team_stays_on_ollama_not_vllm():
    """Self-hosting is relevant here (sensitive data), but NOT at production scale — pick_runtime
    already correctly routes this to Ollama, and this category must not second-guess that by
    recommending heavier production infrastructure for a small team."""
    rec = recommend_stack(SMALL_SENSITIVE_TEXT)["recommendations"]
    assert "Not applicable" in rec["inference_serving_vendor"]["v"]
    assert rec["inference_serving_vendor"]["primaryId"] is None


def test_no_self_hosting_at_all_gets_not_applicable():
    rec = recommend_stack(NO_SELF_HOST_TEXT)["recommendations"]
    assert "Not applicable" in rec["inference_serving_vendor"]["v"]


def test_production_scale_self_hosting_gets_a_real_recommendation():
    rec = recommend_stack(PRODUCTION_SELF_HOST_TEXT)["recommendations"]
    assert "vLLM" in rec["inference_serving_vendor"]["v"]
    assert rec["inference_serving_vendor"]["primaryId"] == "vllm"


# ------------------------------------------------------------------------- vendor catalog data

def test_vllm_and_sglang_are_in_the_catalog_with_real_facts():
    ids = {v["id"] for v in INFERENCE_SERVING_VENDORS}
    assert ids == {"vllm", "sglang"}
    # TGI must never appear as a catalog entry — it's detected as a signal (to redirect away
    # from it), never offered as a selectable comparison option.
    assert "tgi" not in ids

    vllm = next(v for v in INFERENCE_SERVING_VENDORS if v["id"] == "vllm")
    sglang = next(v for v in INFERENCE_SERVING_VENDORS if v["id"] == "sglang")
    assert "PagedAttention" in vllm["strength"]
    assert "RadixAttention" in sglang["strength"]


def test_inference_serving_vendor_catalog_has_no_duplicate_ids():
    ids = [v["id"] for v in INFERENCE_SERVING_VENDORS]
    assert len(ids) == len(set(ids))


# ------------------------------------------------------------------------------------ JS parity

@requires_node
def test_js_vllm_mention_is_detected_and_recommended():
    text = "We already use vLLM. " + PRODUCTION_SELF_HOST_TEXT
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({text!r}));
      console.log(JSON.stringify({{ v: rec.inferenceServingVendorPick.v }}));
    """)
    assert out["v"] == "vLLM"


@requires_node
def test_js_tgi_mention_is_steered_to_vllm():
    text = "We were planning to use Text Generation Inference. " + PRODUCTION_SELF_HOST_TEXT
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({text!r}));
      console.log(JSON.stringify({{ v: rec.inferenceServingVendorPick.v, why: rec.inferenceServingVendorPick.why }}));
    """)
    assert "vLLM" in out["v"]
    assert "maintenance mode" in out["why"]


@requires_node
def test_js_small_sensitive_team_stays_not_applicable():
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({SMALL_SENSITIVE_TEXT!r}));
      console.log(JSON.stringify({{ v: rec.inferenceServingVendorPick.v }}));
    """)
    assert "Not applicable" in out["v"]


@requires_node
def test_js_and_python_inference_serving_vendor_ids_match():
    py_ids = sorted(v["id"] for v in INFERENCE_SERVING_VENDORS)
    js_ids = sorted(_js("console.log(JSON.stringify(INFERENCE_SERVING_VENDORS.map(v => v.id)));"))
    assert py_ids == js_ids
