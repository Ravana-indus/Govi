"""Escalation service: the human-in-the-loop queue."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Escalation, Farmer
from app.services import audit


def create(db: Session, *, farmer_id: str, type: str, reason: str,
           conversation_id: str | None = None, ai_draft: str | None = None,
           sla_hours: int = 24) -> Escalation:
    farmer = db.get(Farmer, farmer_id)
    esc = Escalation(
        farmer_id=farmer_id,
        conversation_id=conversation_id,
        type=type,
        reason=reason,
        ai_draft=ai_draft,
        status="open",
        district=farmer.district if farmer else None,
        sla_due=datetime.utcnow() + timedelta(hours=sla_hours),
    )
    db.add(esc)
    db.flush()
    return esc


def list_open(db: Session, *, status: str | None = None,
              district: str | None = None) -> list[Escalation]:
    stmt = select(Escalation)
    if status:
        stmt = stmt.where(Escalation.status == status)
    if district:
        stmt = stmt.where(Escalation.district == district)
    stmt = stmt.order_by(Escalation.sla_due.asc())
    return list(db.scalars(stmt))


def claim(db: Session, esc_id: str, officer_id: str, officer_role: str) -> Escalation | None:
    esc = db.get(Escalation, esc_id)
    if not esc or esc.status != "open":
        return None
    esc.status = "claimed"
    esc.assigned_officer_id = officer_id
    audit.record(db, actor_id=officer_id, actor_role=officer_role,
                 action="claim", entity="escalation", entity_id=esc.id)
    db.flush()
    return esc


def resolve(db: Session, esc_id: str, officer_id: str, officer_role: str,
            note: str) -> Escalation | None:
    esc = db.get(Escalation, esc_id)
    if not esc:
        return None
    esc.status = "resolved"
    esc.resolution_note = note
    esc.assigned_officer_id = esc.assigned_officer_id or officer_id
    audit.record(db, actor_id=officer_id, actor_role=officer_role,
                 action="resolve", entity="escalation", entity_id=esc.id, detail=note)
    db.flush()
    return esc
