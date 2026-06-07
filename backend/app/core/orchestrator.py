"""Orchestrator / Router.

Input: a normalized message (text / voice / image) + resolved farmer + light
conversation memory. Steps: transcribe voice -> image routes to Crop Doctor ->
else route intent -> attach context -> dispatch -> guardrails -> persist every
turn -> localize -> (synthesize a voice reply for voice inbound) -> return.
Low-confidence turns create an Escalation. When assisted mode is on, agent
answers are held for an officer to front (Wizard-of-Oz pilot).

Channel-agnostic: imports no channel SDK.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from app.agents import advisory as advisory_agent
from app.agents import crop as crop_agent
from app.agents import price as price_agent
from app.core import guardrails, memory, router
from app.core.intent import detect_language_command
from app.db.models import Conversation, Farmer, Message
from app.gateway import get_gateway
from app.i18n import localize
from app.services import escalation as escalation_svc
from app.services import farmer as farmer_svc
from app.services import media as media_svc
from app.services import settings as settings_svc


@dataclass
class Reply:
    conversation_id: str
    intent: str
    agent: str | None
    reply: str
    confidence: float | None
    escalation_id: str | None
    payload: dict | None
    transcript: str | None = None
    reply_media_url: str | None = None
    assisted: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _persist(db: Session, conv: Conversation, *, direction: str, modality: str,
             text: str | None, media_url: str | None = None, transcript: str | None = None,
             agent: str | None = None, confidence: float | None = None) -> None:
    db.add(Message(
        conversation_id=conv.id, direction=direction, modality=modality,
        content_text=text, media_url=media_url, transcript=transcript,
        agent=agent, confidence=confidence,
    ))
    db.flush()


def _recent_farmer_context(conversation_id: str) -> str:
    history = memory.get_history(conversation_id)
    turns = [
        turn["text"] for turn in history[-6:]
        if turn.get("role") == "farmer" and turn.get("text")
    ]
    return " ".join(turns)


def handle(db: Session, *, farmer: Farmer, channel: str, modality: str = "text",
           text: str | None = None, media_url: str | None = None,
           media_bytes: bytes | None = None) -> Reply:
    lang = farmer.preferred_language or "si"
    conv = farmer_svc.open_conversation(db, farmer, channel)
    previous_intent = conv.last_intent
    gw = get_gateway()

    # --- Voice inbound: transcribe to text, route on the transcript ---
    transcript = None
    if modality == "voice" and media_bytes:
        tr = gw.transcribe(media_bytes, lang)
        transcript = tr.text
        text = transcript or text

    clean_text = guardrails.scrub_user_text(text)
    has_image = modality == "image" and bool(media_bytes)
    image_bytes = media_bytes if has_image else None

    _persist(db, conv, direction="in", modality=modality, text=text,
             media_url=media_url, transcript=transcript)
    if clean_text:
        memory.append_turn(conv.id, "farmer", clean_text)

    requested_lang = detect_language_command(clean_text)
    if requested_lang:
        lang = requested_lang
    context_text = _recent_farmer_context(conv.id)
    decision = router.route(
        db,
        text=clean_text,
        modality=modality,
        has_image=has_image,
        previous_intent=previous_intent,
        context_text=context_text,
    )
    intent = decision.intent
    crop_id = decision.crop_id
    price_text = decision.crop_text or clean_text
    agent_name: str | None = None
    confidence: float | None = None
    escalation_id: str | None = None
    payload: dict | None = None
    assisted = False

    if intent == "language" and requested_lang:
        farmer.preferred_language = requested_lang
        lang = requested_lang
        reply = localize("language.updated", lang)
    elif intent == "greeting":
        reply = localize("greeting", lang)
    elif intent == "price":
        agent_name = "price"
        out = price_agent.run(db, lang=lang, crop_id=crop_id, crop_text=price_text,
                              gps_lat=farmer.gps_lat, gps_lng=farmer.gps_lng)
        reply, confidence, payload = out.explanation_localized, out.confidence, out.model_dump()
        if out.escalate:
            esc = escalation_svc.create(db, farmer_id=farmer.id, type="price",
                                        reason=out.escalate_reason or "price_unavailable",
                                        conversation_id=conv.id)
            escalation_id = esc.id
    elif intent == "crop_health":
        agent_name = "crop"
        if not (image_bytes or media_url):
            reply = localize("crop.ask_photo", lang)
        else:
            out = crop_agent.run(db, farmer=farmer, image_bytes=image_bytes or b"",
                                 image_url=media_url, symptom_text=clean_text, lang=lang)
            reply, confidence, payload = out.explanation_localized, out.confidence, out.model_dump()
            if out.escalate:
                esc = escalation_svc.create(db, farmer_id=farmer.id, type="crop",
                                            reason=out.escalate_reason or "low_confidence",
                                            conversation_id=conv.id)
                escalation_id = esc.id
    elif intent == "farming_tip":
        agent_name = "advisory"
        out = advisory_agent.run(
            db,
            lang=lang,
            question=clean_text or "",
            crop_id=crop_id,
            context_text=context_text,
        )
        reply = out["reply"]
        confidence = out["confidence"]
        payload = out["payload"]
    else:
        reply = localize("other.agriculture_only", lang)

    # --- Assisted mode: hold a confident agent answer for an officer to front ---
    if (agent_name in ("price", "crop", "advisory") and escalation_id is None
            and bool(settings_svc.get(db, "assisted_mode"))):
        esc = escalation_svc.create(
            db, farmer_id=farmer.id, type="assisted",
            reason=f"assisted_review:{intent}", conversation_id=conv.id, ai_draft=reply)
        escalation_id = esc.id
        assisted = True
        reply = localize("assisted.holding", lang)

    conv.last_intent = intent
    _persist(db, conv, direction="out", modality="text", text=reply,
             agent=agent_name, confidence=confidence)
    memory.append_turn(conv.id, "assistant", reply)

    # --- Voice inbound -> synthesize a spoken reply too ---
    reply_media_url = None
    if modality == "voice":
        reply_media_url = media_svc.save_bytes(gw.speak(reply, lang), ext="ogg")

    db.commit()
    return Reply(
        conversation_id=conv.id, intent=intent, agent=agent_name, reply=reply,
        confidence=confidence, escalation_id=escalation_id, payload=payload,
        transcript=transcript, reply_media_url=reply_media_url, assisted=assisted,
    )
