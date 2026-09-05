"""README.md's numeric claims must match the code they describe.

`landing.html` has had a guard on its own numbers since the 933-vs-1,005 drift
(`test_landing_claims_are_current.py`). README.md — the file every new reader hits first, and
the one the repo's own agent contract points at — had none, and drifted much further: it
advertised 93 tests against an actual 1,233, 45 `pickX()` functions against 59, a 16-section
result view against 19, and an 11-domain knowledge base against 18. Every one of those
understated a product that had grown for a month underneath the description of it.

The asymmetry is the point: the marketing page was guarded and the front door was not.

Each figure here is derived from the thing it describes rather than restated, so the test cannot
agree with a stale README by construction. The test count gets a 5% band for the same reason the
landing guard does — pinning it exactly would make every test-adding PR also a README edit, which
is the kind of friction that gets resolved by deleting the guard. Everything else is exact: those
numbers only move when a feature is added or removed, which is precisely when the README should
be edited anyway.

Source text is read with full-line `//` comments stripped before any pattern is matched, per the
agent contract — several tests in this repo have previously matched their own explanatory prose,
including comments that existed to explain why a value was *not* used.
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
INDEX = ROOT / "index.html"


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def _claim(pattern: str) -> int:
    """Pull one number out of the README, failing loudly if the sentence carrying it is gone.

    A claim that has been deleted or reworded is not silently "no longer drifting" — it means
    this guard is now watching nothing, which is the failure mode it exists to prevent.
    """
    m = re.search(pattern, _readme())
    assert m, f"README.md no longer states this claim: {pattern}"
    return int(m.group(1).replace(",", ""))


def _index_source_without_line_comments() -> str:
    """`index.html` with whole-line `//` comments removed.

    Deliberately does NOT strip `/* */`: the file is 22k lines of mixed CSS and JS, and a
    non-greedy block-comment regex over it swallows real code the moment a `/*` or `*/`
    sequence appears inside a string or regex literal — which it does. Whole-line `//` removal
    is enough for every pattern below, all of which anchor to the start of a line.
    """
    return "\n".join(
        line for line in INDEX.read_text(encoding="utf-8").split("\n")
        if not line.lstrip().startswith("//")
    )


# ------------------------------------------------------------------ recommendation functions

def test_the_pick_function_count_matches_the_browser_engine():
    """Was 45 against an actual 59. The README describes the *browser* engine specifically
    ("runs entirely in your browser"), so this derives from index.html rather than from
    rule_engine.py — the two are held equal by test_engine_differential.py, not by this file."""
    claimed = _claim(r"`detectSignals\(\)` \+ (\d+)\s*\n?\s*`pickX\(\)` category functions")
    actual = len(re.findall(r"^function pick[A-Z]\w*", _index_source_without_line_comments(), re.M))
    assert claimed == actual, (
        f"README says {claimed} pickX() functions; index.html defines {actual}"
    )


# ------------------------------------------------------------------------------ stack cards

def test_the_stack_card_count_matches_the_category_map():
    """STACK_CARD_CATEGORY is the map every card-level feature (refine, ask, challenge) looks a
    card up in, so it is the honest definition of "how many stack cards are there"."""
    claimed = _claim(r"(\d+) stack cards")
    src = _index_source_without_line_comments()
    block = re.search(r"const STACK_CARD_CATEGORY = \{(.*?)\n\};", src, re.S)
    assert block, "STACK_CARD_CATEGORY was not found in index.html"
    titles = re.findall(r"'([^']+)'\s*:\s*'[^']+'", block.group(1))
    assert len(titles) == len(set(titles)), "STACK_CARD_CATEGORY has a duplicate card title"
    assert claimed == len(titles), (
        f"README says {claimed} stack cards; STACK_CARD_CATEGORY has {len(titles)}"
    )


# --------------------------------------------------------------------------- result sections

def test_the_section_count_matches_the_results_renderer():
    """Two separate sentences state this ("19 sections in all", "the exact same 19-section
    view"), and they drifted together at 16 — so both are checked against the same derivation
    rather than against each other."""
    src = _index_source_without_line_comments()
    ids = re.findall(r"^\s*sec\('([a-zA-Z]+)'", src, re.M)
    assert ids, "no sec('id', ...) calls found in index.html's results renderer"
    assert len(ids) == len(set(ids)), f"duplicate section id in index.html: {ids}"
    actual = len(ids)

    in_all = _claim(r"(\d+) sections in all")
    shared_view = _claim(r"(\d+)-section view")
    assert in_all == actual, f"README says {in_all} sections; index.html renders {actual}"
    assert shared_view == actual, (
        f"README's shared-view sentence says {shared_view} sections; index.html renders {actual}"
    )


# ------------------------------------------------------------------- knowledge-base domains

def test_the_knowledge_base_domain_count_matches_the_discovered_corpus():
    """app.retrieval discovers the corpus from disk rather than enumerating it, so DOC_FILES is
    the corpus — importing it is strictly better than re-globbing the directory here and getting
    the exclusion rules subtly wrong (00-INDEX is meta, the eval/prototype files are tooling)."""
    from app.retrieval import DOC_FILES

    claimed = _claim(r"(\d+)-domain use-case knowledge base")
    assert claimed == len(DOC_FILES), (
        f"README says {claimed} knowledge-base domains; app.retrieval discovers "
        f"{len(DOC_FILES)}: {DOC_FILES}"
    )


# ------------------------------------------------------------------------------- test count

def test_the_advertised_test_count_is_close_to_the_real_one():
    """A band, not an exact match — see the module docstring. 5% catches the 93-vs-1,233 gap this
    was written for (a 92% miss) many times over while tolerating a sprint's worth of new tests.

    Collects the whole suite, this file included, so the number in the README is the number a
    reader gets from `pytest --collect-only` with no caveat attached.
    """
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT / "backend", capture_output=True, text=True, timeout=300,
    )
    m = re.search(r"(\d+) tests? collected", proc.stdout)
    if not m:
        pytest.skip(f"could not determine the collected test count: {proc.stdout[-300:]}")
    actual = int(m.group(1))
    claimed = _claim(r"([\d,]+) tests — see backend/README\.md")
    drift = abs(claimed - actual) / actual
    assert drift <= 0.05, (
        f"README advertises {claimed} tests; the suite collects {actual} ({drift:.1%} adrift). "
        f"Update the figure in README.md's project-structure block."
    )
