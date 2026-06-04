"""Media store.

Dev fallback writes bytes to a local dir and returns a path-style URL. Prod
swaps this for S3 with signed, expiring URLs (same save_bytes signature).
"""
from __future__ import annotations

import os
import uuid

from app.config import settings


def save_bytes(data: bytes, *, ext: str = "bin") -> str:
    os.makedirs(settings.media_dir, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(settings.media_dir, name)
    with open(path, "wb") as fh:
        fh.write(data)
    # Returned as a relative URL; prod returns a signed S3 URL instead.
    return f"/media/{name}"
