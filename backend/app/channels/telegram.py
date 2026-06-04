"""Telegram adapter (Phase 3).

Telegram is the fastest channel to stand up: long-polling getUpdates works with
no public endpoint (good for an early pilot); switch to a webhook in prod
(POST /v1/webhooks/telegram). normalize/render shape inbound/outbound; the API
helpers use stdlib urllib, which honors HTTPS_PROXY in restricted networks.

Note: requires TELEGRAM_BOT_TOKEN and outbound HTTPS to api.telegram.org. Cannot
receive inbound in a no-inbound sandbox — run the poll loop on a real host.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

from app.channels.base import ChannelAdapter, NormalizedMessage
from app.config import settings

_API = "https://api.telegram.org"


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=70) as r:
        return json.loads(r.read().decode())


def _post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


class TelegramAdapter(ChannelAdapter):
    channel = "tg"

    def __init__(self, token: str | None = None) -> None:
        self.token = token or settings.telegram_bot_token

    def _base(self) -> str:
        return f"{_API}/bot{self.token}"

    def normalize(self, payload: dict) -> NormalizedMessage:
        msg = payload.get("message", {}) or payload.get("edited_message", {})
        modality, text, media_url = "text", msg.get("text"), None
        if "voice" in msg:
            modality = "voice"
            media_url = self.file_url(msg["voice"]["file_id"])
        elif "photo" in msg:
            modality = "image"
            media_url = self.file_url(msg["photo"][-1]["file_id"])  # largest size
        return NormalizedMessage(
            channel="tg",
            external_user_id=str(msg.get("from", {}).get("id", "")),
            modality=modality, text=text, media_url=media_url,
        )

    def render(self, reply: dict) -> dict:
        return {"method": "sendMessage", "text": reply.get("reply", "")}

    # --- Bot API helpers (used by the poll loop / webhook sender) ---
    def file_url(self, file_id: str) -> str | None:
        if not self.token:
            return None
        try:
            info = _get(f"{self._base()}/getFile?file_id={urllib.parse.quote(file_id)}")
            path = info["result"]["file_path"]
            return f"{_API}/file/bot{self.token}/{path}"
        except Exception:  # noqa: BLE001
            return None

    def send_message(self, chat_id: str, text: str) -> dict:
        return _post(f"{self._base()}/sendMessage", {"chat_id": chat_id, "text": text})

    def get_updates(self, offset: int | None = None, timeout: int = 60) -> list[dict]:
        url = f"{self._base()}/getUpdates?timeout={timeout}"
        if offset is not None:
            url += f"&offset={offset}"
        return _get(url).get("result", [])
