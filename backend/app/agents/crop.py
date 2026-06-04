"""Crop Doctor agent.

Inputs: image bytes (+ optional symptom text), crop, location.
Logic: vision_classify -> candidate label(s) + confidence -> retrieve a
validated treatment doc (RAG, scoped to crop+disease, symptom text folded into
the query) -> assemble step-by-step, locally valid treatment with safety notes
and **citations** (every answer traces to a validated KnowledgeDoc).

Guardrails: confidence < admin-tunable threshold OR unusable image -> escalate,
ask for a clearer photo. Also escalate when confident but no citable treatment
doc exists. Always include a 'when to consult an officer' line.
"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.agents.schemas import Citation, CropAgentOutput
from app.core import guardrails
from app.gateway import get_gateway
from app.i18n import localize
from app.services import diagnosis as diag_svc
from app.services import kb_rag
from app.services import settings as settings_svc


def _parse_doc(body: str) -> tuple[list[str], list[str]]:
    """Pull 'Steps:' and 'Inputs:' sections from a treatment doc; fall back to
    sentence splitting for steps."""
    steps: list[str] = []
    inputs: list[str] = []
    section = None
    for raw in body.splitlines():
        line = raw.strip()
        low = line.lower()
        if low.startswith("steps:"):
            section = "steps"; continue
        if low.startswith("inputs:") or low.startswith("inputs needed:"):
            section = "inputs"; continue
        if not line:
            section = None; continue
        item = re.sub(r"^[-*\d.)\s]+", "", line).strip()
        if not item:
            continue
        if section == "steps":
            steps.append(item)
        elif section == "inputs":
            inputs.append(item)
    if not steps:  # fallback: first few sentences
        sentences = re.split(r"(?<=[.!?])\s+", body.strip())
        steps = [s.strip() for s in sentences if s.strip()][:4]
    return steps, inputs


def run(db: Session, *, farmer, image_bytes: bytes, image_url: str | None = None,
        crop_id: str | None = None, symptom_text: str | None = None,
        lang: str = "si") -> CropAgentOutput:
    vision = get_gateway().vision_classify(image_bytes, crop=crop_id)
    candidates = [{"label": l, "confidence": c} for l, c in (vision.candidates or [])]

    threshold = settings_svc.get(db, "crop_confidence_threshold")
    threshold = float(threshold) if threshold is not None else None
    escalate = guardrails.crop_should_escalate(
        vision.confidence, usable=vision.usable, threshold=threshold)
    reason = None
    treatment_doc = None
    citations: list[dict] = []

    # Confident & healthy -> reassure, no treatment, no escalation.
    if not escalate and vision.label == "healthy":
        case = diag_svc.create_case(
            db, farmer_id=farmer.id, image_url=image_url, label="healthy",
            confidence=vision.confidence, treatment_doc_id=None, escalated=False)
        return CropAgentOutput(
            label="healthy", confidence=vision.confidence, candidates=candidates,
            escalate=False, diagnosis_case_id=case.id,
            explanation_localized=localize("crop.healthy", lang), safety="")

    if not escalate:
        treatment_doc, citations = kb_rag.cited_treatment(
            db, label=vision.label, symptom_text=symptom_text,
            crop_id=crop_id, language=lang)
        if treatment_doc is None:
            escalate = True
            reason = f"No validated treatment doc for {vision.label}"
    else:
        reason = "low_confidence" if vision.usable else "unusable_image"

    case = diag_svc.create_case(
        db, farmer_id=farmer.id, image_url=image_url,
        label=None if not vision.usable else vision.label,
        confidence=vision.confidence,
        treatment_doc_id=treatment_doc.id if treatment_doc else None,
        escalated=escalate)

    if escalate:
        return CropAgentOutput(
            label=vision.label if vision.usable else None,
            confidence=vision.confidence, candidates=candidates, escalate=True,
            diagnosis_case_id=case.id,
            explanation_localized=localize("crop.escalate", lang),
            safety=localize("crop.safety", lang), escalate_reason=reason)

    steps, inputs = _parse_doc(treatment_doc.body)
    parts = [
        localize("crop.diagnosis", lang, label=vision.label.replace("_", " "),
                 confidence=int(vision.confidence * 100)),
        localize("crop.treatment_header", lang),
        *[f"• {s}" for s in steps],
    ]
    if inputs:
        parts.append(localize("crop.inputs_header", lang))
        parts.extend(f"• {i}" for i in inputs)
    parts.append(localize("crop.safety", lang))
    parts.append(localize("crop.consult_officer", lang))
    if citations:
        parts.append(localize("crop.source", lang, source=citations[0]["title"]))
    explanation = get_gateway().complete("\n".join(parts)).text

    return CropAgentOutput(
        label=vision.label, confidence=vision.confidence, candidates=candidates,
        treatment_steps=steps, inputs_needed=inputs,
        safety=localize("crop.safety", lang), escalate=False,
        diagnosis_case_id=case.id, treatment_doc_id=treatment_doc.id,
        citations=[Citation(**c) for c in citations],
        explanation_localized=explanation)
