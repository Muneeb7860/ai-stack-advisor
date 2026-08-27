"""
Report-vs-export fidelity.

The on-screen recommendation and the downloadable ADR pack are produced by different code
paths, and they had drifted far enough apart that the export actively contradicted the report
(it recorded "use Kafka" for a requirement the site answered with RabbitMQ) and silently dropped
recommendations it had no knowledge-base entry for.

These tests pin the five structural fixes. They run the real index.html under Node, because
every one of these paths (buildAdrInput, renderC4, mapAppPicksToKb, the arc42 renderer) exists
only in the frontend — the Python engine has no export layer.
"""
import json
import re
import shutil
from pathlib import Path

import pytest

from app.rule_engine import detect_concurrency_target, detect_signals, detect_timeline
from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

# A requirement that states every fact the export was losing: cloud, IdP, language, database,
# compliance regime, concurrency, team size and delivery window.
REQ = (
    "Internal enterprise knowledge assistant with RAG over our Confluence and SharePoint policy "
    "documents. We use Azure and Entra ID, Python, and PostgreSQL. Answers must cite sources. "
    "500 concurrent users. Team of 6 engineers, 4 month timeline. SOC2 compliance required."
)

_STUBS = r"""
const fs = require('fs');
const src = fs.readFileSync(INDEX_PATH, 'utf8');
const dummyEl = { style:{}, classList:{add(){},remove(){},toggle(){}}, addEventListener(){},
  setAttribute(){}, getAttribute:()=>null, appendChild(){}, removeChild(){}, click(){}, focus(){},
  querySelector:()=>null, querySelectorAll:()=>[], innerHTML:'', textContent:'', value:'' };
const kbMatch = src.match(/id="stackKbData"[^>]*>([\s\S]*?)<\/script>/);
const kbNode = Object.assign({}, dummyEl, { textContent: kbMatch ? kbMatch[1] : '{}' });
global.window = { location:{search:''}, addEventListener(){}, matchMedia:()=>({matches:false,addEventListener(){}}) };
global.document = { documentElement:dummyEl, body:dummyEl, querySelector:()=>dummyEl,
  querySelectorAll:()=>[], createElement:()=>dummyEl, addEventListener(){},
  getElementById:(id)=> id === 'stackKbData' ? kbNode : dummyEl };
global.navigator = { clipboard:{} };
global.localStorage = { getItem:()=>null, setItem(){}, removeItem(){} };
global.fetch = () => Promise.resolve({ ok:false });
global.URL = { createObjectURL:()=>'', revokeObjectURL(){} };
for (const b of src.split('<script>').slice(1).map(b => b.split('</script>')[0])) {
  try { (0, eval)(b); } catch (e) {}
}
"""


def _js(body: str):
    harness = f"const INDEX_PATH = {str(INDEX_HTML)!r};\n" + _STUBS + "\n" + body
    return run_node_json(harness)


def _bundle():
    return _js(
        f"const REQ = {REQ!r};\n"
        """
        const s = detectSignals(REQ);
        const rec = computeRecommendations(s);
        const mapped = mapAppPicksToKb(rec, s);
        const input = buildAdrInput(s);
        const out = window.AdrExport.buildExports({kb: getKbData(), input, recommendations: mapped.recommendations, omitted: mapped.omitted});
        console.log(JSON.stringify({
          input,
          decisions: mapped.recommendations.map(r => ({role: r.role, techId: r.techId, basis: r.basis})),
          omitted: mapped.omitted.map(o => ({category: o.category, detail: o.detail})),
          bundle: out.bundle,
        }));
        """
    )


