"""landing.html's numeric claims must match the codebase they describe.

That page says of itself that "every number below is a real, currently-shipping count in the
codebase — not a roadmap claim", which makes a stale number worse there than it would be anywhere
else on the site.

Two had drifted. It advertised 933 passing tests against an actual 1002, and 53 recommendation
functions against an actual 58. The pre-existing guard on the test count asserted only `>= 900`,
which is precisely why the drift went unnoticed: the number was free to fall behind by any amount
without ever failing, and the assertion still looked like coverage.

So these derive each figure from the thing it describes and compare with a tolerance tight enough
to notice. The test count gets a small band rather than an exact match, because pinning it exactly
means every PR that adds a test also has to edit the landing page, which is the kind of friction
that gets solved by deleting the test. A 5% band still catches "a hundred tests behind" while
tolerating "three tests ahead".
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LANDING = ROOT / "landing.html"
RULE_ENGINE = ROOT / "backend" / "app" / "rule_engine.py"
INDEX = ROOT / "index.html"


def _landing() -> str:
    return LANDING.read_text(encoding="utf-8")


def _claim(pattern: str) -> int:
    m = re.search(pattern, _landing())
    assert m, f"the landing page no longer states this claim: {pattern}"
    return int(m.group(1))


# --------------------------------------------------------------------------- catalogued techs

def test_the_technology_count_matches_the_embedded_knowledge_base():
    """This one was accurate and stays asserted, so it cannot quietly become the stale one."""
    claimed = _claim(r"(\d+) cataloged technologies")
    block = re.search(r'id="stackKbData"[^>]*>(.*?)</script>', INDEX.read_text(encoding="utf-8"), re.S)
    assert block, "the embedded knowledge-base block was not found"
    import json
    actual = len(json.loads(block.group(1))["technologies"])
    assert claimed == actual, f"landing says {claimed} technologies; the knowledge base has {actual}"


# ------------------------------------------------------------------- recommendation functions

def test_the_recommendation_function_count_matches_the_rule_engine():
    """Was 53 against an actual 58 — the engine gained categories (agent framework, inference
    serving, real-time analytics, LLM observability, GitOps CD) and the page kept the old figure,
    understating the product."""
    claimed = _claim(r"(\d+) recommendation functions")
    actual = len(re.findall(r"^def pick_\w+", RULE_ENGINE.read_text(encoding="utf-8"), re.M))
    assert claimed == actual, (
        f"landing says {claimed} recommendation functions; rule_engine.py defines {actual} pick_*"
    )


# -------------------------------------------------------------------------------- test count

def test_the_advertised_test_count_is_close_to_the_real_one():
    """Deliberately a band, not an exact match: an exact figure would make every test-adding PR
    also a landing-page edit. 5% is tight enough to catch real drift — the 933-vs-1002 gap this
    was written for is 6.9% — while tolerating a handful of new tests."""
    claimed = _claim(r"(\d+) passing regression tests")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "--ignore", str(Path(__file__).resolve())],
        cwd=ROOT / "backend", capture_output=True, text=True, timeout=300,
    )
    m = re.search(r"(\d+) tests? collected", proc.stdout)
    if not m:
        pytest.skip(f"could not determine the collected test count: {proc.stdout[-300:]}")
    actual = int(m.group(1))
    drift = abs(claimed - actual) / actual
    assert drift <= 0.05, (
        f"landing advertises {claimed} tests; the suite collects {actual} "
        f"({drift:.1%} adrift). Update the figure on landing.html."
    )
