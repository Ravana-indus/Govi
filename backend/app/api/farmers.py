"""Farmer profile, plots, and one-shot web onboarding."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import verify_otp
from app.api.deps import get_current_farmer
from app.api.schemas import FarmerOut, FarmerPatchIn, OnboardIn, PlotCropIn, TokenOut
from app.core.security import create_access_token, create_refresh_token
from app.db.base import get_db
from app.db.models import Farmer
from app.services import farmer as farmer_svc

router = APIRouter(tags=["farmers"])


@router.post("/farmers/onboard", response_model=TokenOut)
def onboard(body: OnboardIn, db: Session = Depends(get_db)):
    """Verify OTP, create/resolve the farmer, capture location, crops, and consent
    in a single call — the web onboarding wizard's submit. Target: first value in
    under 3 minutes."""
    if not verify_otp(body.phone, body.code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid OTP")
    farmer = farmer_svc.resolve_or_create(
        db, phone=body.phone, created_via="web",
        preferred_language=body.preferred_language,
    )
    farmer_svc.update_profile(
        db, farmer, name=body.name, preferred_language=body.preferred_language,
        gps_lat=body.gps_lat, gps_lng=body.gps_lng, district=body.district,
        dsd=body.dsd, village=body.village,
    )
    if body.consent:
        farmer_svc.give_consent(db, farmer)
    if body.crops:
        farmer_svc.add_plot(db, farmer, name="Main plot",
                            crops=[c.model_dump() for c in body.crops])
    db.commit()
    return TokenOut(
        access_token=create_access_token(farmer.id, role="farmer"),
        refresh_token=create_refresh_token(farmer.id, role="farmer"),
        farmer_id=farmer.id, role="farmer",
    )


@router.get("/farmers/me", response_model=FarmerOut)
def me(farmer: Farmer = Depends(get_current_farmer)):
    return farmer


@router.patch("/farmers/me", response_model=FarmerOut)
def update_me(body: FarmerPatchIn, farmer: Farmer = Depends(get_current_farmer),
              db: Session = Depends(get_db)):
    farmer_svc.update_profile(db, farmer, **body.model_dump(exclude_none=True))
    db.commit()
    return farmer


@router.post("/farmers/me/plots", status_code=201)
def add_plot(crops: list[PlotCropIn], farmer: Farmer = Depends(get_current_farmer),
             db: Session = Depends(get_db)):
    plot = farmer_svc.add_plot(db, farmer, name="Plot",
                               crops=[c.model_dump() for c in crops])
    db.commit()
    return {"plot_id": plot.id}


@router.post("/farmers/me/consent", response_model=FarmerOut)
def consent(farmer: Farmer = Depends(get_current_farmer), db: Session = Depends(get_db)):
    farmer_svc.give_consent(db, farmer)
    db.commit()
    return farmer


# ---- PDPA (Sri Lanka PDPA No. 9 of 2022) ----
@router.get("/farmers/me/data")
def export_my_data(farmer: Farmer = Depends(get_current_farmer), db: Session = Depends(get_db)):
    """Data-access request: returns everything held about the requesting farmer."""
    return farmer_svc.export_data(db, farmer)


@router.post("/farmers/me:erase")
def erase_my_data(farmer: Farmer = Depends(get_current_farmer), db: Session = Depends(get_db)):
    """Right-to-erasure: anonymizes the farmer's PII (irreversible)."""
    farmer_svc.erase(db, farmer)
    db.commit()
    return {"erased": True}
