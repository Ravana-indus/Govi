"""Core data model (Blueprint section 3).

PK = uuid (string for cross-dialect portability), created_at/updated_at on every
table via TimestampMixin. Enum-like fields are stored as String with the allowed
values documented inline; the service/schema layer validates them.

Mapped[] annotations use typing.Optional/List (not PEP 604 `X | None`) because
SQLAlchemy resolves these annotations at runtime and that syntax requires 3.10+.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Embedding, JSONList, PkMixin, TimestampMixin


class Farmer(Base, PkMixin, TimestampMixin):
    __tablename__ = "farmers"

    phone: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(128))
    preferred_language: Mapped[str] = mapped_column(String(2), default="si")  # si|ta|en
    gps_lat: Mapped[Optional[float]] = mapped_column(Float)
    gps_lng: Mapped[Optional[float]] = mapped_column(Float)
    district: Mapped[Optional[str]] = mapped_column(String(64))
    dsd: Mapped[Optional[str]] = mapped_column(String(64))            # divisional secretariat
    village: Mapped[Optional[str]] = mapped_column(String(128))
    farmer_org_id: Mapped[Optional[str]] = mapped_column(String(36))
    consent_data: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_ts: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_via: Mapped[str] = mapped_column(String(8), default="web")  # wa|tg|web|staff

    plots: Mapped[List["Plot"]] = relationship(back_populates="farmer")


class Plot(Base, PkMixin, TimestampMixin):
    __tablename__ = "plots"

    farmer_id: Mapped[str] = mapped_column(ForeignKey("farmers.id"), index=True)
    name: Mapped[Optional[str]] = mapped_column(String(128))
    area_value: Mapped[Optional[float]] = mapped_column(Float)
    area_unit: Mapped[Optional[str]] = mapped_column(String(16))  # acre|perch|ha
    soil_type: Mapped[Optional[str]] = mapped_column(String(64))
    irrigation_type: Mapped[Optional[str]] = mapped_column(String(64))
    gps_lat: Mapped[Optional[float]] = mapped_column(Float)
    gps_lng: Mapped[Optional[float]] = mapped_column(Float)

    farmer: Mapped[Farmer] = relationship(back_populates="plots")
    crops: Mapped[List["PlotCrop"]] = relationship(back_populates="plot")


class Crop(Base, PkMixin, TimestampMixin):
    __tablename__ = "crops"

    name_en: Mapped[str] = mapped_column(String(64))
    name_si: Mapped[Optional[str]] = mapped_column(String(64))
    name_ta: Mapped[Optional[str]] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(16))  # vegetable|paddy|tea|fruit|spice
    default_calendar_ref: Mapped[Optional[str]] = mapped_column(String(64))


class PlotCrop(Base, PkMixin, TimestampMixin):
    __tablename__ = "plot_crops"

    plot_id: Mapped[str] = mapped_column(ForeignKey("plots.id"), index=True)
    crop_id: Mapped[str] = mapped_column(ForeignKey("crops.id"), index=True)
    season: Mapped[str] = mapped_column(String(12))  # maha|yala|perennial
    planted_date: Mapped[Optional[date]] = mapped_column(Date)
    expected_harvest_date: Mapped[Optional[date]] = mapped_column(Date)
    stage: Mapped[Optional[str]] = mapped_column(String(32))

    plot: Mapped[Plot] = relationship(back_populates="crops")
    crop: Mapped[Crop] = relationship()


class Market(Base, PkMixin, TimestampMixin):
    __tablename__ = "markets"

    name: Mapped[str] = mapped_column(String(128))
    type: Mapped[str] = mapped_column(String(16))  # farmgate|wholesale|retail|DEC
    district: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    gps_lat: Mapped[Optional[float]] = mapped_column(Float)
    gps_lng: Mapped[Optional[float]] = mapped_column(Float)


class PriceRecord(Base, PkMixin, TimestampMixin):
    __tablename__ = "price_records"

    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), index=True)
    crop_id: Mapped[str] = mapped_column(ForeignKey("crops.id"), index=True)
    price_min: Mapped[float] = mapped_column(Float)
    price_max: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(8), default="kg")
    currency: Mapped[str] = mapped_column(String(8), default="LKR")
    observed_date: Mapped[date] = mapped_column(Date, index=True)
    source: Mapped[str] = mapped_column(String(8), default="staff")  # staff|feed|api
    entered_by: Mapped[Optional[str]] = mapped_column(ForeignKey("staff_users.id"))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    market: Mapped[Market] = relationship()
    crop: Mapped[Crop] = relationship()


class KnowledgeDoc(Base, PkMixin, TimestampMixin):
    __tablename__ = "knowledge_docs"

    title: Mapped[str] = mapped_column(String(256))
    body: Mapped[str] = mapped_column(Text)
    crop_id: Mapped[Optional[str]] = mapped_column(ForeignKey("crops.id"))
    topic: Mapped[str] = mapped_column(String(16))  # pest|disease|fertilizer|calendar|subsidy|general
    language: Mapped[str] = mapped_column(String(2), default="en")
    source: Mapped[Optional[str]] = mapped_column(String(256))
    validated_by: Mapped[Optional[str]] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft|validated|archived

    chunks: Mapped[List["KnowledgeChunk"]] = relationship(back_populates="doc")


class KnowledgeChunk(Base, PkMixin, TimestampMixin):
    __tablename__ = "knowledge_chunks"

    doc_id: Mapped[str] = mapped_column(ForeignKey("knowledge_docs.id"), index=True)
    chunk_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Optional[list]] = mapped_column(Embedding)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)

    doc: Mapped[KnowledgeDoc] = relationship(back_populates="chunks")


class Conversation(Base, PkMixin, TimestampMixin):
    __tablename__ = "conversations"

    farmer_id: Mapped[str] = mapped_column(ForeignKey("farmers.id"), index=True)
    channel: Mapped[str] = mapped_column(String(4))  # wa|tg|web
    state: Mapped[str] = mapped_column(String(32), default="open")
    last_intent: Mapped[Optional[str]] = mapped_column(String(32))
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    messages: Mapped[List["Message"]] = relationship(back_populates="conversation")


class Message(Base, PkMixin, TimestampMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    direction: Mapped[str] = mapped_column(String(3))   # in|out
    modality: Mapped[str] = mapped_column(String(8))    # text|voice|image
    content_text: Mapped[Optional[str]] = mapped_column(Text)
    media_url: Mapped[Optional[str]] = mapped_column(String(512))
    transcript: Mapped[Optional[str]] = mapped_column(Text)
    agent: Mapped[Optional[str]] = mapped_column(String(8))  # price|crop|router
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    tokens: Mapped[Optional[int]] = mapped_column(Integer)
    cost: Mapped[Optional[float]] = mapped_column(Float)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class DiagnosisCase(Base, PkMixin, TimestampMixin):
    __tablename__ = "diagnosis_cases"

    farmer_id: Mapped[str] = mapped_column(ForeignKey("farmers.id"), index=True)
    plot_crop_id: Mapped[Optional[str]] = mapped_column(ForeignKey("plot_crops.id"))
    image_url: Mapped[Optional[str]] = mapped_column(String(512))
    model_label: Mapped[Optional[str]] = mapped_column(String(64))
    model_confidence: Mapped[Optional[float]] = mapped_column(Float)
    treatment_doc_id: Mapped[Optional[str]] = mapped_column(ForeignKey("knowledge_docs.id"))
    status: Mapped[str] = mapped_column(String(20), default="auto_resolved")  # auto_resolved|escalated|officer_resolved
    outcome: Mapped[str] = mapped_column(String(8), default="unknown")  # saved|lost|unknown


class StaffUser(Base, PkMixin, TimestampMixin):
    __tablename__ = "staff_users"

    name: Mapped[str] = mapped_column(String(128))
    email: Mapped[Optional[str]] = mapped_column(String(128), unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(20))  # ground_staff|extension_officer|admin
    district_scope: Mapped[List[str]] = mapped_column(JSONList, default=list)
    password_hash: Mapped[Optional[str]] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(16), default="active")


class Escalation(Base, PkMixin, TimestampMixin):
    __tablename__ = "escalations"

    conversation_id: Mapped[Optional[str]] = mapped_column(ForeignKey("conversations.id"))
    farmer_id: Mapped[str] = mapped_column(ForeignKey("farmers.id"), index=True)
    type: Mapped[str] = mapped_column(String(8))  # price|crop|other
    reason: Mapped[Optional[str]] = mapped_column(Text)
    assigned_officer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("staff_users.id"))
    status: Mapped[str] = mapped_column(String(12), default="open")  # open|claimed|resolved
    ai_draft: Mapped[Optional[str]] = mapped_column(Text)  # assisted-mode: AI's proposed reply
    resolution_note: Mapped[Optional[str]] = mapped_column(Text)
    district: Mapped[Optional[str]] = mapped_column(String(64))
    sla_due: Mapped[Optional[datetime]] = mapped_column(DateTime)


class OutcomeLog(Base, PkMixin, TimestampMixin):
    """Powers the north-star metric: % advised -> acted -> outcome."""

    __tablename__ = "outcome_logs"

    farmer_id: Mapped[str] = mapped_column(ForeignKey("farmers.id"), index=True)
    interaction_ref: Mapped[Optional[str]] = mapped_column(String(64))
    recommended_action: Mapped[Optional[str]] = mapped_column(String(256))
    action_taken: Mapped[Optional[bool]] = mapped_column(Boolean)
    outcome_value: Mapped[Optional[float]] = mapped_column(Float)
    captured_via: Mapped[Optional[str]] = mapped_column(String(16))
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SystemSetting(Base, PkMixin, TimestampMixin):
    """Admin-tunable feature flags / settings (key/value).

    Examples: crop_confidence_threshold, assisted_mode. Read by the agent
    guardrails so admins can tune behavior without a redeploy."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)  # JSON-encoded scalar


class AuditLog(Base, PkMixin, TimestampMixin):
    """Immutable audit trail for staff mutations (price edits, KB changes, etc.)."""

    __tablename__ = "audit_logs"

    actor_id: Mapped[Optional[str]] = mapped_column(String(36))
    actor_role: Mapped[Optional[str]] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[Optional[str]] = mapped_column(String(36))
    detail: Mapped[Optional[str]] = mapped_column(Text)


# Composite indexes from the blueprint
Index(
    "ix_price_crop_market_date",
    PriceRecord.crop_id,
    PriceRecord.market_id,
    PriceRecord.observed_date.desc(),
)
Index("ix_escalation_status_district", Escalation.status, Escalation.district)
