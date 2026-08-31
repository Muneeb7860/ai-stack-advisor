"""Harness Readiness feedback capture — implements
docs/harness-engineering/HARNESS_FEEDBACK_SCOPE.md.

Why this endpoint exists at all: the harness results screen previously had no feedback
affordance of any kind (attachRefineUI only targets #stack .stack-card and #tradeoffs
.tradeoff-card), and harness audits never call ensureAnalysisId, so the existing disagreement
endpoint could not fire from that screen either. Everything harness-related was localStorage-only
— nothing had ever left a user's browser. With the product free-and-collecting-feedback for six
months, that made feedback capture the blocking gap, ahead of promoting the mode.

Standalone table by design (no FK to analyses) — see the HarnessFeedback model docstring.

Uses the same TestClient(app) pattern as test_disagreements.py, against conftest.py's in-memory
SQLite fixture — no Postgres or docker-compose needed.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

VALID = {
    "total": 8,
    "band": "Real harness exists",
    "answers": {"system_of_record": 2, "tools": 2, "verification": 2, "guardrails": 1, "observability": 1},
    "helpful": True,
    "comment": "The fix-order list was the useful part.",
}


def test_valid_submission_returns_201_and_the_stored_row():
    r = client.post("/api/harness-feedback", json=VALID)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["total"] == 8
    assert body["band"] == "Real harness exists"
    assert body["helpful"] is True
    assert body["comment"] == "The fix-order list was the useful part."
    assert body["answers"]["guardrails"] == 1
    assert body["id"] and body["created_at"]


def test_comment_is_optional():
    """Deliberate: requiring prose is what collapses response rates. A one-click `helpful` from
    many users is a better dataset than prose from almost nobody."""
    payload = {**VALID}
    payload.pop("comment")
    r = client.post("/api/harness-feedback", json=payload)
    assert r.status_code == 201, r.text
    assert r.json()["comment"] is None


def test_negative_feedback_is_capturable():
    r = client.post("/api/harness-feedback", json={**VALID, "helpful": False, "comment": "Too generic."})
    assert r.status_code == 201
    assert r.json()["helpful"] is False


def test_answers_are_stored_so_a_comment_has_its_score_context():
    """The comment is nearly useless without the score that produced it — "this wasn't useful"
    from a team scoring 14/15 means something completely different than from one scoring 2/15."""
    r = client.post("/api/harness-feedback", json={
        **VALID, "total": 15, "band": "Mature",
        "answers": {"system_of_record": 3, "tools": 3, "verification": 3, "guardrails": 3, "observability": 3},
    })
    assert r.status_code == 201
    assert r.json()["answers"] == {
        "system_of_record": 3, "tools": 3, "verification": 3, "guardrails": 3, "observability": 3,
    }


def test_submissions_are_append_only_not_overwritten():
    """Same rationale as Disagreement/RefinementResult: feedback is a fact about a moment.
    A second submission must not replace the first."""
    from app import models
    from app.db import SessionLocal

    before = SessionLocal().query(models.HarnessFeedback).count()
    client.post("/api/harness-feedback", json={**VALID, "comment": "first"})
    client.post("/api/harness-feedback", json={**VALID, "comment": "second"})
    after = SessionLocal().query(models.HarnessFeedback).count()
    assert after == before + 2


def test_score_out_of_range_is_rejected():
    """The audit is scored /15 — a total outside that can only be a client bug or a forged
    payload, and silently storing it would poison any aggregate read off this table."""
    assert client.post("/api/harness-feedback", json={**VALID, "total": 16}).status_code == 422
    assert client.post("/api/harness-feedback", json={**VALID, "total": -1}).status_code == 422


def test_helpful_is_required():
    """The one field that will reliably have an n — it must not be silently defaulted."""
    payload = {**VALID}
    payload.pop("helpful")
    assert client.post("/api/harness-feedback", json=payload).status_code == 422


def test_no_update_or_delete_route_exists():
    """Append-only is enforced by the absence of these routes, not by convention. If someone adds
    one later, this test is the thing that makes them justify it."""
    assert client.put("/api/harness-feedback", json=VALID).status_code == 405
    assert client.delete("/api/harness-feedback").status_code == 405


def test_endpoint_does_not_require_an_analysis_id():
    """Structural assertion: a harness audit has no Analysis row and must not create one, so
    unlike /api/analyses/{id}/disagreements this route takes no analysis path segment."""
    from app.routers.harness_feedback import router
    assert router.prefix == "/api/harness-feedback"
    assert "analyses" not in router.prefix


# ---------------------------------------------------------------------- frontend (index.html)

import shutil
from pathlib import Path

import pytest

from tests.node_harness import run_node_json

INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="Node.js runtime required for frontend JavaScript execution"
)

_STUBS = r"""
const dummyEl = { style:{}, classList:{add(){},remove(){},toggle(){}}, addEventListener(){},
  setAttribute(){}, getAttribute:()=>null, appendChild(){}, removeChild(){}, click(){}, focus(){},
  querySelector:()=>null, querySelectorAll:()=>[], innerHTML:'', textContent:'', value:'' };
