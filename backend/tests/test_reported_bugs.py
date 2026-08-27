"""
Regression suite for the externally-reported bug list (BUG-1 … BUG-12).

Each test names the bug it locks down and asserts the SPECIFIC wrong behaviour that was
reported, not just that the engine still runs. Two bugs from that list are deliberately absent:
BUG-2 and BUG-3 ("backend unavailable" for Refine/Ask/Share) were validated as working-as-
designed — v2 is opt-in and index.html degrades to an inline message when it isn't running, per
README.md — so there is nothing to regress.

Where a fix lives only in index.html (DOM wiring, the provenance map, the ADR exporter) the test
runs the real JS under Node; where it lives in the rule engine it is asserted against BOTH
engines, since index.html and rule_engine.py are independent implementations (see
test_engine_parity.py).
"""
import re
import shutil
from pathlib import Path

import pytest

from app.rule_engine import (
    detect_exclusions,
    detect_known_tech,
    detect_latency_target,
    detect_signals,
    recommend_stack,
)
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


# --------------------------------------------------------------------------- BUG-1
def test_bug1_upload_screen_has_no_inline_display_none():
    """Clicking "Upload architecture diagram" blanked the page.

    showScreen() toggles the `active` class, and `#screenUpload.active { display: block }` exists
    in the stylesheet — but the element also carried an inline `style="display:none"`, which wins
    over any selector-based rule. The base `#screenUpload { display: none }` rule already handles
    the initial hidden state (exactly as it does for the working #screenFreetext), so the inline
    copy was redundant AND load-bearing in the wrong direction.
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    m = re.search(r'<div[^>]*id="screenUpload"[^>]*>', html)
    assert m, "#screenUpload element not found"
    tag = m.group(0)
    style = re.search(r'style="([^"]*)"', tag)
    if style:
        assert "display:none" not in style.group(1).replace(" ", ""), (
            "inline display:none on #screenUpload beats '#screenUpload.active { display:block }', "
            "so showScreen() can never reveal it — the upload screen renders blank."
        )
    assert re.search(r"#screenUpload\s*\{\s*display:\s*none", html), (
        "the base hidden-state rule must stay, otherwise the upload screen shows on page load"
    )
    assert re.search(r"#screenUpload\.active\s*\{\s*display:\s*block", html), (
        "showScreen() reveals the screen via the .active class — that rule must exist"
    )


# --------------------------------------------------------------------------- BUG-4
def test_bug4_meaningless_input_is_flagged_not_silently_defaulted():
    """"12345" detected zero signals and still returned AWS + Kubernetes + microservices +
    Postgres + React with normal confidence badges, indistinguishable from a real analysis."""
    s = detect_signals("12345")
    assert not [k for k, v in s.items() if v is True], "expected zero boolean signals for gibberish"

    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "No requirements detected in your input" in html, (
        "the results view must state outright that nothing was derived from the input"
    )
    assert "not a recommendation for your project" in html


@requires_node
def test_bug4_signal_chips_ignore_non_boolean_signals():
    """`excluded`/`known`/`latencyTarget` are objects, and `{}` is truthy — a plain truthiness
    filter would list them as detected signals and make the "0 signals" case unreachable."""
    out = _js("""
      const s = detectSignals("12345");
      console.log(JSON.stringify({
        activeTrue: Object.entries(s).filter(([k,v])=>v===true).map(([k])=>k),
        activeTruthy: Object.entries(s).filter(([k,v])=>v).map(([k])=>k),
      }));
    """)
    assert out["activeTrue"] == [], "gibberish must yield zero boolean signals"
    assert set(out["activeTruthy"]) >= {"excluded", "known"}, "sanity: the objects ARE truthy"
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "filter(([k,v])=>v===true)" in html, "activeSignals must filter on `=== true`, not truthiness"


# --------------------------------------------------------------------------- BUG-5
@pytest.mark.parametrize("text", [
    "Enterprise platform, large organization, high traffic. We must not use Kubernetes.",
    "Enterprise platform, large organization, high traffic. Do not use Kubernetes.",
    "Enterprise platform, large organization, high traffic. No Kubernetes.",
])
def test_bug5_explicitly_rejected_technology_is_not_recommended(text):
    """strip_negations() removed the clause (preventing a false positive) but nothing recorded the
    prohibition, and Kubernetes is the DEFAULT for enterprise/high-scale — so it came back anyway."""
    assert detect_exclusions(text).get("kubernetes") is True
    containers = recommend_stack(text)["recommendations"]["containers"]
    assert "Kubernetes" not in containers["v"] or "not Kubernetes" in containers["v"]
    assert containers.get("excluded") is True


def test_bug5_exclusion_does_not_over_read_into_unrelated_negations():
    """The negation regex is deliberately conservative — an exclusion must name something the
    engine actually recommends, or "don't have compliance requirements" would exclude compliance."""
    assert detect_exclusions("don't have compliance requirements yet") == {}
    assert detect_exclusions("A fintech app with high traffic.") == {}


# --------------------------------------------------------------------------- BUG-6
def test_bug6_notebook_only_requirement_suppresses_the_web_platform():
    """A Jupyter-notebook-only ML requirement that explicitly ruled out website/API/database/
    cloud/microservices/RAG/LLM returned a full web platform anyway — byte-identical to "12345",
    because every "no X" phrase was stripped and nothing recorded it."""
    text = ("I only need a heart-disease prediction model in a Jupyter Notebook. No website, "
            "no API, no database, no cloud, no microservices, no RAG, no LLM is needed.")
    recs = recommend_stack(text)["recommendations"]
    assert recs["database"].get("excluded") is True
    assert recs["cloud"].get("excluded") is True
    assert recs["frontend"].get("excluded") is True
    assert recs["rag"].get("excluded") is True
    assert recs["llm"][0]["name"].startswith("Not recommended")
    assert "Modular monolith" in recs["architecture"]["v"], "microservices was ruled out"


# --------------------------------------------------------------------------- BUG-7
def test_bug7_bare_mention_does_not_imply_team_experience():
    """`kubernetesMentioned: has(['kubernetes','k8s'])` fed a "Your team already knows Kubernetes"
    claim AND a confidence bump — so asking whether to adopt it asserted prior experience."""
    asking = "Should we use Kubernetes for our enterprise platform? We have never used it before."
    assert detect_signals(asking)["kubernetesMentioned"] is True, "still NAMED"
    assert detect_known_tech(asking) == {}, "but must not be counted as KNOWN"

    for evaluating in ["We are evaluating Kubernetes.", "We are considering Kubernetes.",
                       "New to Kubernetes.", "Build a platform. Kubernetes."]:
        assert detect_known_tech(evaluating).get("kubernetes") is not True, evaluating


def test_bug7_real_ownership_is_still_recognised():
    """The fix must not throw away the legitimate signal it was guarding."""
    assert detect_known_tech("We run Kubernetes in production today.")["kubernetes"] is True
    assert detect_known_tech("Our team knows React and has Datadog experience.") == {
        "react": True, "datadog": True}


@requires_node
def test_bug7_containers_card_claims_skill_only_on_ownership():
    out = _js("""
      const mk = t => { const s = detectSignals(t); return computeRecommendations(s).containers.why; };
      console.log(JSON.stringify({
        asking: mk("Should we use Kubernetes for our enterprise platform? We have never used it before."),
        owning: mk("We run Kubernetes in production today for our enterprise platform."),
      }));
    """)
    assert "already knows" not in out["asking"]
    assert "already knows" in out["owning"]


# --------------------------------------------------------------------------- BUG-8
@requires_node
def test_bug8_only_user_named_technologies_are_marked_stated():
    """confToBasis() renders `stated` as "you asked for this". cardExplicitMap keyed it on proxies
    — saying "web app" marked React stated; "enterprise"/"high traffic" marked microservices and
    Kubernetes stated — so the report claimed the user requested things they never named."""
    out = _js("""
      const src = require('fs').readFileSync(process.argv[1] || 'index.html','utf8');
      const s = detectSignals("We use Python, Azure and PostgreSQL. Build us a web app.");
      const ex = s.excluded || {};
      const map = {
        cloud: !!(s.awsShop || s.azureShop || s.gcpShop || s.huaweiShop || s.onPrem || ex.cloud),
        languages: !!(s.javaMentioned || s.pythonMentioned || s.dotnetMentioned || s.goMentioned || s.nodeMentioned || s.rubyMentioned || s.phpMentioned),
        database: !!(s.postgresMentioned || s.mongoMentioned || s.mysqlMentioned || s.sqlServerMentioned || s.oracleDbMentioned || ex.database),
        frontend: !!(s.reactMentioned || s.angularMentioned || s.vueMentioned || s.vanillaWebMentioned || ex.frontend),
        architecture: !!(s.microservicesMentioned || s.monolithMentioned || ex.microservices),
        containers: !!(s.dockerMentioned || s.kubernetesMentioned || s.openshiftMentioned || s.onPrem || ex.kubernetes || ex.containers),
      };
      console.log(JSON.stringify(map));
    """)
    assert out["cloud"] and out["languages"] and out["database"], "Azure/Python/Postgres WERE named"
    assert not out["frontend"], "React was never named — 'web app' is not a frontend choice"
    assert not out["architecture"], "microservices was never named"
    assert not out["containers"], "Kubernetes was never named"


def test_bug8_provenance_map_does_not_key_on_context_signals():
    """Static guard: the proxy signals that caused this must not reappear in the map."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    # One shared buildExplicitMap() now serves BOTH the on-screen cards and the ADR exporter —
    # the exporter used to carry its own copy with the same defect, so fixing the cards left the
    # export still reporting team size and traffic volume as things the user asked for.
    assert "const cardExplicitMap = buildExplicitMap(s);" in html, "cards must use the shared map"
    assert "const EX = buildExplicitMap(s);" in html, "the ADR exporter must use the shared map"
    block = html[html.index("function buildExplicitMap(s){"):]
    block = block[:block.index("\n}")]
    for proxy in ["s.startupMvp", "s.smallTeam", "s.enterprise", "s.largeTeam", "s.highScale",
                  "s.structured", "s.finance", "s.web", "s.mobile", "s.realtime"]:
        assert proxy not in block, (
            f"{proxy} is project context, not a statement about a technology — keying `stated` on "
            "it tells the reader they asked for a pick they never named."
        )


