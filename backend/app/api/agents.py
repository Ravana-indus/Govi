"""Direct agent endpoints (also used by portals + tests).

These bypass the orchestrator and call an agent directly with explicit inputs —
handy for the staff price-portal 'preview', for testing, and for contract checks.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.agents import crop as crop_agent
from app.agents import price as price_agent
from app.agents.schemas import CropAgentOutput, PriceAgentOutput
from app.api.deps import rate_limit
from app.config import settings
from app.core.security import decode_token
from app.db.base import get_db
from app.db.models import Farmer
from app.services import escalation as escalation_svc

router = APIRouter(prefix="/agents", tags=["agents"], dependencies=[Depends(rate_limit)])


@router.post("/price", response_model=PriceAgentOutput)
def price(body: dict, db: Session = Depends(get_db)):
    return price_agent.run(
        db, lang=body.get("lang", "si"), crop_id=body.get("crop_id"),
        crop_text=body.get("crop"), gps_lat=body.get("gps_lat"),
        gps_lng=body.get("gps_lng"), quantity=body.get("quantity"),
    )


def _resolve_farmer(db: Session, farmer_id: str | None, authorization: str | None) -> Farmer:
    if not farmer_id and authorization and authorization.lower().startswith("bearer "):
        try:
            farmer_id = decode_token(authorization.split(" ", 1)[1]).get("sub")
        except Exception:  # noqa: BLE001
            farmer_id = None
    if not farmer_id:
        raise HTTPException(400, "farmer_id (or a farmer bearer token) is required")
    farmer = db.get(Farmer, farmer_id)
    if not farmer:
        raise HTTPException(404, "Farmer not found")
    return farmer


@router.post("/crop", response_model=CropAgentOutput)
async def crop(
    image: UploadFile = File(...),
    crop_id: str | None = Form(None),
    lang: str = Form("si"),
    farmer_id: str | None = Form(None),
    symptom_text: str | None = Form(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    farmer = _resolve_farmer(db, farmer_id, authorization)
    image_bytes = await image.read()
    if len(image_bytes) > settings.max_media_mb * 1024 * 1024:
        raise HTTPException(413, f"Image exceeds {settings.max_media_mb} MB limit")
    out = crop_agent.run(
        db, farmer=farmer, image_bytes=image_bytes, image_url=image.filename,
        crop_id=crop_id, symptom_text=symptom_text, lang=lang,
    )
    # Guarantee the human-in-the-loop record exists regardless of entry path
    # (the orchestrator does this for conversational turns; mirror it here).
    if out.escalate:
        esc = escalation_svc.create(
            db, farmer_id=farmer.id, type="crop",
            reason=out.escalate_reason or "low_confidence")
        out.escalate_reason = out.escalate_reason or esc.reason
    db.commit()
    return out