global.window = { location:{search:''}, addEventListener(){}, matchMedia:()=>({matches:false,addEventListener(){}}) };
global.document = { documentElement:dummyEl, body:dummyEl, querySelector:()=>dummyEl,
  querySelectorAll:()=>[], getElementById:()=>dummyEl, createElement:()=>dummyEl, addEventListener(){} };
global.navigator = { clipboard:{} };
global.localStorage = { getItem:()=>null, setItem(){}, removeItem(){} };
global.URL = { createObjectURL:()=>'', revokeObjectURL(){} };
"""


def _main_script() -> str:
    return INDEX_HTML.read_text(encoding="utf-8").split("<script>")[2].split("</script>")[0]


def _js(body: str):
    return run_node_json(_STUBS + _main_script() + "\n" + body)


@requires_node
def test_submit_never_throws_when_the_backend_is_unreachable():
    """The realistic case for anyone running index.html as a local file. The audit must not be
    degraded by the absence of infrastructure the user never asked for."""
    out = _js("""
      global.fetch = () => Promise.reject(new Error('ECONNREFUSED'));
      haAnswers = {system_of_record:1, tools:1, verification:1, guardrails:1, observability:1};
      haSetFeedbackHelpful(true);
      submitHarnessFeedback().then(
        () => console.log(JSON.stringify({threw: false})),
        (e) => console.log(JSON.stringify({threw: true, msg: String(e)}))
      );
    """)
    assert out["threw"] is False


@requires_node
def test_submit_is_a_no_op_until_a_helpful_choice_is_made():
    """Guards the disabled-button contract at the logic level, not just the DOM attribute."""
    out = _js("""
      let called = false;
      global.fetch = () => { called = true; return Promise.resolve({ok:true}); };
      haFeedbackHelpful = null;
      haAnswers = {system_of_record:1, tools:1, verification:1, guardrails:1, observability:1};
      Promise.resolve(submitHarnessFeedback()).then(() => console.log(JSON.stringify({called})));
    """)
    assert out["called"] is False


@requires_node
def test_submitted_payload_carries_the_score_and_answers_not_just_the_comment():
    out = _js("""
      let body = null;
      global.fetch = (url, opts) => { body = JSON.parse(opts.body); return Promise.resolve({ok:true}); };
      haAnswers = {system_of_record:3, tools:2, verification:1, guardrails:0, observability:2};
      haSetFeedbackHelpful(false);
      Promise.resolve(submitHarnessFeedback()).then(() => console.log(JSON.stringify(body)));
    """)
    assert out["total"] == 8
    assert out["helpful"] is False
    assert out["answers"]["guardrails"] == 0
    assert out["band"]


def test_disclosure_text_is_present_next_to_the_button():
    """Regression lock: silently removing the "what gets sent" line would turn an explicit,
    disclosed exchange into undisclosed telemetry. That's a privacy regression, not a copy edit."""
    text = INDEX_HTML.read_text(encoding="utf-8")
    start = text.index('id="haFeedbackCard"')
    section = text[start:start + 2500]
    assert "Sends your score" in section
    assert "no email, no identifier" in section


def test_feedback_is_never_sent_without_an_explicit_button_press():
    """No automatic/background telemetry: the only fetch to the feedback endpoint must live
    inside submitHarnessFeedback, which is only reachable from the Send button."""
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert text.count("/api/harness-feedback") == 1
    start = text.index("async function submitHarnessFeedback()")
    end = text.index("function getAnalysisHistory()")
    assert "/api/harness-feedback" in text[start:end]
