"""The hosted page must not fall through to localhost.

index.html resolves API_BASE as window.__API_BASE__ → <meta name="api-base"> → and finally
`http://localhost:8000`. That fallback is right for local development and wrong for everyone
else: on GitHub Pages the one-time /health probe fails, backendAvailable goes false, and Refine,
Ask, saved analyses and live cost tracking quietly stop existing. Nothing errors, nothing is
logged, and the page still looks entirely functional — which is why this shipped unnoticed.

The core analysis is deliberately unaffected: it runs client-side with no network calls at all
(AGENTS.md's offline invariant, NFR-1/NFR-5). This guards only the optional backend features.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
RENDER_YAML = ROOT / "render.yaml"


def _meta_tag() -> str | None:
    """The real element, not the two prose mentions of it.

    index.html contains `<meta name="api-base" ...>` inside an explanatory comment and again as
    a querySelector argument. A substring search finds three hits and proves nothing, so this
    anchors to a tag at the start of a line — which is what the browser actually parses.
    """
    m = re.search(r'^\s*<meta\s+name="api-base"\s+content="([^"]*)"', INDEX.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else None


def test_the_page_declares_an_api_base():
    assert _meta_tag() is not None, (
        "no <meta name=\"api-base\"> element in index.html — the hosted page falls through to "
        "http://localhost:8000 and every backend feature is dead for real visitors"
    )


def test_the_declared_api_base_is_not_a_developer_machine():
    v = _meta_tag() or ""
    for local in ("localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal"):
        assert local not in v, f"api-base points at {v!r} — that resolves to the visitor's own machine"
    assert v.startswith("https://"), f"api-base must be https for a page served over https, got {v!r}"


def test_the_api_base_is_an_origin_not_a_url_with_a_path():
    """API_BASE is concatenated with paths like `/health` and `/api/refine`. A trailing slash or
    a path segment produces `//health` or `/sub//api/refine` — requests that 404 against a
    service that is up."""
    v = _meta_tag() or ""
    assert not v.endswith("/"), f"trailing slash in api-base produces a doubled slash on every call: {v!r}"
    assert v.count("/") == 2, f"api-base should be scheme://host with no path, got {v!r}"


@pytest.mark.skipif(not RENDER_YAML.exists(), reason="no render blueprint in this repo")
def test_cors_allows_the_origin_the_page_is_served_from():
    """CORSMiddleware matches the browser's Origin header, which is scheme + host only. A
    CORS_ORIGINS value carrying a path never matches, and the failure surfaces in the browser
    console as a CORS error against an API that is healthy and reachable."""
    cors = re.search(r'key:\s*CORS_ORIGINS\s*\n\s*value:\s*(\S+)', RENDER_YAML.read_text(encoding="utf-8"))
    assert cors, "render.yaml does not set CORS_ORIGINS"
    for origin in cors.group(1).split(","):
        assert origin.count("/") == 2, f"CORS origin must be scheme://host with no path, got {origin!r}"
        assert not origin.endswith("/"), f"trailing slash never matches an Origin header: {origin!r}"


@pytest.mark.skipif(not RENDER_YAML.exists(), reason="no render blueprint in this repo")
def test_the_blueprint_points_at_files_that_exist():
    """A blueprint referencing a missing Dockerfile fails at build time on Render, not here."""
    y = RENDER_YAML.read_text(encoding="utf-8")
    for key in ("dockerfilePath", "dockerContext"):
        m = re.search(rf'{key}:\s*(\S+)', y)
        assert m, f"render.yaml has no {key}"
        assert (ROOT / m.group(1)).exists(), f"{key} points at {m.group(1)}, which does not exist"
