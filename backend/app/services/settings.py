"""System settings / feature flags service.

Stored as JSON-encoded key/value rows so scalars (float, bool) round-trip.
Falls back to config defaults when a key hasn't been overridden by an admin.
"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings as cfg
from app.db.models import SystemSetting
from app.services import audit

# Admin-tunable keys and their defaults (sourced from env/config).
DEFAULTS: dict[str, object] = {
    "crop_confidence_threshold": cfg.crop_confidence_threshold,
    "assisted_mode": False,
    "price_stale_days": cfg.price_stale_days,
}


def get_all(db: Session) -> dict:
    stored = {s.key: json.loads(s.value) for s in db.scalars(select(SystemSetting))}
    return {**DEFAULTS, **stored}


def get(db: Session, key: str):
    row = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if row is not None:
        return json.loads(row.value)
    return DEFAULTS.get(key)


def set_many(db: Session, updates: dict, *, actor_id: str | None = None,
             actor_role: str | None = None) -> dict:
    for key, value in updates.items():
        if key not in DEFAULTS:
            continue  # ignore unknown keys
        row = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
        if row:
            row.value = json.dumps(value)
        else:
            db.add(SystemSetting(key=key, value=json.dumps(value)))
        audit.record(db, actor_id=actor_id, actor_role=actor_role,
                     action="update", entity="setting", entity_id=key,
                     detail=json.dumps(value))
    db.flush()
    return get_all(db)
