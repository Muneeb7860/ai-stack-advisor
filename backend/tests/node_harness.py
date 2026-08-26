"""Run a generated JS harness under Node.

Exists because `subprocess.run(["node", "-e", script])` — which every JS-runtime test in this
suite used to call directly — cannot work on Linux for this project. The harnesses embed the
main <script> block extracted from index.html, which is several hundred KB, and Linux caps a
SINGLE argv entry at MAX_ARG_STRLEN (128 KiB, a separate limit from the much larger total
ARG_MAX). Passing the script as `-e`'s argument therefore fails with
`OSError: [Errno 7] Argument list too long` before Node ever starts.

macOS has no comparable per-argument cap, so all 23 affected tests passed locally and failed
the first time they ran on ubuntu-latest — found by adding .github/workflows/ci.yml and
installing Node there, exactly the class of bug the `node --version` step exists to stop from
hiding behind a skip.

Writing the script to a temp file and running `node <file>` has no size limit, and is what
scripts/*.py already do for the same reason.
"""
import json
import os
import subprocess
import tempfile


def run_node_script(script: str, timeout: int = 30) -> str:
    """Execute `script` under Node, returning stdout. Raises AssertionError on failure."""
    tmp = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
    try:
        tmp.write(script)
        tmp.close()
        proc = subprocess.run(
            ["node", tmp.name], capture_output=True, text=True, timeout=timeout
        )
        assert proc.returncode == 0, f"Node execution failed:\n{proc.stderr}"
        return proc.stdout
    finally:
        os.unlink(tmp.name)


def run_node_json(script: str, timeout: int = 30):
    """run_node_script() + json.loads() — the shape every caller in this suite wants."""
    return json.loads(run_node_script(script, timeout=timeout))
