"""Harness Readiness feedback capture — see
docs/harness-engineering/HARNESS_FEEDBACK_SCOPE.md.

Deliberately thin, same posture as share.py and disagreements.py: this router does NOT call an
LLM. It exists purely to persist what a user thought of their completed harness self-audit.

Unlike disagreements.py there is no {analysis_id} path segment and no existence check, because
a harness audit has no Analysis row and must not create one (see the HarnessFeedback model
docstring for why). The route is therefore top-level rather than nested under /api/analyses.

The frontend half is best-effort and fire-and-forget: index.html's submitHarnessFeedback() never
blocks the UI or surfaces an error if this endpoint is unreachable, which is the normal case for
anyone running index.html as a local file. Feedback reaching the backend is a bonus, never a
precondition for the audit working.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db

router = APIRouter(prefix="/api/harness-feedback", tags=["harness-feedback"])


@router.post("", response_model=schemas.HarnessFeedbackResponse, status_code=201)
def create_harness_feedback(payload: schemas.HarnessFeedbackRequest, db: Session = Depends(get_db)):
    row = models.HarnessFeedback(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
