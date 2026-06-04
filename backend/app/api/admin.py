"""Admin console endpoints: feature flags/settings, farmers & conversations views.

KB doc management lives in api/kb.py; analytics in api/metrics.py. All admin-only.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.api.schemas import SettingsIn
from app.db.base import get_db
from app.db.models import Conversation, Farmer, StaffUser
from app.services import settings as settings_svc

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/settings")
def get_settings(db: Session = Depends(get_db),
                 staff: StaffUser = Depends(require_staff("admin"))):
    return settings_svc.get_all(db)


@router.patch("/settings")
def patch_settings(body: SettingsIn, db: Session = Depends(get_db),
                   staff: StaffUser = Depends(require_staff("admin"))):
    updates = body.model_dump(exclude_none=True)
    result = settings_svc.set_many(db, updates, actor_id=staff.id, actor_role=staff.role)
    db.commit()
    return result


@router.get("/farmers")
def list_farmers(limit: int = 50, db: Session = Depends(get_db),
                 staff: StaffUser = Depends(require_staff("admin"))):
    rows = db.scalars(select(Farmer).order_by(Farmer.created_at.desc()).limit(limit))
    return [
        {"id": f.id, "phone": f.phone, "name": f.name, "district": f.district,
         "preferred_language": f.preferred_language, "created_via": f.created_via,
         "consent_data": f.consent_data}
        for f in rows
    ]


@router.get("/conversations")
def list_conversations(limit: int = 50, db: Session = Depends(get_db),
                       staff: StaffUser = Depends(require_staff("admin"))):
    rows = db.scalars(select(Conversation).order_by(Conversation.opened_at.desc()).limit(limit))
    out = []
    for c in rows:
        farmer = db.get(Farmer, c.farmer_id)
        out.append({"id": c.id, "channel": c.channel, "state": c.state,
                    "last_intent": c.last_intent,
                    "farmer_phone": farmer.phone if farmer else None})
    return out
