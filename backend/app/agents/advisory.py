"""General farming advice agent.

This agent is for cultivation help that is not market pricing and not crop
disease diagnosis. It can use a general LLM answer, but always labels the answer
as general guidance and gives the farmer the hotline for confirmation.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.gateway import get_gateway
from app.i18n import localize
from app.services import kb_rag

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are Govi, a Sri Lankan farming assistant. Answer only agriculture "
    "cultivation questions. Keep the answer concise for chat. Do not invent "
    "market prices. Do not give exact pesticide dosage or guaranteed outcomes "
    "unless the provided context explicitly supports it."
)


def _warning(lang: str) -> str:
    return localize("advisory.warning", lang)


def _with_warning(text: str, lang: str) -> str:
    base = (text or "").strip() or localize("advisory.fallback", lang)
    warning = _warning(lang)
    if "0117929494" in base:
        return base
    return f"{base}\n\n{warning}"


def _kb_context(db: Session, *, question: str, crop_id: str | None, lang: str) -> str:
    hits = kb_rag.retrieve(db, question, crop_id=crop_id, language=lang, k=2)
    if not hits and lang != "en":
        hits = kb_rag.retrieve(db, question, crop_id=crop_id, language="en", k=2)
    snippets = [chunk.chunk_text for chunk, _score in hits]
    return "\n\n".join(snippets)


def run(
    db: Session,
    *,
    lang: str,
    question: str,
    crop_id: str | None = None,
    context_text: str = "",
) -> dict:
    kb_context = _kb_context(db, question=question, crop_id=crop_id, lang=lang)
    prompt = (
        f"Recent farmer context:\n{context_text or '-'}\n\n"
        f"Validated knowledge context:\n{kb_context or '-'}\n\n"
        f"Farmer question:\n{question}\n\n"
        "Answer:"
    )
    try:
        text = get_gateway().complete(prompt, system=_SYSTEM, max_tokens=220).text
    except Exception as exc:  # noqa: BLE001
        logger.warning("Advisory agent failed: %s", exc)
        text = localize("advisory.fallback", lang)
    return {
        "agent": "advisory",
        "reply": _with_warning(text, lang),
        "confidence": 0.65,
        "payload": {"source": "general_guidance", "has_kb_context": bool(kb_context)},
    }
