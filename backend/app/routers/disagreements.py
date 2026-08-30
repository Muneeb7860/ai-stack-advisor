"""Disagreement capture — the "Challenge This Pick" widget (see docs/challenge-this-pick-spec.md
and BRD Section 7's "disagreement rate" success metric, which had zero instrumentation anywhere
before this).

Deliberately thin, same posture as share.py: this router does NOT call an LLM. It exists purely
to persist a user's stated disagreement with one specific pick, scoped to an existing Analysis.
Client-side capture (localStorage, index.html's saveChallengeEntry()) always happens regardless
of whether this endpoint is reachable — see the module docstring in index.html's
getChallengeLog()/saveChallengeEntry() for the fire-and-forget contract this endpoint is the
backend half of.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db

router = APIRouter(prefix="/api/analyses", tags=["disagreements"])


@router.post(
    "/{analysis_id}/disagreements",
    response_model=schemas.DisagreementResponse,
    status_code=201,
)
def create_disagreement(analysis_id: str, payload: schemas.DisagreementRequest, db: Session = Depends(get_db)):
    analysis = db.query(models.Analysis).filter_by(id=analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    row = models.Disagreement(analysis_id=analysis.id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
