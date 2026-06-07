"""Structured message router for the conversational orchestrator."""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re

from sqlalchemy.orm import Session

from app.core.intent import detect_language_command
from app.gateway import get_gateway
from app.services import price as price_svc

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RouterDecision:
    intent: str
    agent: str | None
    confidence: float
    crop_id: str | None = None
    crop_text: str | None = None
    market_ids: list[str] = field(default_factory=list)
    reason: str = ""


_GREETINGS = (
    "hi", "hello", "hey", "good morning", "good evening",
    "ආයුබෝ", "හලෝ", "සුබ", "வணக்கம்", "ஹலோ",
)

_PRICE_TERMS = (
    "price", "prices", "pricing", "rate", "rates", "sell", "market",
    "wholesale", "kg", "dambulla", "manning", "colombo", "nuwara eliya",
    "keppetipola", "මිල", "අගය", "විකුණ", "වෙළඳ",
    "விலை", "சந்தை", "விற்க", "கிலோ",
)

_CROP_HEALTH_TERMS = (
    "disease", "sick", "pest", "blight", "spot", "spots", "leaf", "leaves",
    "rot", "fungus", "yellow", "wilt", "wilting", "insect", "curl",
    "රෝග", "පළිබෝධ", "කොළ", "පැළ", "දිලීර",
    "நோய்", "பூச்சி", "இலை", "செடி", "பூஞ்சை",
)

_FARMING_TERMS = (
    "water", "watering", "irrigate", "irrigation", "fertilizer", "fertiliser",
    "compost", "soil", "seed", "seedling", "plant", "plants", "planting",
    "harvest", "prune", "pruning", "nursery", "field", "farm", "crop",
    "tomato", "onion", "chili", "chilli", "rice", "beetroot",
    "වතුර", "පොහොර", "බීජ", "වගා", "අස්වැන්න", "පස",
    "நீர்", "உரம்", "விதை", "பயிர்", "அறுவடை", "மண்",
)


def _norm(text: str | None) -> str:
    return " ".join((text or "").lower().strip().split())


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    for term in terms:
        term = term.lower()
        if term.isascii():
            if re.search(rf"\b{re.escape(term)}\b", text):
                return True
        elif term in text:
            return True
    return False


def _is_greeting(text: str) -> bool:
    return any(text == term or text.startswith(term) for term in _GREETINGS)


def _fallback_route_with_llm(text: str) -> RouterDecision:
    prompt = (
        "Classify this farmer message as exactly one token: farming_tip or other.\n"
        "Use farming_tip only for agriculture, crop cultivation, irrigation, "
        "soil, fertilizer, harvest, pest prevention, or farm planning questions.\n"
        f"Message: {text}\n"
        "Token:"
    )
    try:
        raw = get_gateway().complete(prompt, max_tokens=4).text.strip().lower()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Router LLM fallback failed: %s", exc)
        raw = ""
    if raw == "farming_tip":
        return RouterDecision(
            intent="farming_tip", agent="advisory", confidence=0.55,
            crop_text=text, reason="llm_fallback",
        )
    return RouterDecision(intent="other", agent=None, confidence=0.4, reason="fallback")


def route(
    db: Session,
    *,
    text: str | None,
    modality: str,
    has_image: bool,
    previous_intent: str | None,
    context_text: str = "",
) -> RouterDecision:
    clean = _norm(text)
    context = _norm(context_text)
    crop = price_svc.resolve_crop(db, clean)
    markets = price_svc.resolve_markets(db, clean)

    if has_image or modality == "image":
        return RouterDecision(
            intent="crop_health", agent="crop", confidence=1.0,
            crop_id=crop.id if crop else None, crop_text=text, reason="image",
        )

    if detect_language_command(clean):
        return RouterDecision(intent="language", agent=None, confidence=1.0, reason="language")

    if clean and (_has_any(clean, _PRICE_TERMS) or markets):
        return RouterDecision(
            intent="price", agent="price", confidence=0.95,
            crop_id=crop.id if crop else None, crop_text=text,
            market_ids=[m.id for m in markets], reason="price_terms",
        )

    if previous_intent == "price":
        context_crop = price_svc.resolve_crop(db, context)
        context_markets = price_svc.resolve_markets(db, context)
        if crop or markets or context_crop or context_markets:
            chosen_crop = crop or context_crop
            return RouterDecision(
                intent="price", agent="price", confidence=0.82,
                crop_id=chosen_crop.id if chosen_crop else None,
                crop_text=context_text or text,
                market_ids=[m.id for m in (markets or context_markets)],
                reason="price_followup",
            )

    if clean and _has_any(clean, _CROP_HEALTH_TERMS):
        return RouterDecision(
            intent="crop_health", agent="crop", confidence=0.9,
            crop_id=crop.id if crop else None, crop_text=text, reason="crop_health_terms",
        )

    if clean and _is_greeting(clean):
        return RouterDecision(intent="greeting", agent=None, confidence=0.9, reason="greeting")

    if clean and _has_any(clean, _FARMING_TERMS):
        return RouterDecision(
            intent="farming_tip", agent="advisory", confidence=0.7,
            crop_id=crop.id if crop else None, crop_text=text, reason="farming_terms",
        )

    if clean:
        return _fallback_route_with_llm(clean)

    return RouterDecision(intent="other", agent=None, confidence=0.5, reason="empty")
