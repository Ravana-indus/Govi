"""Agent output contracts (Blueprint section 4).

These Pydantic models ARE the contract. Every agent returns one; contract tests
assert the shape. Channels/portals consume these regardless of transport.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class PriceMarketOption(BaseModel):
    name: str
    type: str | None = None
    price_min: float
    price_max: float
    unit: str = "kg"
    currency: str = "LKR"
    net_after_transport: float
    distance_km: float | None = None
    days_old: int = 0


class PriceAgentOutput(BaseModel):
    agent: str = "price"
    crop: str | None = None
    markets: list[PriceMarketOption] = Field(default_factory=list)
    trend: str = "flat"  # rising | flat | falling
    recommendation: str = "hold"  # sell_now | hold | go_to:<market>
    confidence: float = 0.0
    explanation_localized: str = ""
    escalate: bool = False
    escalate_reason: str | None = None


class Citation(BaseModel):
    doc_id: str
    title: str
    source: str | None = None
    score: float | None = None


class CropAgentOutput(BaseModel):
    agent: str = "crop"
    label: str | None = None
    confidence: float = 0.0
    candidates: list[dict] = Field(default_factory=list)  # [{label, confidence}]
    treatment_steps: list[str] = Field(default_factory=list)
    inputs_needed: list[str] = Field(default_factory=list)
    safety: str = ""
    escalate: bool = False
    diagnosis_case_id: str | None = None
    treatment_doc_id: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    explanation_localized: str = ""
    escalate_reason: str | None = None
