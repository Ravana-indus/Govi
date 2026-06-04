"""Request/response models for the REST surface."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


# ---- Auth & onboarding ----
class OtpRequestIn(BaseModel):
    phone: str


class OtpRequestOut(BaseModel):
    sent: bool = True
    dev_otp: str | None = None  # only populated in dev (expose_otp_in_dev)


class OtpVerifyIn(BaseModel):
    phone: str
    code: str
    preferred_language: str | None = None


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    farmer_id: str | None = None
    role: str = "farmer"


class StaffLoginIn(BaseModel):
    email: str
    password: str


class PlotCropIn(BaseModel):
    crop_id: str
    season: str = "yala"
    stage: str | None = None


class OnboardIn(BaseModel):
    phone: str
    code: str  # verified OTP code
    preferred_language: str = "si"
    name: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None
    district: str | None = None
    dsd: str | None = None
    village: str | None = None
    crops: list[PlotCropIn] = Field(default_factory=list)
    consent: bool = False


class FarmerOut(BaseModel):
    id: str
    phone: str
    name: str | None = None
    preferred_language: str
    district: str | None = None
    dsd: str | None = None
    village: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None
    consent_data: bool
    created_via: str

    class Config:
        from_attributes = True


class FarmerPatchIn(BaseModel):
    name: str | None = None
    preferred_language: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None
    district: str | None = None
    dsd: str | None = None
    village: str | None = None


# ---- Conversation core ----
class IngestIn(BaseModel):
    channel: str = "web"
    external_user_id: str
    modality: str = "text"
    text: str | None = None
    media_url: str | None = None


class ReplyOut(BaseModel):
    conversation_id: str
    intent: str
    agent: str | None = None
    reply: str
    confidence: float | None = None
    escalation_id: str | None = None
    payload: dict | None = None
    transcript: str | None = None
    reply_media_url: str | None = None
    assisted: bool = False


# ---- Agents (direct) ----
class PriceAgentIn(BaseModel):
    crop: str | None = None
    crop_id: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None
    quantity: float | None = None
    lang: str = "si"


# ---- Prices / markets ----
class PriceIn(BaseModel):
    market_id: str
    crop_id: str
    price_min: float
    price_max: float
    observed_date: date
    unit: str = "kg"
    currency: str = "LKR"


class PricePatch(BaseModel):
    price_min: float | None = None
    price_max: float | None = None
    observed_date: date | None = None


class PriceOut(BaseModel):
    id: str
    market_id: str
    crop_id: str
    price_min: float
    price_max: float
    unit: str
    currency: str
    observed_date: date
    source: str

    class Config:
        from_attributes = True


class MarketIn(BaseModel):
    name: str
    type: str = "wholesale"
    district: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None


class MarketOut(BaseModel):
    id: str
    name: str
    type: str
    district: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None

    class Config:
        from_attributes = True


class BulkResult(BaseModel):
    created: int
    errors: list[str] = Field(default_factory=list)


# ---- Knowledge base ----
class KbDocIn(BaseModel):
    title: str
    body: str
    crop_id: str | None = None
    topic: str = "general"
    language: str = "en"
    source: str | None = None
    status: str = "draft"


class KbDocPatch(BaseModel):
    title: str | None = None
    body: str | None = None
    status: str | None = None
    validated_by: str | None = None


class KbDocOut(BaseModel):
    id: str
    title: str
    topic: str
    language: str
    status: str
    version: int

    class Config:
        from_attributes = True


# ---- Escalations ----
class EscalationOut(BaseModel):
    id: str
    farmer_id: str
    type: str
    reason: str | None = None
    status: str
    district: str | None = None
    assigned_officer_id: str | None = None
    ai_draft: str | None = None
    resolution_note: str | None = None

    class Config:
        from_attributes = True


class ResolveIn(BaseModel):
    note: str


class OutcomeIn(BaseModel):
    farmer_id: str
    recommended_action: str | None = None
    action_taken: bool = True
    outcome_value: float | None = None
    interaction_ref: str | None = None


# ---- Admin settings / feature flags ----
class SettingsIn(BaseModel):
    crop_confidence_threshold: float | None = None
    assisted_mode: bool | None = None
    price_stale_days: int | None = None
