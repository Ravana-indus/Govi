"""Auth & onboarding endpoints.

Farmers authenticate with phone + OTP (they have phones, not emails). Staff use
email + password. In dev the OTP is returned in the response so the flow is
testable without an SMS gateway.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import (
    OtpRequestIn, OtpRequestOut, OtpVerifyIn, StaffLoginIn, TokenOut,
)
from app.config import settings
from app.core.cache import get_cache
from app.core.security import (
    create_access_token, create_refresh_token, generate_otp, verify_password,
)
from app.db.base import get_db
from app.db.models import StaffUser
from app.services import farmer as farmer_svc

router = APIRouter(prefix="/auth", tags=["auth"])

_OTP_TTL = 300


def _otp_key(phone: str) -> str:
    return f"otp:{phone}"


def verify_otp(phone: str, code: str) -> bool:
    stored = get_cache().get(_otp_key(phone))
    return bool(stored) and str(stored) == str(code)


@router.post("/otp/request", response_model=OtpRequestOut)
def request_otp(body: OtpRequestIn):
    code = generate_otp()
    get_cache().set(_otp_key(body.phone), code, ttl=_OTP_TTL)
    # TODO(prod): send via SMS gateway instead of returning.
    dev = code if (settings.app_env == "dev" and settings.expose_otp_in_dev) else None
    return OtpRequestOut(sent=True, dev_otp=dev)


@router.post("/otp/verify", response_model=TokenOut)
def verify_otp_endpoint(body: OtpVerifyIn, db: Session = Depends(get_db)):
    if not verify_otp(body.phone, body.code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid OTP")
    get_cache().delete(_otp_key(body.phone))
    farmer = farmer_svc.resolve_or_create(
        db, phone=body.phone, created_via="web",
        preferred_language=body.preferred_language,
    )
    db.commit()
    return TokenOut(
        access_token=create_access_token(farmer.id, role="farmer"),
        refresh_token=create_refresh_token(farmer.id, role="farmer"),
        farmer_id=farmer.id, role="farmer",
    )


@router.post("/staff/login", response_model=TokenOut)
def staff_login(body: StaffLoginIn, db: Session = Depends(get_db)):
    staff = db.scalar(select(StaffUser).where(StaffUser.email == body.email))
    if not staff or not verify_password(body.password, staff.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if staff.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Inactive account")
    return TokenOut(
        access_token=create_access_token(staff.id, role=staff.role),
        refresh_token=create_refresh_token(staff.id, role=staff.role),
        role=staff.role,
    )
