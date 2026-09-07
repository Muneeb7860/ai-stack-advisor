"""A requirement with no LLM in it must not be shown eleven sections about LLMs.

Reported by a user, in these words: "if i want small small static web page it giving more than
20 cards then how is this optimal suggestion". They were right, and precisely so — "a simple
static marketing website, no backend, just HTML and CSS" produced 25 cards across 18 sections,
eleven of which were LLM sections (model choice, orchestration, hosting, topology, MCP, agent
framework, LLM observability, RAG, vector DB, guardrails), and the architecture diagram drew
AWS API Gateway, FastAPI/Spring Boot, GPT-4o, MCP servers and Terraform+Kubernetes nodes.

The domain floors existed, but only at the level of pick CONTENT: every card still rendered and
captioned itself "Not applicable — static site". A floor that still costs the reader a card has
not floored anything.

The whole 1,422-test suite passed while this was true, which is the more useful finding: section
visibility had no coverage at all, so any future narrowing or widening of it was unobservable.
"""
import shutil
from pathlib import Path

import pytest

from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

# computeVisibleSections is a rendering decision and lives only in index.html — rule_engine.py has
# no section concept, and the API returns every recommendation regardless. So this is frontend-only
# by construction and carries no parity surface, like the other entry/render-mode functions.
_STUBS = r"""
const d = {style:{}, classList:{add(){},remove(){},toggle(){}}, addEventListener(){}, setAttribute(){},
  getAttribute:()=>null, appendChild(){}, removeChild(){}, click(){}, focus(){}, querySelector:()=>null,
  querySelectorAll:()=>[], innerHTML:'', textContent:'', value:''};
global.window = {location:{search:''}, addEventListener(){}, matchMedia:()=>({matches:false,addEventListener(){}})};
global.document = {documentElement:d, body:d, querySelector:()=>d, querySelectorAll:()=>[],
  createElement:()=>d, addEventListener(){}, getElementById:()=>d};
global.navigator = {clipboard:{}};
global.localStorage = {getItem:()=>null, setItem(){}, removeItem(){}};
global.fetch = () => Promise.resolve({ok:false});
global.URL = {createObjectURL:()=>'', revokeObjectURL(){}};
global.requestAnimationFrame = (f) => f();
"""

AI_SECTIONS = {"llm", "orchestration", "hosting", "topology", "mcpapi", "mcpservers",
               "agentframework", "llmobservability", "rag", "vectordb", "guardrails"}
SERVER_SECTIONS = {"iamcompare", "throughput"}

# The four shapes that run no server of their own.
NO_SERVER = [
    ("static site", "A simple static marketing website, no backend, just HTML and CSS. Solo developer."),
    ("CLI tool", "A command line tool in Python that analyses local log files. Solo developer."),
    ("browser extension", "A Chrome extension with Manifest V3 that summarises web pages."),
    ("desktop app", "Cross-platform desktop application, no backend server, data stays on the machine."),
]


def _sections(requirements: list[str]) -> dict[str, list[str]]:
    body = (
        "const out = {};\n"
        f"for (const t of {requirements!r}) out[t] = [...computeVisibleSections(detectSignals(t))];\n"
        "console.log(JSON.stringify(out));"
    ).replace("'", '"')
    main = INDEX_HTML.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]
    return run_node_json(_STUBS + main + "\n" + body)


@requires_node
@pytest.mark.parametrize("label,requirement", NO_SERVER)
def test_a_project_with_no_llm_is_not_shown_llm_sections(label, requirement):
    got = set(_sections([requirement])[requirement])
    assert not (got & AI_SECTIONS), (
        f"{label} was shown LLM sections it never asked for: {sorted(got & AI_SECTIONS)}"
    )


@requires_node
@pytest.mark.parametrize("label,requirement", NO_SERVER)
def test_a_project_with_no_server_is_not_shown_server_sections(label, requirement):
    """An identity-provider bake-off and a concurrency plan both presuppose a server tier."""
    got = set(_sections([requirement])[requirement])
    assert not (got & SERVER_SECTIONS), (
        f"{label} was shown server-tier sections: {sorted(got & SERVER_SECTIONS)}"
    )


@requires_node
def test_the_llm_gate_is_the_ai_signal_not_the_domain_floor():
    """The fault was general, not floor-specific. A perfectly ordinary server-backed web app with
    no AI requirement was also getting all eleven LLM sections — it just never looked as absurd
    as it did on a static page, so nobody reported it."""
    req = "A B2B web application with Postgres and 500 concurrent users on AWS."
    got = set(_sections([req])[req])
    assert not (got & AI_SECTIONS), f"a non-AI web app still gets LLM sections: {sorted(got & AI_SECTIONS)}"
    # It does run a server, so these must survive — this is what separates the AI gate from the floor.
    assert SERVER_SECTIONS <= got, f"a server-backed app lost its server sections: {sorted(SERVER_SECTIONS - got)}"


