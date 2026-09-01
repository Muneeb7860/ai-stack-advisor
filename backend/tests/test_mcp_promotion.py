"""Surfacing the MCP server in the UI.

The server has existed and been tested since the rule-engine port (backend/app/mcp/server.py,
docs/adr/0001-mcp-rule-engine-port.md) and was promoted in neither index.html nor landing.html, so
the only people who could know it existed were the ones who had read the backend source. This adds
a modal, a sidebar entry, a command-palette action, and a landing-page section.

The tests that matter here are the ones checking the advertised config against the SERVER ITSELF
rather than against a copy of the string. An install snippet is uniquely bad to get wrong: it is
copied verbatim into someone else's machine, and it fails there, in their editor, with no obvious
connection back to this page. A review document proposing this feature supplied this config:

    {"mcpServers": {"ai-stack-advisor": {"command": "python",
                                         "args": ["-m", "backend.app.mcp_server"]}}}

Every part of which is wrong. The module is `app.mcp.server` (the package root is backend/, so
`backend.app.mcp_server` resolves to nothing), there is no `cwd`, so it would not resolve even
with the right module name, and there is no `env.DATABASE_URL` — which the server's own
_validate_startup_config() requires, because MCP's stdio_client does not inherit the parent
shell's environment and an unset DATABASE_URL silently falls back to the module default. Shipping
it would have produced a server that exits(1), or worse, one that answers tools/list while being
unable to serve a single call.

So these assertions derive from the source: the module path is checked by importability, and the
DATABASE_URL requirement is checked against the startup validator that enforces it.
"""
import json
import re
from pathlib import Path

import pytest

from tests.node_harness import run_node_script

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
LANDING = ROOT / "landing.html"
SERVER = ROOT / "backend" / "app" / "mcp" / "server.py"


def _index() -> str:
    return INDEX.read_text(encoding="utf-8")


def _advertised_config() -> dict:
    """The snippet the UI hands the user.

    Evaluated under Node rather than regex-converted to JSON. A first version did the latter and
    silently corrupted the value: the "bare keys -> quoted keys" substitution also fired inside
    the connection string, turning `localhost:5432` into a key. Running the real declaration gives
    the exact object the page builds, which is the thing under test anyway.
    """
    m = re.search(r"(const MCP_CONFIG_SNIPPET = JSON\.stringify\(\{.*?\}, null, 2\);)",
                  _index(), re.S)
    assert m, "MCP_CONFIG_SNIPPET not found"
    return json.loads(run_node_script(m.group(1) + "\nconsole.log(MCP_CONFIG_SNIPPET);"))


def _server_entry():
    return _advertised_config()["mcpServers"]["ai-stack-advisor"]


# ------------------------------------------------- the config must match the actual server

def test_the_advertised_module_path_actually_exists():
    """`python -m app.mcp.server` has to resolve from the advertised cwd. Derived from the
    filesystem, so moving or renaming the server breaks this test rather than breaking a
    stranger's editor config silently."""
    args = _server_entry()["args"]
    assert args[0] == "-m", f"expected a module invocation, got {args}"
    module = args[1]
    assert module == "app.mcp.server", (
        f"advertised module is {module!r}; the package root is backend/, so anything like "
        f"'backend.app.mcp_server' resolves to nothing"
    )
    resolved = ROOT / "backend" / Path(module.replace(".", "/") + ".py")
    assert resolved.exists(), f"{module} does not resolve to a real file ({resolved})"
    assert resolved == SERVER


def test_the_cwd_is_the_package_root_not_the_repo_root():
    """Without this the module never resolves, whatever its name. It's the field most easily
    dropped as boilerplate, because a config missing it *looks* complete."""
    cwd = _server_entry()["cwd"]
    assert cwd.rstrip("/").endswith("backend"), (
        f"cwd is {cwd!r} — `app.mcp.server` only resolves with backend/ as the working directory"
    )


def test_database_url_is_set_because_the_server_refuses_to_start_without_it():
    """Cross-checked against the validator that enforces it, not against a remembered fact. The
    server exits(1) on an unreachable DB precisely because stdio_client does not inherit the
    parent environment, so omitting this from the snippet ships a config that cannot work."""
    env = _server_entry().get("env", {})
    assert "DATABASE_URL" in env, "the snippet must set DATABASE_URL explicitly"
    assert env["DATABASE_URL"].startswith("postgresql://")

    source = SERVER.read_text(encoding="utf-8")
    assert "_validate_startup_config" in source and "sys.exit(1)" in source, (
        "this test's premise is that the server hard-fails without a reachable DB; if that "
        "changed, revisit the snippet and this test together"
    )


def test_the_advertised_tool_name_is_the_one_the_server_exposes():
    source = SERVER.read_text(encoding="utf-8")
    assert re.search(r"@mcp\.tool\(\)\s*\ndef recommend_stack\(", source), (
        "recommend_stack is no longer the exposed tool — the UI copy names it explicitly"
    )
    assert "recommend_stack" in _index()


