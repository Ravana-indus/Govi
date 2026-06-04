"""Outcome logging — powers the north-star (% advised -> acted -> outcome).

Officers (or admins) log whether a farmer acted on advice and the result. The
extension-officer console calls this when resolving an escalation.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.api.schemas import OutcomeIn
from app.db.base import get_db
from app.db.models import OutcomeLog, StaffUser

router = APIRouter(prefix="/outcomes", tags=["outcomes"])


@router.post("", status_code=201)
def log_outcome(body: OutcomeIn, db: Session = Depends(get_db),
                staff: StaffUser = Depends(require_staff("extension_officer", "admin"))):
    row = OutcomeLog(
        farmer_id=body.farmer_id, interaction_ref=body.interaction_ref,
        recommended_action=body.recommended_action, action_taken=body.action_taken,
        outcome_value=body.outcome_value, captured_via="officer", ts=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "logged": True}
