"""Regression tests for four "domain floor" gaps found in a manual QA sweep
(docs/manual-qa-test-matrix.csv TC-05/06/07/09) — all four independently verified as real,
reproducible bugs against the live app before any fix existed, not trusted from an external
report at face value:

- A browser extension request got the full enterprise web stack (AWS, React, PostgreSQL) with
  zero signals detected.
- A local CLI log-analysis tool got AWS + Kubernetes + RabbitMQ + PostgreSQL + React with NO
  low-signal honesty banner (worse than the browser-extension case — confidently wrong).
- A static marketing site with "no backend" got Docker + Kubernetes + PostgreSQL anyway; the
  one signal detected ("web") had nothing to do with the "no backend" statement.
- A cross-platform desktop app with explicit "no backend server" / "data stays on the user's
  machine" got zero signals detected and the same enterprise cloud defaults.

Asserted against BOTH engines (rule_engine.py and index.html's JS twin — independent
implementations, see test_engine_differential.py) end-to-end through recommend_stack()/
computeRecommendations(), not just the raw signal dict.
"""
import shutil
from pathlib import Path

import pytest

from app.rule_engine import detect_signals, recommend_stack
from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

_STUBS = r"""
const dummyEl = { style:{}, classList:{add(){},remove(){},toggle(){}}, addEventListener(){},
  setAttribute(){}, getAttribute:()=>null, appendChild(){}, removeChild(){}, click(){}, focus(){},
  querySelector:()=>null, querySelectorAll:()=>[], innerHTML:'', textContent:'', value:'',
  scrollIntoView(){} };
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


BROWSER_EXTENSION_TEXT = "We are building a Chrome extension that helps users summarize web pages using an LLM."
CLI_TOOL_TEXT = "We are building a command line tool in Python that analyzes log files."
STATIC_SITE_TEXT = "I want to make a simple static marketing website with no backend."
DESKTOP_APP_TEXT = (
    "Cross-platform desktop application for Windows and Mac, no backend server, "
    "data stays entirely on the user's machine, small team of 3."
)

FLOOR_CATEGORIES = ("cloud", "containers", "database", "iam", "observability", "messaging", "compute", "architecture")


# --------------------------------------------------------------------------- signal detection

def test_browser_extension_signal_fires():
    assert detect_signals(BROWSER_EXTENSION_TEXT)["browserExtension"] is True


def test_cli_tool_signal_fires():
    assert detect_signals(CLI_TOOL_TEXT)["cliTool"] is True


def test_desktop_app_signal_fires():
    assert detect_signals(DESKTOP_APP_TEXT)["desktopApp"] is True


def test_static_site_signal_fires():
    assert detect_signals(STATIC_SITE_TEXT)["staticSite"] is True


def test_static_site_requires_both_halves_not_just_no_backend():
    """"no backend" alone (no static-site phrase) must NOT fire — it has other, unrelated
    meanings elsewhere and firing on it alone would over-match a normal web app that merely
    doesn't need a backend for some other reason."""
    assert detect_signals("A mobile app with no backend, just local storage.")["staticSite"] is False


def test_static_site_requires_both_halves_not_just_the_static_phrase():
    """A "landing page" mention alone, with no "no backend" statement, must NOT fire — plenty
    of landing pages have a real backend (forms, A/B testing, personalization)."""
    assert detect_signals("We need a landing page with a signup form that saves to our CRM.")["staticSite"] is False


# --------------------------------------------------------------- end-to-end recommendation

def test_browser_extension_gets_a_no_server_stack_not_the_enterprise_default():
    rec = recommend_stack(BROWSER_EXTENSION_TEXT)["recommendations"]
    for key in FLOOR_CATEGORIES:
        assert "Not applicable" in rec[key]["v"], f"{key}: {rec[key]['v']}"
    assert "Manifest V3" in rec["frontend"]["v"]


def test_cli_tool_gets_a_no_server_stack_not_the_enterprise_default():
    rec = recommend_stack(CLI_TOOL_TEXT)["recommendations"]
    for key in FLOOR_CATEGORIES:
        assert "Not applicable" in rec[key]["v"], f"{key}: {rec[key]['v']}"
    assert "command-line" in rec["frontend"]["v"].lower()
    assert "Kubernetes" not in rec["containers"]["v"]
    assert "AWS" not in rec["cloud"]["v"]


def test_desktop_app_gets_local_stack_with_embedded_sqlite_not_hosted_postgres():
    rec = recommend_stack(DESKTOP_APP_TEXT)["recommendations"]
    for key in ("cloud", "containers", "iam", "observability", "messaging", "compute", "architecture"):
        assert "Not applicable" in rec[key]["v"], f"{key}: {rec[key]['v']}"
    assert "SQLite" in rec["database"]["v"]
    assert "PostgreSQL" not in rec["database"]["v"]
    assert "Tauri" in rec["frontend"]["v"] or "Electron" in rec["frontend"]["v"]


