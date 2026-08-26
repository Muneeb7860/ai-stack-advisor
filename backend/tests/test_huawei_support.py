"""
Huawei Cloud vendor support.

Scope, deliberately: the JS rule engine (index.html) gets full huaweiShop
detection + picks across cloud/gateway/containers/observability/DNS/CI-CD,
using the Huawei KB entries seeded in an earlier commit. The Python rule
engine (backend/app/rule_engine.py) only gets the huaweiShop *signal* added
for detection parity with the JS side (per this KB's existing zero-drift
discipline) — its pick-logic functions are NOT updated to branch on Huawei.
That's an explicit, known scope boundary, not an oversight: replicating
every one of the ~8 vendor-branching pick functions in a second language
is a materially larger task than seeding a signal, and nothing in this repo
currently exercises rule_engine.py's picks from a live request path the way
index.html's picks are exercised by the browser UI.
"""
import shutil
from pathlib import Path

import pytest

from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
NODE_AVAILABLE = shutil.which("node") is not None
requires_node = pytest.mark.skipif(
    not NODE_AVAILABLE, reason="Node.js runtime required for frontend JavaScript execution"
)

_HARNESS = r"""
const dummyEl = {
  style: {}, classList: { add: () => {}, remove: () => {}, toggle: () => {} },
  addEventListener: () => {}, setAttribute: () => {}, getAttribute: () => null,
};
global.window = { location: { search: "" }, addEventListener: () => {} };
global.document = {
  documentElement: dummyEl,
  querySelectorAll: () => [],
  getElementById: () => dummyEl,
  addEventListener: () => {},
};
global.navigator = { clipboard: {} };
global.fetch = () => Promise.resolve({ ok: false });

%(script)s

const s = detectSignals("We run everything on Huawei Cloud today and want to keep building on that footprint.");
const rec = computeRecommendations(s);

console.log(JSON.stringify({
  huaweiShop: s.huaweiShop,
  cloud: rec.cloud.v,
  gateway: rec.gw.v,
  containers: rec.containers.v,
  dns: rec.dns.v,
  observability: rec.obs.v,
  cicd: rec.cicd.v,
}));
"""


def _extract_main_script(source: str) -> str:
    parts = source.split("<script>")
    assert len(parts) >= 3, "expected at least 3 bare <script> blocks in index.html"
    return parts[2].split("</script>")[0]


@pytest.fixture(scope="module")
def huawei_scenario_result():
    source = INDEX_HTML.read_text(encoding="utf-8")
    script = _extract_main_script(source)
    node_script = _HARNESS % {"script": script}
    return run_node_json(node_script)


@requires_node
def test_huawei_signal_detected(huawei_scenario_result):
    assert huawei_scenario_result["huaweiShop"] is True


@requires_node
@pytest.mark.parametrize("field,expected_substring", [
    ("cloud", "Huawei Cloud"),
    ("gateway", "Huawei Cloud APIG"),
    ("containers", "Huawei Cloud CCE"),
    ("dns", "Huawei Cloud DNS"),
    ("observability", "Huawei Cloud"),
    ("cicd", "Huawei Cloud CodeArts"),
])
def test_huawei_picks_are_vendor_specific(huawei_scenario_result, field, expected_substring):
    assert expected_substring in huawei_scenario_result[field], (
        f"expected '{expected_substring}' in {field} pick, got: {huawei_scenario_result[field]!r}"
    )


def test_python_signal_parity_for_huawei():
    """The signal itself must exist in both engines — picks are explicitly not mirrored (see module docstring)."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
    from rule_engine import detect_signals

    s = detect_signals("We run everything on Huawei Cloud today.")
    assert s["huaweiShop"] is True
