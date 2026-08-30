"""New vendor category: GitOps continuous deployment (ArgoCD / Flux CD).

Unlike the prior four vendor-catalog pilots (Clerk/WorkOS in IAM, Axiom/Better Stack in
observability, Neon/Turso in database, Coolify/Dokploy in compute — all additions to an
EXISTING comparison card), this is a genuinely new category: neither engine had any GitOps CD
comparison at all before this. ArgoCD was previously only mentioned as inline prose in a
trade-off card, never as a real, comparable pick with alternatives.

Architectural note this test suite locks in: GitOps CD is a distinct job from the CI (build/
test) tools in CICD_VENDORS — ArgoCD/Flux reconcile a Git repo against a running Kubernetes
cluster, they don't build or test anything. It's also gated on Kubernetes-style orchestration
actually being in the stack: a serverless-containers or no-orchestrator outcome has nothing for
GitOps to reconcile against, so this category must say so rather than recommending a tool with
nothing to do.

Pricing/licensing facts (CNCF-graduated, free/OSS) verified live against argo-cd.readthedocs.io
and fluxcd.io before being written into either engine.

Asserted against BOTH engines (rule_engine.py and index.html's JS twin).
"""
import shutil
from pathlib import Path

import pytest

from app.rule_engine import GITOPS_VENDORS, detect_signals, recommend_stack
from app.routers.refine import VALID_CATEGORIES
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


K8S_TEXT = "A large enterprise platform running on Kubernetes with multiple teams."
NO_ORCHESTRATOR_TEXT = "This is a tiny personal learning project, just for me."
SERVERLESS_TEXT = "Early-stage MVP, small team, want the least ops overhead possible."


# ------------------------------------------------------------------------- explicit mentions

def test_argocd_mention_is_detected_and_recommended():
    s = detect_signals("We already use ArgoCD for deployments.")
    assert s["argocdMentioned"] is True
    rec = recommend_stack("We already use ArgoCD for deployments. " + K8S_TEXT)["recommendations"]
    assert rec["gitops"]["v"] == "ArgoCD"


def test_fluxcd_mention_is_detected_and_recommended():
    s = detect_signals("We already use FluxCD for GitOps.")
    assert s["fluxcdMentioned"] is True
    rec = recommend_stack("We already use FluxCD for GitOps. " + K8S_TEXT)["recommendations"]
    assert rec["gitops"]["v"] == "Flux CD"


def test_flux_cd_two_word_synonym_is_also_recognized():
    s = detect_signals("Our deployments run through Flux CD.")
    assert s["fluxcdMentioned"] is True


def test_bare_gitops_mention_without_a_specific_tool_defaults_to_argocd():
    rec = recommend_stack("We want a GitOps workflow. " + K8S_TEXT)["recommendations"]
    assert "ArgoCD" in rec["gitops"]["v"]


# --------------------------------------------------------------------- gating on orchestration

def test_no_orchestrator_stack_gets_not_applicable():
    rec = recommend_stack(NO_ORCHESTRATOR_TEXT)["recommendations"]
    assert rec["gitops"]["v"] == "Not applicable — no Kubernetes-style orchestrator in this stack"
    assert rec["gitops"]["primaryId"] is None


def test_serverless_containers_stack_also_gets_not_applicable():
    """Cloud Run/Fargate-style serverless containers have no Kubernetes manifests for a GitOps
    tool to reconcile — this must not be conflated with a real Kubernetes orchestrator."""
    rec = recommend_stack(SERVERLESS_TEXT)["recommendations"]
    assert "Not applicable" in rec["gitops"]["v"]


def test_kubernetes_stack_gets_a_real_recommendation():
    rec = recommend_stack(K8S_TEXT)["recommendations"]
    assert rec["gitops"]["v"] in ("ArgoCD", "ArgoCD (or Flux CD if you want a lighter-weight, UI-less toolkit)")
    assert rec["gitops"]["primaryId"] == "argocd"


# -------------------------------------------------------------------------- exclusion handling

