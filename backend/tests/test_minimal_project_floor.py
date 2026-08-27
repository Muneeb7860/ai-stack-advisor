"""
The over-suggestion regression this file exists for: "A college project — a simple to-do list app
for my final year submission" detected ZERO signals and fell through every pickX() branch to its
enterprise-ish default — AWS, Kubernetes, microservices, Okta, Datadog, RabbitMQ, Terraform+K8s
CI/CD. Every pickX() function checked for on-prem, startup, Huawei, enterprise, and if none fired,
defaulted to the heaviest answer rather than the lightest one. Confirmed directly against the
running engine before any fix, reproduced here as the regression lock.

minimalProject is deliberately distinct from startupMvp: a startup still intends to acquire real
users and may need to scale. A learning/personal project explicitly does not, and the honest floor
is "the simplest thing that runs" — never suggesting a cloud vendor, an orchestrator, or a paid IAM
platform for a college assignment is the same discipline as never suggesting Kubernetes for
"12345" (BUG-4) or Redis with no caching need (BUG-12), applied to the eight categories that
previously had no floor at all.

Every floor is guarded so a genuine scale, compliance, or explicit-vendor signal still wins — the
floor is for the common case, not an override of a real constraint.
"""
import pytest

from app.rule_engine import detect_signals, recommend_stack

COLLEGE_TODO = "A college project — a simple to-do list app for my final year submission."


@pytest.mark.parametrize("text", [
    COLLEGE_TODO,
    "A university project for my database systems class.",
    "A personal project to learn web development.",
    "My final year capstone — a weather app.",
    "A hobby project, just for learning, a note-taking app.",
])
def test_minimal_project_signal_is_detected(text):
    assert detect_signals(text)["minimalProject"] is True


def test_minimal_project_is_not_confused_with_startup():
    """Distinct signals — a startup intends to scale; a learning project does not."""
    s = detect_signals(COLLEGE_TODO)
    assert s["minimalProject"] is True
    assert s["startupMvp"] is False


# --------------------------------------------------------------------------- the regression itself
def test_the_reported_example_gets_the_minimal_stack_not_the_enterprise_one():
    recs = recommend_stack(COLLEGE_TODO)["recommendations"]

    assert "cloud provider needed" not in recs["cloud"]["v"].lower() or "no cloud" in recs["cloud"]["v"].lower()
    assert "AWS" not in recs["cloud"]["v"] and "Azure" not in recs["cloud"]["v"] and "GCP" not in recs["cloud"]["v"]
    assert "Kubernetes" not in recs["containers"]["v"]
    assert "Okta" not in recs["iam"]["v"] and "Ping Identity" not in recs["iam"]["v"]
    assert "Datadog" not in recs["observability"]["v"] and "Splunk" not in recs["observability"]["v"]
    assert "RabbitMQ" not in recs["messaging"]["v"] and "Kafka" not in recs["messaging"]["v"]
    assert "auto-deploy" in recs["cicd"]["v"]
    assert "SQLite" in recs["database"]["v"]
    assert recs["architecture"]["v"] == "A single simple app — no architecture pattern needed yet"


@pytest.mark.parametrize("category,expected_fragment", [
    ("cloud", "free-tier PaaS"),
    ("containers", "No orchestrator needed"),
    ("architecture", "no architecture pattern"),
    ("iam", "built-in auth"),
    ("observability", "no observability vendor"),
    ("messaging", "No message broker needed"),
    ("cicd", "auto-deploy"),
    ("database", "SQLite"),
])
def test_every_floor_fires_on_the_minimal_case(category, expected_fragment):
    recs = recommend_stack(COLLEGE_TODO)["recommendations"]
    assert expected_fragment in recs[category]["v"]


# --------------------------------------------------------------------------- guards: real signals win
def test_high_scale_overrides_the_cloud_and_containers_floor_even_in_a_minimal_project():
    """A stated scale need is real regardless of the project's context — the floor must not
    suppress it."""
    text = "A college project that needs to handle high traffic, millions of users, for my thesis on distributed systems."
    s = detect_signals(text)
    assert s["minimalProject"] is True and s["highScale"] is True
    recs = recommend_stack(text)["recommendations"]
    assert "AWS" in recs["cloud"]["v"] or "Azure" in recs["cloud"]["v"] or "GCP" in recs["cloud"]["v"]
    assert "Kubernetes" in recs["containers"]["v"]


def test_compliance_overrides_the_cloud_floor_but_not_containers():
    """Compliance affects data-handling and identity, not infrastructure SCALE — a compliance
    signal should block the cloud floor (regulated data on a random free PaaS is a real question)
    but has no reason to force an orchestrator onto a single-instance app."""
    text = "A college project for a healthcare data class assignment, HIPAA patient records."
    s = detect_signals(text)
    assert s["minimalProject"] is True and s["healthcare"] is True
    recs = recommend_stack(text)["recommendations"]
    assert "No cloud provider needed" not in recs["cloud"]["v"]
    assert "No orchestrator needed" in recs["containers"]["v"]


def test_explicit_vendor_mention_wins_over_the_floor():
    """An explicit ask ("I want to use AWS to learn it") is a real signal, not the thing the floor
    exists to suppress — checked before minimalProject in every affected branch."""
    text = "A college project — I want to use AWS specifically to learn cloud deployment."
    s = detect_signals(text)
    assert s["minimalProject"] is True and s["awsShop"] is True
    recs = recommend_stack(text)["recommendations"]
    assert recs["cloud"]["v"] == "AWS"


def test_unrelated_requirements_are_unaffected():
    """The floor must not leak into cases that never mention a minimal/learning project."""
    for text in [
        "A fintech payments platform, high traffic, PCI compliance, real-time fraud detection.",
        "An internal tool for our 5-person team to track expenses.",
    ]:
        assert detect_signals(text)["minimalProject"] is False
        recs = recommend_stack(text)["recommendations"]
        assert "No cloud provider needed" not in recs["cloud"]["v"]
        assert "No orchestrator needed" not in recs["containers"]["v"]


# --------------------------------------------------------------------------- JS engine parity
import json
import shutil
from pathlib import Path

from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

_STUBS = r"""
const dummyEl = { style:{}, classList:{add(){},remove(){},toggle(){}}, addEventListener(){},
  setAttribute(){}, getAttribute:()=>null, querySelector:()=>null, querySelectorAll:()=>[] };
global.window = { location:{search:''}, addEventListener(){} };
global.document = { documentElement:dummyEl, querySelectorAll:()=>[], getElementById:()=>dummyEl, addEventListener(){} };
global.navigator = { clipboard:{} };
global.localStorage = { getItem:()=>null, setItem(){}, removeItem(){} };
global.fetch = () => Promise.resolve({ ok:false });
"""


@requires_node
def test_js_engine_produces_the_same_floor():
    """The browser and backend are independent implementations (see test_engine_differential.py) —
    this is the specific case that motivated the fix, checked against the real index.html."""
    main_js = INDEX_HTML.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]
    out = run_node_json(
        _STUBS + main_js + f"""
        const s = detectSignals({json.dumps(COLLEGE_TODO)});
        const r = computeRecommendations(s);
        console.log(JSON.stringify({{cloud: r.cloud.v, containers: r.containers.v, db: r.db.v}}));
        """
    )
    assert "free-tier PaaS" in out["cloud"]
    assert "No orchestrator needed" in out["containers"]
    assert "SQLite" in out["db"]