def test_the_snippet_has_exactly_one_source():
    """The copy button and the rendered block must not be able to drift: what you copy has to be
    what is shown, or the modal quietly starts lying."""
    text = _index()
    assert text.count("const MCP_CONFIG_SNIPPET") == 1
    assert "block.textContent = MCP_CONFIG_SNIPPET" in text, "the block renders from the constant"
    assert "writeText(MCP_CONFIG_SNIPPET)" in text, "the copy button copies the same constant"


def test_the_config_block_is_rendered_as_text_not_markup():
    """textContent, not innerHTML — the snippet is data being displayed, and nothing about it
    should ever be parsed as HTML."""
    m = re.search(r"function openMcpModal\(\)\{(.*?)\n\}", _index(), re.S)
    assert m
    # Comments stripped first. The function's own comment explains why innerHTML is not used, and
    # matching that made this fail against correct code — the same comment-vs-code confusion that
    # has made other assertions in this suite pass against incorrect code.
    body = re.sub(r"//[^\n]*", "", m.group(1))
    assert "innerHTML" not in body


# -------------------------------------------------------------------------------- wiring

def test_escape_closes_the_new_modal():
    """Every drawer and modal in this app honours Escape; a new one either joins the teardown or
    becomes the single exception users find by accident."""
    # Anchored on closeExportMenu(), which is the first line of the GLOBAL teardown. A looser
    # regex matched the command palette's own earlier Escape handler instead and failed against
    # a block that was never supposed to contain this call.
    m = re.search(r"if \(e\.key === 'Escape'\) \{\s*\n\s*closeExportMenu\(\);(.*?)\n  \}",
                  _index(), re.S)
    assert m, "the global Escape teardown was not found"
    # Comments stripped: every line in this block carries a trailing `// why` comment, and
    # commenting the call OUT left the string present, so the test passed on a broken teardown.
    body = re.sub(r"//[^\n]*", "", m.group(1))
    assert "closeMcpModal()" in body


def test_backdrop_click_dismisses_the_modal():
    m = re.search(r'<div id="mcpModal"[^>]*onclick="([^"]*)"', _index())
    assert m and "closeMcpModal" in m.group(1)


def test_the_command_palette_offers_it_without_requiring_an_analysis():
    """Connecting your editor is useful before you have run anything — arguably most useful then,
    since the point is to stop needing this page. So it must sit outside the analysisOnScreen
    block, which gates the export commands."""
    m = re.search(r"function cmdkBuildItems\(\)\{(.*?)\n\}", _index(), re.S)
    assert m, "cmdkBuildItems not found"
    body = m.group(1)
    assert "openMcpModal()" in body, "the palette should offer the MCP modal"
    gated = re.search(r"if \(analysisOnScreen\) \{(.*?)\n  \}", body, re.S)
    assert gated, "the analysisOnScreen block was not found"
    assert "openMcpModal()" not in gated.group(1), (
        "the MCP command must not be gated on an analysis existing"
    )


def test_the_sidebar_entry_is_always_visible():
    """#sidebarExportShare is display:none until an analysis exists. The MCP entry must sit
    outside it for the same reason as the palette command."""
    text = _index()
    entry = text.index('onclick="openMcpModal()"')
    hidden_block = text.index('<div id="sidebarExportShare"')
    assert entry < hidden_block, (
        "the sidebar MCP button is inside #sidebarExportShare, so it inherits display:none and "
        "is invisible until the user has already run an analysis"
    )


def test_the_modal_is_reachable_from_a_visible_control():
    """A palette-only entry point is only discoverable by people who already know it exists —
    which is the exact problem this change is fixing."""
    assert _index().count('onclick="openMcpModal()"') >= 1


# ------------------------------------------------------------------------------- landing

def test_the_landing_page_mentions_the_server_at_all():
    """It previously had zero mentions."""
    text = LANDING.read_text(encoding="utf-8")
    assert 'id="mcp"' in text
    assert "recommend_stack" in text


def test_the_landing_section_inherits_the_existing_reveal_animation():
    """The observer targets .section-head and .pillar. Using those classes means the new section
    animates like every other one with no change to the script — and, more importantly, is
    covered by the existing failsafe rather than needing its own."""
    text = LANDING.read_text(encoding="utf-8")
    m = re.search(r'<section id="mcp">(.*?)</section>', text, re.S)
    assert m, "the MCP section was not found"
    body = m.group(1)
    assert 'class="section-head"' in body and 'class="pillar"' in body

    targets = re.search(r"querySelectorAll\('([^']*\.pillar[^']*)'\)", text)
    assert targets, "the reveal target list was not found"
    assert ".section-head" in targets.group(1) and ".pillar" in targets.group(1)


@pytest.mark.parametrize("claim", ["45+", "recommend_stack"])
def test_landing_claims_are_grounded_in_the_server_source(claim):
    """This page's own pitch is that its numbers are real. The '45+ decisions' figure and the tool
    name both come from the server's docstring — asserted so the copy can't drift from it."""
    assert claim in LANDING.read_text(encoding="utf-8")
    assert claim in SERVER.read_text(encoding="utf-8")