def test_excluding_kubernetes_replaces_the_primary_gitops_text_too():
    """Regression lock for the bug found while wiring this: pick_gitops_vendor() computes its
    recommendation from the PRE-exclusion containers pick, so merely _suppress()-ing the vendor
    comparison (which only hides the alt-toggle) would leave the PRIMARY card text still
    recommending ArgoCD to manage a Kubernetes cluster the user just excluded."""
    text = "We must not use Kubernetes at all for this project. " + K8S_TEXT
    rec = recommend_stack(text)["recommendations"]
    assert "excluded containers/Kubernetes" in rec["gitops"]["v"]
    assert rec["gitops_vendor"].get("suppressed") is True
    assert rec["gitops_vendor"].get("primaryId") is None


def test_excluding_containers_also_replaces_gitops():
    text = "We don't want Docker or containers at all. " + K8S_TEXT
    rec = recommend_stack(text)["recommendations"]
    assert "excluded containers/Kubernetes" in rec["gitops"]["v"]


# ------------------------------------------------------------------------- vendor catalog data

def test_argocd_and_fluxcd_are_in_the_gitops_vendor_catalog_with_real_facts():
    ids = {v["id"] for v in GITOPS_VENDORS}
    assert ids == {"argocd", "fluxcd"}

    argocd = next(v for v in GITOPS_VENDORS if v["id"] == "argocd")
    fluxcd = next(v for v in GITOPS_VENDORS if v["id"] == "fluxcd")

    assert "CNCF-graduated" in argocd["pricing"]
    assert "CNCF-graduated" in fluxcd["pricing"]
    # The one real architectural difference worth surfacing: ArgoCD ships a UI, Flux doesn't.
    assert "web UI" in argocd["strength"]
    assert "No built-in web UI" in fluxcd["drawback"]


# -------------------------------------------------------------------- refine/ask/challenge wiring

def test_gitops_category_is_reachable_from_refine():
    """Regression lock for the exact defect test_kb_promoted_categories.py documents for other
    cards: a category missing from VALID_CATEGORIES/STACK_CARD_CATEGORY renders its refine
    button but can never show a real suggestion."""
    assert "gitops" in VALID_CATEGORIES


# ------------------------------------------------------------------------------------ JS parity

@requires_node
def test_js_and_python_gitops_pick_functions_exist_and_are_named_consistently():
    """test_engine_parity.py already enforces this generically — this test additionally checks
    the specific expected function/const names land where this test suite assumes they do."""
    out = _js("console.log(JSON.stringify(typeof pickGitopsVendor));")
    assert out == "function"


@requires_node
@pytest.mark.parametrize("text,expected_v", [
    (K8S_TEXT, None),  # None => just check it's a real ArgoCD-family pick, not exact string
    (NO_ORCHESTRATOR_TEXT, "Not applicable — no Kubernetes-style orchestrator in this stack"),
])
def test_js_gitops_matches_python(text, expected_v):
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({text!r}));
      console.log(JSON.stringify({{ v: rec.gitops.v, primaryId: rec.gitops.primaryId }}));
    """)
    if expected_v:
        assert out["v"] == expected_v
    else:
        assert out["primaryId"] == "argocd"


@requires_node
def test_js_excluding_kubernetes_replaces_the_primary_gitops_text_too():
    text = "We must not use Kubernetes at all for this project. " + K8S_TEXT
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({text!r}));
      console.log(JSON.stringify({{ v: rec.gitops.v, suppressed: rec.gitopsVendorPick.suppressed }}));
    """)
    assert "excluded containers/Kubernetes" in out["v"]
    assert out["suppressed"] is True


@requires_node
def test_js_and_python_gitops_vendor_ids_match():
    py_ids = sorted(v["id"] for v in GITOPS_VENDORS)
    js_ids = sorted(_js("console.log(JSON.stringify(GITOPS_VENDORS.map(v => v.id)));"))
    assert py_ids == js_ids


@requires_node
def test_js_stack_card_category_includes_gitops():
    out = _js("console.log(JSON.stringify(STACK_CARD_CATEGORY['GitOps / Continuous Deployment']));")
    assert out == "gitops"