# ---------------------------------------------------------------- FIX 1: input provenance
@requires_node
def test_adr_input_is_derived_from_the_requirement_not_just_wizard_state():
    """buildAdrInput() read wizState.* — populated ONLY by the guided wizard — plus a single
    field from the analysis. Analysing pasted text left it empty, so the pack was built from a
    blank input: no compliance regime, no existing stack, no team size, generic product name,
    even though the requirement stated all of them."""
    inp = _bundle()["input"]
    assert "soc2" in inp["compliance"], "SOC2 was stated in the requirement"
    stack = [x.lower() for x in inp["existingStack"]]
    for named in ["python", "postgresql", "azure", "microsoft entra id"]:
        assert named in stack, f"{named} was named in the requirement but missing from existingStack"
    assert inp["teamSize"], "team size was stated"
    assert inp["productName"] != "Recommended stack (AI Stack Advisor)", "generic fallback name"
    assert inp["concurrencyTarget"]["count"] == 500
    assert inp["timeline"]["days"] == 120


# ---------------------------------------------------------------- FIX 2: C4 correctness
def test_every_kb_category_has_an_explicit_c4_classification():
    """C4_LAYER covered 14 of 60 KB categories and everything else fell through to `|| 'app'`.
    Since every app container is wired Reads/writes to every data container, that fallback is
    what produced Rel(azure, postgres) and Rel(terraform, kafka).

    Static rather than runtime: C4_LAYER is a top-level `const`, and a `const` evaluated through
    indirect eval lands in that eval's lexical scope, not on globalThis — only the function
    declarations in the same block become reachable. Reading the source is also the stricter
    check, since it fails when the KB gains a category regardless of whether any fixture uses it.
    """
    html = INDEX_HTML.read_text(encoding="utf-8")

    layer_block = re.search(r"const C4_LAYER = \{.*?\n\};", html, re.S)
    assert layer_block, "C4_LAYER not found"
    classified = set(re.findall(r"'([a-z0-9-]+)':", layer_block.group(0)))

    not_container = re.search(r"const C4_NOT_A_CONTAINER = new Set\(\[.*?\]\);", html, re.S)
    assert not_container, "C4_NOT_A_CONTAINER not found"
    classified |= set(re.findall(r"'([a-z0-9-]+)'", not_container.group(0)))

    kb = json.loads(re.search(r'id="stackKbData"[^>]*>(.*?)</script>', html, re.S).group(1))
    categories = {t["category"] for t in kb["technologies"]}

    unclassified = sorted(categories - classified)
    assert not unclassified, (
        f"categories with no C4 classification fall through to the 'app' layer and gain bogus "
        f"datastore relationships: {unclassified}"
    )


@requires_node
def test_only_application_containers_read_or_write_datastores():
    """The reported symptom: a cloud provider, an IaC tool and an LLM were all drawn reading and
    writing Postgres and Kafka. 24 of 36 relationships were invalid."""
    bundle = _bundle()["bundle"]
    diagram = bundle[bundle.index("C4Container"):]
    diagram = diagram[:diagram.index("```")]

    db_ids = set(re.findall(r"ContainerDb\((\w+),", diagram))
    assert db_ids, "expected at least one datastore in the diagram"

    writers = {m.group(1) for m in re.finditer(r'Rel\((\w+),\s*(\w+),\s*"Reads/writes"\)', diagram)}
    # Only backend application containers may read/write state. Anything infrastructural
    # (cloud, CI, IaC, orchestration, identity, observability, models) must not.
    forbidden = {"azure", "aws", "gcp", "terraform", "github_actions", "kubernetes", "istio",
                 "entra_id", "okta", "otel", "claude_sonnet", "cloud_api_anthropic",
                 "ollama_self_hosted", "redis"}
    assert not (writers & forbidden), (
        f"these are not application containers and must not read/write datastores: "
        f"{sorted(writers & forbidden)}"
    )


@requires_node
def test_build_time_tooling_is_not_drawn_as_a_runtime_container():
    """Terraform, CI and the cloud provider are not things that run and talk to other things at
    request time — they render as notes."""
    bundle = _bundle()["bundle"]
    diagram = bundle[bundle.index("C4Container"):bundle.index("```", bundle.index("C4Container"))]
    boxes = re.findall(r"Container(?:Db)?\((\w+),", diagram)
    for not_a_container in ["terraform", "github_actions", "azure"]:
        assert not_a_container not in boxes, f"{not_a_container} drawn as a container"
    assert "a property of the system, not a container" in diagram


