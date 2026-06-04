"""Farmer service: identity resolution, creation, profile, plots."""
from __future__ import annotations

from datetime import datetime

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Conversation, DiagnosisCase, Escalation, Farmer, Message, OutcomeLog,
    Plot, PlotCrop,
)
from app.services import audit


def get_by_phone(db: Session, phone: str) -> Farmer | None:
    return db.scalar(select(Farmer).where(Farmer.phone == phone))


def get(db: Session, farmer_id: str) -> Farmer | None:
    return db.get(Farmer, farmer_id)


def resolve_or_create(db: Session, *, phone: str, created_via: str = "web",
                      preferred_language: str | None = None) -> Farmer:
    """Phone is identity. Re-engagement recognizes an existing farmer; no
    re-onboarding."""
    farmer = get_by_phone(db, phone)
    if farmer:
        return farmer
    farmer = Farmer(
        phone=phone,
        created_via=created_via,
        preferred_language=preferred_language or "si",
        status="active",
    )
    db.add(farmer)
    db.flush()
    return farmer


def update_profile(db: Session, farmer: Farmer, **fields) -> Farmer:
    allowed = {
        "name", "preferred_language", "gps_lat", "gps_lng",
        "district", "dsd", "village", "farmer_org_id",
    }
    for k, v in fields.items():
        if k in allowed and v is not None:
            setattr(farmer, k, v)
    db.flush()
    return farmer


def give_consent(db: Session, farmer: Farmer) -> Farmer:
    farmer.consent_data = True
    farmer.consent_ts = datetime.utcnow()
    db.flush()
    return farmer


def add_plot(db: Session, farmer: Farmer, *, name=None, area_value=None,
             area_unit=None, crops: list[dict] | None = None) -> Plot:
    plot = Plot(
        farmer_id=farmer.id, name=name, area_value=area_value, area_unit=area_unit,
        gps_lat=farmer.gps_lat, gps_lng=farmer.gps_lng,
    )
    db.add(plot)
    db.flush()
    for c in crops or []:
        db.add(PlotCrop(
            plot_id=plot.id, crop_id=c["crop_id"], season=c.get("season", "yala"),
            stage=c.get("stage"),
        ))
    db.flush()
    return plot


def export_data(db: Session, farmer: Farmer) -> dict:
    """PDPA data-access request: everything we hold about this farmer."""
    convs = list(db.scalars(select(Conversation).where(Conversation.farmer_id == farmer.id)))
    conv_ids = [c.id for c in convs]
    msgs = list(db.scalars(select(Message).where(Message.conversation_id.in_(conv_ids)))) if conv_ids else []
    plots = list(db.scalars(select(Plot).where(Plot.farmer_id == farmer.id)))
    return {
        "farmer": {
            "id": farmer.id, "phone": farmer.phone, "name": farmer.name,
            "preferred_language": farmer.preferred_language, "district": farmer.district,
            "dsd": farmer.dsd, "village": farmer.village,
            "gps": [farmer.gps_lat, farmer.gps_lng], "consent_data": farmer.consent_data,
            "consent_ts": str(farmer.consent_ts) if farmer.consent_ts else None,
            "created_via": farmer.created_via,
        },
        "plots": [{"id": p.id, "name": p.name, "area_value": p.area_value,
                   "area_unit": p.area_unit} for p in plots],
        "conversations": [{"id": c.id, "channel": c.channel, "last_intent": c.last_intent} for c in convs],
        "messages": [{"direction": m.direction, "modality": m.modality,
                      "text": m.content_text, "transcript": m.transcript,
                      "agent": m.agent} for m in msgs],
        "diagnosis_cases": [{"id": d.id, "label": d.model_label, "status": d.status}
                            for d in db.scalars(select(DiagnosisCase).where(DiagnosisCase.farmer_id == farmer.id))],
        "outcomes": [{"recommended_action": o.recommended_action, "action_taken": o.action_taken,
                      "outcome_value": o.outcome_value}
                     for o in db.scalars(select(OutcomeLog).where(OutcomeLog.farmer_id == farmer.id))],
    }


def erase(db: Session, farmer: Farmer) -> None:
    """PDPA right-to-erasure: anonymize PII, keep anonymized/aggregated rows."""
    convs = list(db.scalars(select(Conversation).where(Conversation.farmer_id == farmer.id)))
    conv_ids = [c.id for c in convs]
    if conv_ids:
        for m in db.scalars(select(Message).where(Message.conversation_id.in_(conv_ids))):
            m.content_text = None
            m.transcript = None
            m.media_url = None
    for d in db.scalars(select(DiagnosisCase).where(DiagnosisCase.farmer_id == farmer.id)):
        d.image_url = None
    # Scrub the farmer record itself.
    farmer.phone = f"erased:{uuid.uuid4().hex[:12]}"
    farmer.name = None
    farmer.gps_lat = farmer.gps_lng = None
    farmer.village = None
    farmer.consent_data = False
    farmer.status = "erased"
    audit.record(db, actor_id=farmer.id, actor_role="farmer",
                 action="erase", entity="farmer", entity_id=farmer.id,
                 detail="PDPA erasure")
    db.flush()


def open_conversation(db: Session, farmer: Farmer, channel: str) -> Conversation:
    """Reuse the farmer's open conversation on a channel, else open one."""
    conv = db.scalar(
        select(Conversation)
        .where(Conversation.farmer_id == farmer.id,
               Conversation.channel == channel,
               Conversation.state == "open")
        .order_by(Conversation.opened_at.desc())
    )
    if conv:
        return conv
    conv = Conversation(farmer_id=farmer.id, channel=channel, state="open")
    db.add(conv)
    db.flush()
    return conv
