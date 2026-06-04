"""Diagnosis case service (Crop Doctor record-keeping)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import DiagnosisCase


def create_case(db: Session, *, farmer_id: str, image_url: str | None,
                label: str | None, confidence: float | None,
                treatment_doc_id: str | None, escalated: bool) -> DiagnosisCase:
    case = DiagnosisCase(
        farmer_id=farmer_id,
        image_url=image_url,
        model_label=label,
        model_confidence=confidence,
        treatment_doc_id=treatment_doc_id,
        status="escalated" if escalated else "auto_resolved",
        outcome="unknown",
    )
    db.add(case)
    db.flush()
    return case
