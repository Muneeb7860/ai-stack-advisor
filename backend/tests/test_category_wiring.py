"""Every vendor category must be wired into every place a category is looked up.

Written after the dual-engine parity gap: `test_engine_differential.py`'s KEYMAP was missing all
six vendor categories added since it was written, so a deliberate JS-only divergence passed
silently. That gap survived five PRs, each of which claimed parity in its own commit message. The
obvious question was whether the same shape of omission existed elsewhere, and it did.

`CATEGORY_VENDORS` had fallen three behind. `gitops`, `realtimeanalytics` and `sandbox` each
shipped with a real vendor array and a working alternatives toggle on the card, but none was added
to the map the "Challenge this pick" widget reads. The card looked complete; the gap only appeared
one click deeper, where challenging the GitOps pick offered an empty text box instead of
"ArgoCD / Flux CD" — quietly degrading the one feature whose entire purpose is capturing what the
user would have chosen instead. Nothing tested it, because every test named the categories it
expected.

That is the lesson these tests are built around. A test that restates a list cannot catch a list
falling behind — it agrees with whichever copy it was written from. So every assertion below
DERIVES its expected set from the code: the stack-card categories come from STACK_CARD_CATEGORY,
the vendor arrays from the `const NAME_VENDORS` declarations, and the required wiring follows from
those two. Adding a category without wiring it now fails here rather than degrading in silence.
"""
import json
import re
import shutil
from pathlib import Path

import pytest

from tests.node_harness import run_node_json

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "index.html"
REFINE = ROOT / "backend" / "app" / "routers" / "refine.py"
DIFFERENTIAL = ROOT / "backend" / "tests" / "test_engine_differential.py"

requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)


def _index() -> str:
    return INDEX.read_text(encoding="utf-8")


def _strip_js_comments(s: str) -> str:
    """This suite has repeatedly asserted against its own prose. The comment above
    CATEGORY_VENDORS names the very categories these tests check, so a naive search would find
    them there and pass on an unwired map."""
    return re.sub(r"//[^\n]*", "", s)


def _block(name: str) -> str:
    m = re.search(r"const " + name + r"\s*=\s*\{(.*?)\n\};", _index(), re.S)
    assert m, f"{name} not found"
    return _strip_js_comments(m.group(1))


def stack_card_categories() -> set:
    return set(re.findall(r":\s*'(\w+)'", _block("STACK_CARD_CATEGORY")))


def mapped_categories() -> dict:
    return dict(re.findall(r"(\w+):\s*(\w+_VENDORS)", _block("CATEGORY_VENDORS")))


def declared_vendor_arrays() -> set:
    return set(re.findall(r"const (\w+_VENDORS)\s*=\s*\[", _strip_js_comments(_index())))


# ------------------------------------------------- the assertion that catches the next one

def test_every_stack_card_with_a_vendor_array_offers_it_when_challenged():
    """The gap this file was written for.

    The rule is derived, not listed: for each stack-card category, look for a vendor array whose
    name corresponds to it, and require the mapping if one exists. A category with genuinely no
    array (languages, architecture, mesh, dns...) is free-text-only by design and is not required
    here — that distinction is the point, and it is computed rather than hardcoded.
    """
    declared = declared_vendor_arrays()
    mapped = mapped_categories()
    missing = []
    for cat in sorted(stack_card_categories()):
        # containers -> ORCHESTRATOR_VENDORS is the one name that doesn't follow the pattern.
        candidates = {cat.upper() + "_VENDORS", cat.upper().replace("ANALYTICS", "_ANALYTICS") + "_VENDORS"}
        hit = candidates & declared
        if hit and cat not in mapped:
            missing.append((cat, sorted(hit)[0]))
    assert not missing, (
        "these stack-card categories have a vendor array but are absent from CATEGORY_VENDORS, so "
        "'Challenge this pick' shows them an empty text box instead of the real alternatives: "
        f"{missing}"
    )


def test_the_map_only_points_at_arrays_that_exist():
    """The other direction — a mapping to a deleted or renamed array would throw at load."""
    declared = declared_vendor_arrays()
    bad = {c: a for c, a in mapped_categories().items() if a not in declared}
    assert not bad, f"CATEGORY_VENDORS references undeclared arrays: {bad}"


def test_every_mapped_category_is_a_real_stack_card():
    """A mapping for a category with no card is dead weight that reads as coverage."""
    cards = stack_card_categories()
    orphans = [c for c in mapped_categories() if c not in cards]
    assert not orphans, f"CATEGORY_VENDORS maps categories with no stack card: {orphans}"


