"""Web chat adapter (Phase 1).

The web widget already speaks the normalized contract, so this adapter is a thin
passthrough. It exists so the web channel is symmetric with WA/TG.
"""
from __future__ import annotations

from app.channels.base import ChannelAdapter, NormalizedMessage


class WebAdapter(ChannelAdapter):
    channel = "web"

    def normalize(self, payload: dict) -> NormalizedMessage:
        return NormalizedMessage(
            channel="web",
            external_user_id=payload["external_user_id"],
            modality=payload.get("modality", "text"),
            text=payload.get("text"),
            media_url=payload.get("media_url"),
        )

    def render(self, reply: dict) -> dict:
        # Web consumes the structured reply directly.
        return reply
