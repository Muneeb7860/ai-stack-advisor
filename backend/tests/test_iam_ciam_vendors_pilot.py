"""Pilot vendor-catalog expansion: adds Clerk and WorkOS to the IAM category as a small,
verified first pass at closing the "closed-world catalog" gap named in the pasted 2026 SaaS
Architectural Decision Playbook and the earlier "brutal feedback" critique — most modern
developer-facing CIAM/embedded-auth vendors (Clerk, WorkOS, Supabase Auth, ...) aren't in the
catalog at all, only legacy workforce IdPs (Okta, Entra, Ping, ...).

Scope, per explicit user decision: ONE category (IAM), a handful of vendors (2), verified and
tested — not a wholesale catalog rewrite. Both are added as their own distinct 'CIAM / Embedded
Auth (not a workforce IdP)' category within IAM_VENDORS/IAM_VENDORS, not conflated with the
existing workforce-SSO rows (Okta/Entra/Ping/...) — they solve a genuinely different problem
(app-user auth for your own product, not employee/workforce login) and every new pick's `why`
explicitly says so, to avoid steering someone who actually needs workforce SSO toward the wrong
tool.

Pricing figures were verified live against clerk.com/pricing and workos.com/pricing (not
invented or copied from the pasted playbook) before being written into either engine.

Asserted against BOTH engines (rule_engine.py and index.html's JS twin).
"""
import re
import shutil
from pathlib import Path

import pytest

from app.rule_engine import IAM_VENDORS, detect_signals, recommend_stack
from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)


def _main_script() -> str:
    return INDEX_HTML.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]


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


def _js(expr_body: str):
    return run_node_json(_STUBS + _main_script() + "\n" + expr_body)


# ------------------------------------------------------------------------- explicit mentions

def test_clerk_mention_is_detected_and_recommended():
    s = detect_signals("We're already using Clerk for auth in our Next.js app.")
    assert s["clerkMentioned"] is True
    rec = recommend_stack("We're already using Clerk for auth in our Next.js app.")["recommendations"]
    assert rec["iam"]["v"] == "Clerk"


def test_workos_mention_is_detected_and_recommended():
    s = detect_signals("We use WorkOS to handle enterprise SSO for our B2B customers.")
    assert s["workosMentioned"] is True
    rec = recommend_stack("We use WorkOS to handle enterprise SSO for our B2B customers.")["recommendations"]
    assert rec["iam"]["v"] == "WorkOS"


def test_clerk_and_workos_picks_disclaim_they_are_not_a_workforce_idp():
    """The whole point of scoping these as a separate category is that a reader must not
    confuse "we use Clerk" with "we have workforce SSO solved" — the `why` text must say so
    explicitly, not just imply it via the category label."""
    rec = recommend_stack("We're already using Clerk for our app's login.")["recommendations"]
    assert "workforce" in rec["iam"]["why"].lower()

    rec2 = recommend_stack("We use WorkOS for enterprise SSO.")["recommendations"]
    assert "workforce" in rec2["iam"]["why"].lower()


# ------------------------------------------------------------------------- vendor catalog data

def test_clerk_and_workos_are_in_the_iam_vendor_catalog_with_real_pricing():
    ids = {v["id"] for v in IAM_VENDORS}
    assert "clerk" in ids
    assert "workos" in ids

    clerk = next(v for v in IAM_VENDORS if v["id"] == "clerk")
    workos = next(v for v in IAM_VENDORS if v["id"] == "workos")

    # Not fabricated placeholder pricing — real, verified figures.
    assert "50,000 MRU" in clerk["pricing"]
    assert "$25/mo" in clerk["pricing"]
    assert "1M MAU" in workos["pricing"]
    assert "$125/connection" in workos["pricing"]

    # Both are clearly scoped away from the workforce-IdP rows (Okta/Entra/Ping/...).
    assert "not a workforce IdP" in clerk["cat"]
    assert "not a workforce IdP" in workos["cat"]


def test_iam_vendor_catalog_still_has_no_duplicate_ids():
    ids = [v["id"] for v in IAM_VENDORS]
    assert len(ids) == len(set(ids))


# ------------------------------------------------------------------------------------ JS parity

@requires_node
def test_js_clerk_mention_is_detected_and_recommended():
    text = "We're already using Clerk for auth in our Next.js app."
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({text!r}));
      console.log(JSON.stringify({{ v: rec.iam.v, why: rec.iam.why }}));
    """)
    assert out["v"] == "Clerk"
    assert "workforce" in out["why"].lower()


@requires_node
def test_js_workos_mention_is_detected_and_recommended():
    text = "We use WorkOS to handle enterprise SSO for our B2B customers."
    out = _js(f"""
      const rec = computeRecommendations(detectSignals({text!r}));
      console.log(JSON.stringify({{ v: rec.iam.v, why: rec.iam.why }}));
    """)
    assert out["v"] == "WorkOS"
    assert "workforce" in out["why"].lower()


@requires_node
def test_js_iam_vendors_catalog_has_clerk_and_workos():
    out = _js("console.log(JSON.stringify(IAM_VENDORS.map(v => v.id)));")
    assert "clerk" in out
    assert "workos" in out


@requires_node
def test_js_and_python_iam_vendor_ids_match():
    py_ids = sorted(v["id"] for v in IAM_VENDORS)
    js_ids = sorted(_js("console.log(JSON.stringify(IAM_VENDORS.map(v => v.id)));"))
    assert py_ids == js_ids