# ---------------------------------------------------------------- FIX 3: shared provenance
@requires_node
def test_export_does_not_mark_inferred_picks_as_user_stated():
    """The exporter carried its OWN explicit-map, so fixing the on-screen cards left it still
    reporting team size as an architecture request and traffic volume as a Kafka request."""
    decisions = {d["role"]: d["basis"] for d in _bundle()["decisions"]}
    for role in ["Architecture Style", "Containers / Orchestration"]:
        if role in decisions:
            assert decisions[role] != "stated", f"{role} was never named by the user"
    # The four things the requirement DID name must still read as stated.
    for role in ["Primary Database", "Identity & Access", "Cloud Provider"]:
        assert decisions.get(role) == "stated", f"{role} was explicitly named and must stay 'stated'"


# ---------------------------------------------------------------- FIX 4: pick-head matching
@requires_node
def test_pick_head_parsing_ignores_rationale_prose():
    out = _js("""
      console.log(JSON.stringify({
        rabbit: parsePickHeads("RabbitMQ (task queue / flexible routing) for now — move to Kafka if you need durable replay"),
        multi: parsePickHeads("PostgreSQL (primary transactional store) · MongoDB (flexible schema for content)"),
      }));
    """)
    assert out["rabbit"] == ["RabbitMQ"], "the contra-indication clause must not count as a pick"
    assert out["multi"] == ["PostgreSQL", "MongoDB"], "every store in a multi-pick must be seen"


@requires_node
def test_export_never_records_a_technology_the_report_did_not_recommend():
    """The site recommended RabbitMQ; the ADR recorded "0004. Messaging / Streaming: use Kafka",
    because 'Kafka' appears in RabbitMQ's own contra-indication clause."""
    data = _bundle()
    messaging = [d for d in data["decisions"] if "Messaging" in d["role"]]
    assert not any(d["techId"] == "kafka" for d in messaging), (
        "Kafka recorded as a decision for a requirement the report answered with RabbitMQ"
    )
    assert any("Messaging" in o["category"] for o in data["omitted"]), (
        "an unmappable messaging pick must be declared as omitted, not dropped"
    )
    assert "use Kafka" not in data["bundle"]


@requires_node
def test_multi_store_picks_declare_every_store_they_drop():
    """`if PostgreSQL -> map; else -> omit` meant "PostgreSQL · MongoDB" mapped Postgres and let
    MongoDB vanish — the else branch never ran, so there was no omission note either."""
    data = _bundle()
    db_omissions = [o for o in data["omitted"] if "Database(s)" in o["category"]]
    assert db_omissions, "MongoDB was recommended on screen and must be declared in the export"
    assert any("MongoDB" in o["detail"] for o in db_omissions)


# ---------------------------------------------------------------- FIX 5: stated numbers
@requires_node
def test_quality_scenarios_use_stated_numbers_instead_of_tbd():
    """The exported quality table asked the reader to supply figures they had already stated."""
    bundle = _bundle()["bundle"]
    section = bundle[bundle.index("### 10.2 Quality scenarios"):]
    section = section[:section.index("\n---")]
    assert "500 concurrent" in section
    assert "120 days" in section
    assert "SOC2" in section
    # Genuinely unknown attributes must still be marked TBD rather than invented.
    assert "_TBD_" in section, "attributes with no stated measure must stay explicitly TBD"


@pytest.mark.parametrize("text,count", [
    ("500 concurrent users", 500),
    ("10k concurrent sessions", 10000),
    ("supports 2,500 simultaneous connections", 2500),
])
def test_concurrency_targets_parse(text, count):
    assert detect_concurrency_target(text)["count"] == count


@pytest.mark.parametrize("text,days", [
    ("4 month timeline", 120),
    ("12 week delivery", 84),
    ("ship in two quarters", 182),
])
def test_timeline_targets_parse(text, days):
    assert detect_timeline(text)["days"] == days


def test_no_targets_means_no_invented_ones():
    s = detect_signals("A plain internal CRUD app.")
    assert s["concurrencyTarget"] is None
    assert s["timeline"] is None
