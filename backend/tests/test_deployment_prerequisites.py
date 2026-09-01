"""Deployment prerequisites — the gaps that would break a hosted deploy, all fixable locally.

Identified while writing docs/deployment/GCP_DEPLOYMENT_PLAN.md and fixed before any
provisioning, because each one fails in a way that is hard to diagnose from the outside:

  1. API_BASE was hardcoded to localhost:8000, so a hosted frontend silently discarded every
     feedback submission — the user still sees a thank-you, by design.
  2. The Dockerfile never ran migrations. docker-compose runs `alembic upgrade head` in its own
     `command:` (which overrides CMD), so that path was covered while a plain `docker run` or a
     Cloud Run deploy started against a database with no schema.
  3. The Dockerfile hardcoded port 8000. Cloud Run injects $PORT and routes to it, so a fixed
     port means the container is up and nothing reaches it — surfacing as a generic "container
     failed to start".
  4. CORS defaults to localhost. Misconfigured, the API is up and curl works while the browser
     shows an opaque network error with no server-side trace.

None of these needed GCP to find or to fix.
"""
import re
import shutil
from pathlib import Path

import pytest

from tests.node_harness import run_node_json

ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "index.html"
DOCKERFILE = ROOT / "backend" / "Dockerfile"
COMPOSE = ROOT / "backend" / "docker-compose.yml"
MAIN_PY = ROOT / "backend" / "app" / "main.py"

requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)


def _main_script() -> str:
    return INDEX_HTML.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]


def _js(body: str, head: str = ""):
    stubs = f"""
const dummyEl = {{ style:{{}}, classList:{{add(){{}},remove(){{}},toggle(){{}}}}, addEventListener(){{}},
  setAttribute(){{}}, getAttribute:()=>null, appendChild(){{}}, removeChild(){{}}, click(){{}}, focus(){{}},
  querySelector:()=>null, querySelectorAll:()=>[], innerHTML:'', textContent:'', value:'' }};
global.window = {{ innerWidth:1280, location:{{search:''}}, addEventListener(){{}},
  matchMedia:()=>({{matches:false,addEventListener(){{}}}}) }};
global.document = {{ documentElement:dummyEl, body:dummyEl, querySelector:()=>null,
  querySelectorAll:()=>[], getElementById:()=>dummyEl, createElement:()=>dummyEl, addEventListener(){{}} }};
global.navigator = {{ clipboard:{{}} }};
global.localStorage = {{ getItem:()=>null, setItem(){{}}, removeItem(){{}} }};
global.fetch = () => Promise.resolve({{ ok:false }});
global.URL = {{ createObjectURL:()=>'', revokeObjectURL(){{}} }};
global.requestAnimationFrame = (fn) => fn();
{head}
"""
    return run_node_json(stubs + _main_script() + "\n" + body)


# ------------------------------------------------------------------ 1. API_BASE is overridable

@requires_node
def test_api_base_defaults_to_localhost_when_nothing_overrides_it():
    """Opening index.html directly must still reach a local backend, and the fully-offline v1
    path (NFR-5) is unaffected either way."""
    assert _js("console.log(JSON.stringify(API_BASE));") == "http://localhost:8000"


@requires_node
def test_api_base_can_be_overridden_by_a_global():
    """For a host or edge worker that injects the value before the script runs."""
    out = _js("console.log(JSON.stringify(API_BASE));",
              head="global.window.__API_BASE__ = 'https://api.example.com';")
    assert out == "https://api.example.com"


@requires_node
def test_api_base_can_be_overridden_by_a_meta_tag():
    """The preferred route for static hosting — one line of HTML at deploy time, no source edit,
    which matters because this product ships as a single file with no build step to substitute
    a value into."""
    out = _js("console.log(JSON.stringify(API_BASE));", head="""
      global.document.querySelector = (sel) =>
        sel === 'meta[name="api-base"]' ? { getAttribute: () => 'https://api.example.com' } : null;
    """)
    assert out == "https://api.example.com"


@requires_node
def test_api_base_resolution_never_throws():
    """It runs at module load, so an exception here takes the whole app down — including the
    offline-only path that needs no backend at all."""
    out = _js("console.log(JSON.stringify(API_BASE));", head="""
      global.document.querySelector = () => { throw new Error('hostile DOM'); };
    """)
    assert out == "http://localhost:8000"


def test_api_base_is_no_longer_a_hardcoded_constant():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "const API_BASE = 'http://localhost:8000';" not in text


# --------------------------------------------------------------- 2/3. the container can deploy

def _dockerfile_cmd() -> str:
    """Just the CMD line. A first pass at these tests searched the whole file and passed cleanly
    when the migration step was deleted from CMD — because the word appears in the comment above
    it. Scoping to the actual instruction is the difference between testing the code and testing
    my own prose."""
    for line in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("CMD "):
            return line
    raise AssertionError("no CMD instruction found in the Dockerfile")


def test_dockerfile_runs_migrations_before_serving():
    """The gap: compose ran them in its own `command:`, which overrides CMD — so the covered path
    hid an uncovered one."""
    assert "alembic upgrade head" in _dockerfile_cmd()


def test_migrations_can_be_opted_out_for_a_separate_job():
    """Several cold-starting containers racing `alembic upgrade head` is safe in practice but not
    correct in principle — a deployment that runs migrations as a one-off job needs a way out."""
    assert "RUN_MIGRATIONS" in _dockerfile_cmd()


def test_dockerfile_listens_on_the_injected_port():
    """Cloud Run injects $PORT and routes to it. A hardcoded port means the container is up and
    nothing reaches it, which presents as a generic startup failure rather than a port mismatch."""
    cmd = _dockerfile_cmd()
    assert "${PORT:-8000}" in cmd, "uvicorn must bind the injected port, falling back to 8000"
    assert "--port 8000" not in cmd, "the port must not be hardcoded in the CMD"


def test_local_compose_behaviour_is_unchanged():
    """compose overrides CMD entirely, so local dev keeps its own migrate-then-reload command —
    this change must not have altered that."""
    compose = COMPOSE.read_text(encoding="utf-8")
    assert "alembic upgrade head" in compose
    assert "--reload" in compose, "local dev keeps hot reload; the image CMD must never add it"


def test_the_image_cmd_never_enables_reload():
    """--reload in a deployed image would fork a watcher per instance and serve from a source
    tree that never changes."""
    assert "--reload" not in _dockerfile_cmd()


# ------------------------------------------------------------------- 4. CORS fails visibly

def test_effective_cors_origins_are_logged_at_startup():
    """A CORS misconfiguration is the most confusing failure this backend has: the API is up,
    curl works, and the browser shows an opaque error with no server-side trace."""
    src = MAIN_PY.read_text(encoding="utf-8")
    assert "CORS allow_origins=%s" in src
    assert "cors_origin_list" in src


def test_the_cors_warning_names_the_deployment_case():
    """The default is localhost-only, so a real deployment that forgets CORS_ORIGINS hits exactly
    this — the message has to point at the fix, not just state the value."""
    src = MAIN_PY.read_text(encoding="utf-8")
    assert "CORS_ORIGINS" in src
    assert re.search(r"refused", src)
