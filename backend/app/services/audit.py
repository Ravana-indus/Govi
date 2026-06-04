"""Audit logging for staff mutations (immutable trail)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AuditLog


def record(db: Session, *, actor_id: str | None, actor_role: str | None,
           action: str, entity: str, entity_id: str | None = None,
           detail: str | None = None) -> None:
    db.add(AuditLog(
        actor_id=actor_id, actor_role=actor_role, action=action,
        entity=entity, entity_id=entity_id, detail=detail,
    ))
    db.flush()
