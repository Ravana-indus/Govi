"""Analytics — north-star and basic usage/SLA."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.db.base import get_db
from app.db.models import Conversation, Escalation, Message, OutcomeLog, StaffUser

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _compute_northstar(db: Session) -> dict:
    advised = db.scalar(select(func.count()).select_from(OutcomeLog)) or 0
    acted = db.scalar(
        select(func.count()).select_from(OutcomeLog)
        .where(OutcomeLog.action_taken.is_(True))) or 0
    outcome = db.scalar(
        select(func.count()).select_from(OutcomeLog)
        .where(OutcomeLog.action_taken.is_(True),
               OutcomeLog.outcome_value.isnot(None))) or 0
    return {
        "advised": advised, "acted": acted, "saw_outcome": outcome,
        "acted_pct": round(100 * acted / advised, 1) if advised else 0.0,
        "outcome_pct": round(100 * outcome / advised, 1) if advised else 0.0,
    }


@router.get("/northstar")
def northstar(db: Session = Depends(get_db),
              staff: StaffUser = Depends(require_staff("admin"))):
    """% of advised farmers who took action and saw an outcome."""
    return _compute_northstar(db)


@router.get("/usage")
def usage(db: Session = Depends(get_db),
          staff: StaffUser = Depends(require_staff("admin"))):
    return {
        "conversations": db.scalar(select(func.count()).select_from(Conversation)) or 0,
        "messages": db.scalar(select(func.count()).select_from(Message)) or 0,
        "open_escalations": db.scalar(
            select(func.count()).select_from(Escalation)
            .where(Escalation.status == "open")) or 0,
        "total_cost": db.scalar(select(func.coalesce(func.sum(Message.cost), 0.0))) or 0.0,
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db),
              staff: StaffUser = Depends(require_staff("admin"))):
    """Consolidated pilot dashboard: north-star + usage + breakdowns + SLA."""
    by_intent = dict(db.execute(
        select(Conversation.last_intent, func.count())
        .group_by(Conversation.last_intent)).all())
    esc_by_status = dict(db.execute(
        select(Escalation.status, func.count()).group_by(Escalation.status)).all())
    sla_overdue = db.scalar(
        select(func.count()).select_from(Escalation)
        .where(Escalation.status != "resolved", Escalation.sla_due < datetime.utcnow())) or 0
    return {
        "northstar": _compute_northstar(db),
        "by_intent": {str(k): v for k, v in by_intent.items()},
        "escalations_by_status": {str(k): v for k, v in esc_by_status.items()},
        "sla_overdue": sla_overdue,
    }