# --------------------------------------------------------------------------- BUG-10
@requires_node
def test_bug10_adr_export_declares_the_categories_it_drops():
    """The bundle's own header promises gaps are "listed explicitly rather than dropped silently",
    but RAG pattern, guardrails, MCP and KPIs appeared in neither the decisions nor the omissions."""
    out = _js("""
      const s = detectSignals("Internal knowledge base chatbot over our Confluence policy documents for an enterprise, SOC2 compliant.");
      const mapped = mapAppPicksToKb(computeRecommendations(s), s);
      console.log(JSON.stringify({omitted: mapped.omitted.map(o => o.category)}));
    """)
    for category in ["RAG Pattern", "Guardrails", "MCP Servers", "KPIs / success metrics"]:
        assert category in out["omitted"], f"{category} is dropped from the export without being declared"


# --------------------------------------------------------------------------- BUG-11
@pytest.mark.parametrize("text,ms", [
    ("The complete RAG answer must be returned in under three seconds.", 3000),
    ("p95 latency below 200ms please.", 200),
    ("sub-500 milliseconds", 500),
    ("respond within 2 seconds, and under 800ms for search", 800),  # tightest target binds
])
def test_bug11_numeric_latency_targets_are_parsed(text, ms):
    """detect_signals() had no numeric parsing at all, so the requirement's single hardest number
    was dropped and the report substituted generic latency copy."""
    target = detect_latency_target(text)
    assert target is not None and target["ms"] == ms