@requires_node
@pytest.mark.parametrize("requirement", [
    "A customer support chatbot for our web app.",
    "Internal knowledge assistant with RAG over our Confluence policy documents.",
    "An agentic workflow that takes actions against our internal tools.",
])
def test_a_real_ai_requirement_keeps_every_llm_section(requirement):
    """The narrowing must not cost anything to the users the sections exist for. This is the
    assertion that stops a future tightening from quietly gutting the product's main feature."""
    got = set(_sections([requirement])[requirement])
    assert AI_SECTIONS <= got, f"an AI requirement lost LLM sections: {sorted(AI_SECTIONS - got)}"


@requires_node
def test_the_brownfield_modes_are_unchanged():
    """Both predate this change and have their own reasons; the new filtering runs after them and
    must not reach them."""
    guardrails_only = "We already have AI built and running in production; we just need our guardrails reviewed."
    ai_only = "We already have an application in production and only want to add AI to our existing system."
    got = _sections([guardrails_only, ai_only])
    assert set(got[guardrails_only]) == {"guardrails"}
    assert "stack" not in got[ai_only] and "llm" in got[ai_only]


# ---------------------------------------------------------------- the cards inside the stack section
# Narrowing the SECTION list took the static site from 18 sections to 5 and left the card count at
# 25, because almost every card lives inside the single "Core Technical Stack" section. Seven of
# those cards said nothing but "Not applicable — a static site has no application architecture".
NOT_APPLICABLE_RE = r"^\s*Not applicable\b"


def _stack_picks(requirement: str) -> list[str]:
    """The pick text of every card the stack section renders, in order."""
    body = (
        f'const rec = computeRecommendations(detectSignals({requirement!r}));\n'
        "const keys = ['cloud','gw','iam','lang','arch','compute','msg','mesh','cache','db',"
        "'containers','obs','fe','cicd','dns','hybridConnectivity','multiCloudBridging'];\n"
        "console.log(JSON.stringify(keys.map(k => String((rec[k]||{}).v ?? '')).filter(Boolean)));"
    ).replace("'", '"')
    main = INDEX_HTML.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]
    return run_node_json(_STUBS + main + "\n" + body)


@requires_node
@pytest.mark.parametrize("label,requirement", NO_SERVER)
def test_the_floors_still_emit_not_applicable_picks_for_the_filter_to_catch(label, requirement):
    """The card filter keys off this exact wording, so if the floors ever stop producing it the
    filter silently stops filtering. This pins the contract between the two."""
    import re as _re
    picks = _stack_picks(requirement)
    assert any(_re.match(NOT_APPLICABLE_RE, p, _re.I) for p in picks), (
        f"{label} produced no 'Not applicable' pick — the stack-card filter now removes nothing"
    )


def test_the_card_filter_keeps_user_exclusions_visible():
    """'Not recommended — you excluded a service mesh' must keep rendering: the user asked for
    that exclusion and seeing it confirmed is the whole point. Only 'Not applicable', which the
    domain floors emit for categories that cannot exist, is removed. Asserted against the source
    because it is the filter's predicate that has to make this distinction."""
    src = INDEX_HTML.read_text(encoding="utf-8")
    assert '.filter(([, pick]) => !/^\\s*Not applicable\\b/i.test(String(pick ?? \'\')));' in src, (
        "the stack-card filter changed shape — confirm it still removes only 'Not applicable' "
        "and never 'Not recommended — you excluded ...'"
    )


@requires_node
def test_the_filter_never_removes_a_real_decision_from_a_normal_app():
    """Written first as "a normal web app loses no cards" — and it failed, correctly.

    A single-cloud B2B app does produce one: multiCloudBridging reads "Not applicable — single
    cloud provider in use". Removing that is right; a card explaining that multi-cloud bridging
    is not applicable to your single-cloud app is precisely the noise this filter exists for. The
    assumption was wrong, not the filter.

    So the property worth pinning is not "removes nothing" but "removes nothing that is a real
    decision" — every load-bearing pick must survive.
    """
    import re as _re
    picks = _stack_picks("A B2B web application with Postgres and 500 concurrent users on AWS.")
    kept = [p for p in picks if not _re.match(NOT_APPLICABLE_RE, p, _re.I)]
    removed = [p for p in picks if _re.match(NOT_APPLICABLE_RE, p, _re.I)]

    assert all("Not applicable" in p for p in removed), removed
    # The stack this app actually has to build. Losing any of these would be the filter
    # over-reaching, which is the failure mode that matters.
    for essential in ("AWS", "PostgreSQL"):
        assert any(essential in p for p in kept), f"the filter removed the {essential} pick"
    assert len(kept) >= 12, f"only {len(kept)} cards survived on a normal app — filter is too broad"
