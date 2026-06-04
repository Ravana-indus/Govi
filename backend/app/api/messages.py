"""Conversation core — the channel-agnostic ingest endpoint + conversation reads.

Adapters (web/WA/TG) all funnel here. The endpoint resolves the farmer from the
external_user_id (phone is identity), runs the orchestrator, and returns a
normalized reply the adapter renders for its platform.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import rate_limit
from app.api.schemas import IngestIn, ReplyOut
from app.core import orchestrator
from app.db.base import get_db
from app.db.models import Conversation, Message
from app.services import farmer as farmer_svc

router = APIRouter(tags=["conversation"])


def _read_media_bytes(media_url: str | None) -> bytes | None:
    """Dev helper: if media_url points to a readable local file, load it.
    (Prod: fetch from S3 / the channel's media API.)"""
    if media_url and os.path.isfile(media_url):
        try:
            with open(media_url, "rb") as fh:
                return fh.read()
        except OSError:
            return None
    return None


@router.post("/messages:ingest", response_model=ReplyOut, dependencies=[Depends(rate_limit)])
def ingest(body: IngestIn, db: Session = Depends(get_db)):
    farmer = farmer_svc.resolve_or_create(
        db, phone=body.external_user_id, created_via=body.channel)
    db.commit()
    reply = orchestrator.handle(
        db, farmer=farmer, channel=body.channel, modality=body.modality,
        text=body.text, media_url=body.media_url,
        media_bytes=_read_media_bytes(body.media_url),
    )
    return ReplyOut(**reply.to_dict())


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    msgs = list(db.scalars(
        select(Message).where(Message.conversation_id == conv.id)
        .order_by(Message.created_at.asc())))
    return {
        "id": conv.id, "farmer_id": conv.farmer_id, "channel": conv.channel,
        "state": conv.state, "last_intent": conv.last_intent,
        "messages": [
            {"direction": m.direction, "modality": m.modality, "text": m.content_text,
             "agent": m.agent, "confidence": m.confidence} for m in msgs
        ],
    }
