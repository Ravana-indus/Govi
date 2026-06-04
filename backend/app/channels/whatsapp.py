"""WhatsApp Cloud API adapter — SCAFFOLD (Phase 3).

Reality check (from the blueprint): WhatsApp needs a Meta Business account, a
verified number, pre-approved templates for business-initiated messages, and a
public HTTPS webhook with signature + verify-token checks. It cannot run inside a
no-inbound sandbox — deploy to a real host. The normalize/render shapes are real;
network + signature verification are marked TODO.
"""
from __future__ import annotations

from app.channels.base import ChannelAdapter, NormalizedMessage


class WhatsAppAdapter(ChannelAdapter):
    channel = "wa"

    def normalize(self, payload: dict) -> NormalizedMessage:
        try:
            value = payload["entry"][0]["changes"][0]["value"]
            msg = value["messages"][0]
            mtype = msg.get("type", "text")
            modality = {"audio": "voice", "image": "image"}.get(mtype, "text")
            text = msg.get("text", {}).get("body") if mtype == "text" else None
            media_url = None  # TODO: resolve media id -> download URL (Graph API)
            return NormalizedMessage(
                channel="wa", external_user_id=msg["from"],
                modality=modality, text=text, media_url=media_url,
            )
        except (KeyError, IndexError):
            return NormalizedMessage(channel="wa", external_user_id="", text=None)

    def render(self, reply: dict) -> dict:
        # TODO: POST to graph.facebook.com/<v>/<phone_id>/messages
        return {"messaging_product": "whatsapp", "text": {"body": reply.get("reply", "")}}

    @staticmethod
    def verify_signature(app_secret: str | None, signature: str | None, body: bytes) -> bool:
        """Verify Meta's X-Hub-Signature-256 header (sha256=<hmac>)."""
        if not app_secret:
            return True  # not configured -> skip (dev). Enforced when set.
        if not signature or not signature.startswith("sha256="):
            return False
        import hashlib
        import hmac as _hmac
        expected = _hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
        return _hmac.compare_digest(expected, signature.split("=", 1)[1])
