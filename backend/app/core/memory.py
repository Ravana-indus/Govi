"""Short-term conversation memory (Redis in prod, in-memory in dev).

Keeps the last N turns per conversation so the orchestrator can attach light
context without a DB round-trip on every message.
"""
from __future__ import annotations

from app.core.cache import get_cache

_MAX_TURNS = 8
_TTL_SECONDS = 60 * 60  # 1h sliding window


def _key(conversation_id: str) -> str:
    return f"conv:mem:{conversation_id}"


def append_turn(conversation_id: str, role: str, text: str) -> None:
    cache = get_cache()
    history: list[dict] = list(cache.get(_key(conversation_id)) or [])
    history.append({"role": role, "text": text})
    history = history[-_MAX_TURNS:]
    cache.set(_key(conversation_id), history, ttl=_TTL_SECONDS)


def get_history(conversation_id: str) -> list[dict]:
    return list(get_cache().get(_key(conversation_id)) or [])
