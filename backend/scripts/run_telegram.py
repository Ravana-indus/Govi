"""Telegram long-poll runner (Phase 3, deployment).

Polls getUpdates, forwards each message to the channel-agnostic core via
/v1/messages:ingest, and sends the reply back. Keeps the brain behind the API.

Run on a real host (needs TELEGRAM_BOT_TOKEN + reachable API):
    TELEGRAM_BOT_TOKEN=... API_BASE=http://localhost:8000/v1 \
        PYTHONPATH=. python scripts/run_telegram.py

This cannot run inside a no-inbound sandbox. For prod, prefer a webhook to
POST /v1/webhooks/telegram instead of polling.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.channels.telegram import TelegramAdapter  # noqa: E402

API_BASE = os.environ.get("API_BASE", "http://localhost:8000/v1")


def ingest(channel: str, external_user_id: str, modality: str, text, media_url):
    payload = json.dumps({
        "channel": channel, "external_user_id": external_user_id,
        "modality": modality, "text": text, "media_url": media_url,
    }).encode()
    req = urllib.request.Request(f"{API_BASE}/messages:ingest", data=payload,
                                method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode())


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN required")
    tg = TelegramAdapter(token)
    print("Telegram poll loop started.")
    offset = None
    while True:
        try:
            for upd in tg.get_updates(offset=offset, timeout=60):
                offset = upd["update_id"] + 1
                msg = tg.normalize(upd)
                if not msg.external_user_id:
                    continue
                reply = ingest("tg", msg.external_user_id, msg.modality,
                               msg.text, msg.media_url)
                chat_id = (upd.get("message") or {}).get("chat", {}).get("id")
                if chat_id:
                    tg.send_message(str(chat_id), reply.get("reply", ""))
        except Exception as e:  # noqa: BLE001
            print("poll error:", e)
            time.sleep(3)


if __name__ == "__main__":
    main()
