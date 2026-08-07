"""Share-link persistence — v2's FIRST milestone (PRD FR-28, DDD Section 3.3 "Sharing Context").

Deliberately thin: this router does NOT call an LLM and does NOT touch the rule-engine logic.
It exists purely to store an Analysis snapshot and hand back a slug. Keeping it first means v2
gets real, working persistence before taking on any LLM-refinement complexity.
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db

router = APIRouter(prefix="/api/analyses", tags=["analyses"])

SLUG_BYTES = 6  # ~8 url-safe chars — plenty of keyspace for a v1-scale share-link feature


def _generate_unique_slug(db: Session) -> str:
    for _ in range(5):
        candidate = secrets.token_urlsafe(SLUG_BYTES)
        exists = db.query(models.Analysis).filter_by(share_slug=candidate).first()
        if not exists:
            return candidate
    # Astronomically unlikely with 5 retries at this keyspace size, but fail loudly rather
    # than silently returning a colliding slug.
    raise HTTPException(status_code=500, detail="Could not generate a unique share slug — retry.")


@router.post("", response_model=schemas.AnalysisOut, status_code=201)
def create_analysis(payload: schemas.AnalysisCreate, db: Session = Depends(get_db)):
    """Persist a completed v1 analysis. Not shared yet — share_slug is null until the user
    explicitly opts in via POST /api/analyses/{id}/share (ERD: sharing is opt-in per analysis,
    never automatic)."""
    row = models.Analysis(
        requirement_text=payload.requirement_text,
        signals=payload.signals,
        recommendations=payload.recommendations,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/{analysis_id}/share", response_model=schemas.ShareLinkOut)
def create_share_link(analysis_id: str, db: Session = Depends(get_db)):
    row = db.query(models.Analysis).filter_by(id=analysis_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if not row.share_slug:
        row.share_slug = _generate_unique_slug(db)
        db.commit()
        db.refresh(row)
    return schemas.ShareLinkOut(share_slug=row.share_slug, share_path=f"/s/{row.share_slug}")


@router.get("/shared/{slug}", response_model=schemas.AnalysisOut)
def get_shared_analysis(slug: str, db: Session = Depends(get_db)):
    """Public, unauthenticated, read-only — this is the ENTIRE access-control model for shared
    analyses by design (ERD "Deliberately Excluded": no accounts, no auth on this route). Don't
    add auth here without first updating the ERD/PRD — that would be a real scope change."""
    row = db.query(models.Analysis).filter_by(share_slug=slug).first()
    if not row:
        raise HTTPException(status_code=404, detail="No analysis found for this share link")
    return row