def test_static_site_gets_cdn_hosting_not_full_iaas_and_no_containers_or_database():
    rec = recommend_stack(STATIC_SITE_TEXT)["recommendations"]
    assert "CDN" in rec["cloud"]["v"]
    assert "Not applicable" in rec["containers"]["v"]
    assert "Not applicable" in rec["database"]["v"]
    assert "Kubernetes" not in rec["containers"]["v"]
    assert "PostgreSQL" not in rec["database"]["v"]


def test_domain_floors_do_not_fire_on_a_normal_enterprise_requirement():
    """Regression guard: the four new signals must not accidentally fire on ordinary web-app
    requirements and start suppressing categories that should stay populated."""
    text = ("We're a fintech startup building a mobile + web app for real-time fraud detection "
            "on card transactions. SOC2/PCI compliant, small team of 6 engineers.")
    s = detect_signals(text)
    assert not any(s.get(k) for k in ("browserExtension", "cliTool", "desktopApp", "staticSite"))
    rec = recommend_stack(text)["recommendations"]
    assert "Not applicable" not in rec["cloud"]["v"]
    assert "Not applicable" not in rec["database"]["v"]


def test_explicit_exclusion_still_wins_over_the_inferred_domain_floor():
    """Domain floors run BEFORE apply_exclusions — an explicit, user-stated exclusion on the
    same category must still get the final "you excluded X" wording, not the inferred one."""
    text = "We are building a command line tool in Python. We must not use Datadog or any observability vendor."
    rec = recommend_stack(text)["recommendations"]
    # observability was BOTH domain-floor-suppressed (cliTool) AND explicitly excluded by the
    # user — the explicit, user-stated wording must win, since it ran second.
    assert "you excluded" in rec["observability"]["v"]
    # cloud has no explicit exclusion — domain-floor wording stands for it.
    assert "Not applicable" in rec["cloud"]["v"]


# --------------------------------------------------------------------------- JS parity

@requires_node
def test_js_all_four_domain_floors_match_python():
    out = _js(f"""
      console.log(JSON.stringify({{
        browserExtension: detectSignals({BROWSER_EXTENSION_TEXT!r}).browserExtension,
        cliTool: detectSignals({CLI_TOOL_TEXT!r}).cliTool,
        desktopApp: detectSignals({DESKTOP_APP_TEXT!r}).desktopApp,
        staticSite: detectSignals({STATIC_SITE_TEXT!r}).staticSite,
      }}));
    """)
    assert out == {"browserExtension": True, "cliTool": True, "desktopApp": True, "staticSite": True}


@requires_node
def test_js_cli_tool_end_to_end_matches_python():
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({CLI_TOOL_TEXT!r}));
      console.log(JSON.stringify({{
        cloud: rec.cloud.v, containers: rec.containers.v, db: rec.db.v, fe: rec.fe.v,
      }}));
    """)
    assert "Not applicable" in out["cloud"]
    assert "Not applicable" in out["containers"]
    assert "Not applicable" in out["db"]
    assert "command-line" in out["fe"].lower()


@requires_node
def test_js_ambiguous_short_input_banner_fires_for_language_only_mention():
    """"Java or python" (TC-08) already has real signals (language mentions), so the pre-existing
    zero-signal lowSignalBanner never fires for it — this is index.html-only (no Python
    equivalent; banners are a UI-rendering concern, not part of recommend_stack's output).
    renderRecommendations() writes to document.getElementById('results').innerHTML rather than
    returning a string — dummyEl is shared across every element id in this stub, and nothing
    else in this script writes to it after renderRecommendations runs, so reading it back
    afterward reflects the render output.
    """
    out = _js("""
      // dummyEl is shared across EVERY element id — renderRecommendations() also calls
      // renderFlowLegend() etc., which write to the SAME shared object afterward and clobber
      // whatever renderRecommendations wrote to 'results'. Give 'results' its own dedicated
      // node, the same fix test_analysis_history.py's TC-16 test needed for 'sidebarHistoryList'.
      const resultsNode = Object.assign({}, dummyEl, { innerHTML: '' });
      const origGetById = document.getElementById;
      document.getElementById = (id) => id === 'results' ? resultsNode : origGetById(id);
      const s = detectSignals('Java or python');
      const rec = computeRecommendations(s);
      lastRequirementText = 'Java or python';
      renderRecommendations(s, rec);
      console.log(JSON.stringify({ hasBanner: resultsNode.innerHTML.includes('Very little context to go on') }));
    """)
    assert out["hasBanner"] is True


@requires_node
def test_js_ambiguous_short_input_banner_does_not_fire_for_a_real_requirement():
    out = _js(f"""
      const resultsNode = Object.assign({{}}, dummyEl, {{ innerHTML: '' }});
      const origGetById = document.getElementById;
      document.getElementById = (id) => id === 'results' ? resultsNode : origGetById(id);
      const text = {BROWSER_EXTENSION_TEXT!r};
      const s = detectSignals(text);
      const rec = computeRecommendations(s);
      lastRequirementText = text;
      renderRecommendations(s, rec);
      console.log(JSON.stringify({{ hasBanner: resultsNode.innerHTML.includes('Very little context to go on') }}));
    """)
    assert out["hasBanner"] is False
