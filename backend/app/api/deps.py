"""Shared API dependencies: auth principals, role gating, rate limiting."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.cache import get_cache
from app.core.security import decode_token
from app.db.base import get_db
from app.db.models import Farmer, StaffUser


def _bearer(authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        return decode_token(token)
    except Exception:  # noqa: BLE001 - any decode error is a 401
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")


def get_current_farmer(authorization: str | None = Header(None),
                       db: Session = Depends(get_db)) -> Farmer:
    payload = _bearer(authorization)
    if payload.get("role") != "farmer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Farmer token required")
    farmer = db.get(Farmer, payload.get("sub"))
    if not farmer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Farmer not found")
    return farmer


def require_staff(*roles: str):
    """Dependency factory enforcing a staff role (and exposing district scope)."""
    def _dep(authorization: str | None = Header(None),
             db: Session = Depends(get_db)) -> StaffUser:
        payload = _bearer(authorization)
        if payload.get("role") not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                f"Requires role in {roles}")
        staff = db.get(StaffUser, payload.get("sub"))
        if not staff or staff.status != "active":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Inactive or unknown staff")
        return staff
    return _dep


def rate_limit(authorization: str | None = Header(None)) -> None:
    """Per-principal sliding 60s window (Redis in prod; in-memory in dev)."""
    key = f"rl:{(authorization or 'anon')[-32:]}"
    count = get_cache().incr(key, ttl=60)
    if count > settings.rate_limit_per_min:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded")
