"""Extension-officer console endpoints — the human-in-the-loop queue."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.api.schemas import EscalationOut, ResolveIn
from app.db.base import get_db
from app.db.models import StaffUser
from app.services import escalation as escalation_svc

router = APIRouter(prefix="/escalations", tags=["escalations"])


def _scoped_district(staff: StaffUser, requested: str | None) -> str | None:
    if staff.role == "admin":
        return requested
    # Officers are limited to their own district scope.
    return staff.district_scope[0] if staff.district_scope else None


@router.get("", response_model=list[EscalationOut])
def list_escalations(status: str | None = "open", district: str | None = None,
                     db: Session = Depends(get_db),
                     staff: StaffUser = Depends(require_staff("extension_officer", "admin"))):
    return escalation_svc.list_open(
        db, status=status, district=_scoped_district(staff, district))


@router.post("/{esc_id}:claim", response_model=EscalationOut)
def claim(esc_id: str, db: Session = Depends(get_db),
          staff: StaffUser = Depends(require_staff("extension_officer", "admin"))):
    esc = escalation_svc.claim(db, esc_id, staff.id, staff.role)
    if not esc:
        raise HTTPException(409, "Cannot claim (not found or already claimed)")
    db.commit()
    return esc


@router.post("/{esc_id}:resolve", response_model=EscalationOut)
def resolve(esc_id: str, body: ResolveIn, db: Session = Depends(get_db),
            staff: StaffUser = Depends(require_staff("extension_officer", "admin"))):
    esc = escalation_svc.resolve(db, esc_id, staff.id, staff.role, body.note)
    if not esc:
        raise HTTPException(404, "Escalation not found")
    db.commit()
    return esc