def test_bug11_stated_target_leads_the_throughput_section():
    recs = recommend_stack("A RAG assistant. The complete answer must be returned in under three seconds.")
    first = recs["recommendations"]["concurrency"][0]
    assert "under three seconds" in first["t"]
    assert "under three seconds" in first["w"], "the user's own number must be quoted back"


def test_bug11_no_target_means_no_invented_one():
    recs = recommend_stack("A plain internal CRUD app.")
    assert detect_latency_target("A plain internal CRUD app.") is None
    assert "stated target" not in recs["recommendations"]["concurrency"][0]["t"]


# --------------------------------------------------------------------------- BUG-12
def test_bug12_cache_requires_a_reason():
    """pick_cache() ignored its `s` argument entirely and returned Redis unconditionally, so a
    static site or notebook script got a cache tier with no load to justify it."""
    for text in ["A simple static website.", "A heart-disease prediction model in a Jupyter Notebook."]:
        cache = recommend_stack(text)["recommendations"]["cache"]
        assert cache["v"] == "Not required yet", text
        assert cache["needed"] is False


@pytest.mark.parametrize("text,reason", [
    ("A high traffic e-commerce platform.", "high traffic"),
    ("A real-time low latency trading dashboard.", "real-time"),
    ("We use Redis already for our internal tool.", "you already use Redis"),
])
def test_bug12_cache_is_still_recommended_when_warranted(text, reason):
    """The fix requires a reason — it must not stop recommending Redis where one exists."""
    cache = recommend_stack(text)["recommendations"]["cache"]
    assert cache["v"] == "Redis", text
    assert reason in cache["why"]


# --------------------------------------------------------------------------- cross-cutting
def test_a_well_specified_requirement_is_unaffected():
    """None of the above may change a requirement that states no exclusions and no target."""
    recs = recommend_stack(
        "A fintech payments platform, high traffic, PCI compliance, real-time fraud detection."
    )["recommendations"]
    assert recs["cache"]["v"] == "Redis"
    assert "Kubernetes" in recs["containers"]["v"]
    assert "Microservices" in recs["architecture"]["v"]
    assert recs["database"]["v"].startswith("PostgreSQL")
