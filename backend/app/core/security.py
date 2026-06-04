"""Auth primitives: password hashing, JWT, OTP.

Dev note: passwords use stdlib PBKDF2 here to keep the keyless run dependency-free.
Production swaps in argon2 (argon2-cffi is in requirements) — same interface.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings

# Prefer argon2 (recommended); fall back to stdlib PBKDF2 so the keyless dev/CI
# run needs no native build. Both verify paths are supported.
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, InvalidHashError

    _PH = PasswordHasher()
    _HAS_ARGON2 = True
except Exception:  # noqa: BLE001
    _HAS_ARGON2 = False

_PBKDF2_ROUNDS = 200_000


def _pbkdf2(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2${_PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def hash_password(password: str) -> str:
    if _HAS_ARGON2:
        return _PH.hash(password)
    return _pbkdf2(password)


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    if stored.startswith("$argon2"):
        if not _HAS_ARGON2:
            return False
        try:
            return _PH.verify(stored, password)
        except (VerifyMismatchError, InvalidHashError, Exception):  # noqa: BLE001
            return False
    if stored.startswith("pbkdf2$"):
        try:
            _, rounds, salt_hex, dk_hex = stored.split("$")
            dk = hashlib.pbkdf2_hmac(
                "sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds))
            return hmac.compare_digest(dk.hex(), dk_hex)
        except (ValueError, TypeError):
            return False
    return False


def _encode(payload: dict, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {**payload, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def create_access_token(subject: str, *, role: str = "farmer", **extra) -> str:
    return _encode(
        {"sub": subject, "role": role, "type": "access", **extra},
        timedelta(minutes=settings.access_token_ttl_min),
    )


def create_refresh_token(subject: str, *, role: str = "farmer") -> str:
    return _encode(
        {"sub": subject, "role": role, "type": "refresh"},
        timedelta(days=settings.refresh_token_ttl_days),
    )


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"
