"""Channel webhooks (Phase 3 scaffold).

Inbound platform payload -> adapter.normalize -> orchestrator -> adapter.render.
WhatsApp needs verify-token + signature checks and a public HTTPS host (cannot run
in a no-inbound sandbox). Telegram can also long-poll without a webhook for dev.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.channels.telegram import TelegramAdapter
from app.channels.whatsapp import WhatsAppAdapter
from app.config import settings
from app.core import orchestrator
from app.db.base import get_db
from app.services import farmer as farmer_svc

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
_wa = WhatsAppAdapter()
_tg = TelegramAdapter()


def _dispatch(db: Session, normalized, channel: str) -> dict:
    if not normalized.external_user_id:
        return {"ok": True}
    farmer = farmer_svc.resolve_or_create(
        db, phone=normalized.external_user_id, created_via=channel)
    db.commit()
    reply = orchestrator.handle(
        db, farmer=farmer, channel=channel, modality=normalized.modality,
        text=normalized.text, media_url=normalized.media_url)
    return reply.to_dict()


@router.get("/whatsapp")
def wa_verify(mode: str = Query(None, alias="hub.mode"),
              token: str = Query(None, alias="hub.verify_token"),
              challenge: str = Query(None, alias="hub.challenge")):
    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        return PlainTextResponse(challenge or "")
    return PlainTextResponse("forbidden", status_code=403)


@router.post("/whatsapp")
async def wa_inbound(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    sig = request.headers.get("X-Hub-Signature-256")
    if not _wa.verify_signature(settings.whatsapp_app_secret, sig, raw):
        return PlainTextResponse("invalid signature", status_code=403)
    import json as _json
    normalized = _wa.normalize(_json.loads(raw or b"{}"))
    reply = _dispatch(db, normalized, "wa")
    return _wa.render(reply)


@router.post("/telegram")
async def tg_inbound(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    normalized = _tg.normalize(body)
    reply = _dispatch(db, normalized, "tg")
    return _tg.render(reply)