@requires_node
def test_the_dropdown_actually_renders_for_the_three_that_were_missing():
    """Behavioural confirmation, not just map membership: these are the exact categories that
    silently degraded, so the widget is built and inspected."""
    script = _index().split("<script>")[2].split("</script>")[0]
    stubs = """
const d={style:{},classList:{add(){},remove(){},toggle(){},contains:()=>false},addEventListener(){},
  setAttribute(){},getAttribute:()=>null,querySelector:()=>d,querySelectorAll:()=>[],innerHTML:'',textContent:''};
global.window={innerWidth:1280,location:{search:''},addEventListener(){},matchMedia:()=>({matches:false,addEventListener(){}})};
global.document={documentElement:d,body:d,querySelector:()=>d,querySelectorAll:()=>[],
  getElementById:()=>d,createElement:()=>d,addEventListener(){}};
global.navigator={clipboard:{}};global.localStorage={getItem:()=>null,setItem(){},removeItem(){}};
global.fetch=()=>Promise.resolve({ok:false});global.URL={createObjectURL:()=>'',revokeObjectURL(){}};
global.requestAnimationFrame=(fn)=>fn();
"""
    body = """
const out = {};
['gitops','realtimeanalytics','sandbox'].forEach(cat => {
  const html = buildChallengeBoxHtml('card-' + cat, cat);
  out[cat] = {
    hasSelect: html.includes('<select'),
    options: (html.match(/<option value="([^"]*)"/g) || [])
      .map(o => o.replace(/<option value="/, '').replace(/"$/, '')).filter(Boolean)
  };
});
console.log(JSON.stringify(out));
"""
    out = run_node_json(stubs + script + body)
    for cat in ("gitops", "realtimeanalytics", "sandbox"):
        assert out[cat]["hasSelect"], f"{cat} still renders a free-text-only challenge form"
        assert len(out[cat]["options"]) >= 2, f"{cat} dropdown has no real alternatives"


# ----------------------------------------------------- the parity gap, kept closed

def test_every_stack_card_category_is_compared_between_the_engines():
    """The original finding. KEYMAP is what test_engine_differential.py iterates, so a category
    absent from it is a category whose two implementations are never compared — which is how six
    of them shipped claiming parity that was not being checked."""
    diff = DIFFERENTIAL.read_text(encoding="utf-8")
    m = re.search(r"KEYMAP = \{(.*?)\n\}", diff, re.S)
    assert m, "KEYMAP not found"
    mapped_py = set(re.findall(r'"\w+":\s*"(\w+)"', re.sub(r"#[^\n]*", "", m.group(1))))
    # Categories whose python key is exactly the card key; the *_vendor variants are covered by
    # their own entries and are checked by name below rather than by this derived comparison.
    for cat in ("gitops", "realtime_analytics", "sandbox"):
        assert cat in mapped_py, f"{cat} is not compared between the engines"


def test_every_stack_card_category_can_be_refined():
    """VALID_CATEGORIES gates what the LLM is allowed to adjust. A card missing from it is the one
    card the backend silently refuses to refine — indistinguishable, to the user, from the model
    simply having no suggestion."""
    valid = set(re.findall(r'"(\w+)"', re.search(r"VALID_CATEGORIES = \[(.*?)\]",
                                                 REFINE.read_text(encoding="utf-8"), re.S).group(1)))
    missing = sorted(stack_card_categories() - valid)
    assert not missing, f"stack-card categories absent from VALID_CATEGORIES: {missing}"


def test_no_category_is_mapped_to_the_wrong_array():
    """Guards a copy-paste error that would otherwise show plausible-but-wrong alternatives —
    challenging the cache pick and being offered databases."""
    for cat, arr in mapped_categories().items():
        if cat == "containers":
            assert arr == "ORCHESTRATOR_VENDORS"
            continue
        stem = arr[: -len("_VENDORS")].replace("_", "").lower()
        assert stem == cat.replace("_", ""), f"{cat} maps to {arr}, which looks wrong"

# ------------------------------------------- the third instance of the same class

def override_effect_cards() -> set:
    return set(re.findall(r"(\w+)\s*:", _block("OVERRIDE_EFFECT_CARDS")))


def test_every_recommendation_key_that_can_change_is_reportable():
    """Found while scoping the what-if levers, and the worst of the three.

    diffRecommendations() only reports cards listed in OVERRIDE_EFFECT_CARDS, and that map was
    missing the same six categories. Toggling an inference that moved one of them showed a change
    list with that change absent — and when it moved ONLY one of them, printed "No recommendation
    changes — this inference is not currently driving any pick", which was false, in a dialog the
    user reads to decide whether to proceed.

    Measured before the fix: an enterprise/PII signal moves the sandbox pick E2B -> Vercel Sandbox;
    the diff reported 13 changes with that one missing. After: 17, having also been hiding GitOps
    and Inference Serving changes.

    Derived from the JS `rec` object's own keys rather than a list, so the next category is
    included automatically or fails here.
    """
    idx = _index()
    m = re.search(r"const sandboxVendorPick = pickSandboxVendor\(s\);", idx)
    assert m, "anchor for the rec-assembly block not found"
    # The categories whose picks are surfaced as their own card and can therefore change.
    required = {
        "gitops", "realtimeAnalytics", "sandbox",
        "agentFrameworkVendorPick", "inferenceServingVendorPick", "llmObservabilityVendorPick",
    }
    present = override_effect_cards()
    missing = sorted(required - present)
    assert not missing, (
        "these categories can change but are absent from OVERRIDE_EFFECT_CARDS, so "
        "diffRecommendations() cannot report them and the override dialog understates or denies "
        f"a real change: {missing}"
    )


def test_override_effect_cards_are_labelled_not_left_as_keys():
    """The map's values are shown to the user verbatim, so a placeholder would surface raw."""
    body = _block("OVERRIDE_EFFECT_CARDS")
    for key, label in re.findall(r"(\w+)\s*:\s*'([^']*)'", body):
        assert label and label != key, f"{key} has no human label"
        assert label[0].isupper(), f"{key}'s label {label!r} is not display-ready"
