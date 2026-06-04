"""Tiny i18n helper.

All farmer-facing strings live in si.json / ta.json / en.json — never hard-coded.
localize() resolves a key in the requested language, falls back to English, then
to the raw key, and applies {placeholder} substitution.

NOTE: Sinhala/Tamil safety and treatment copy here is placeholder-quality and
MUST be replaced by professional translation + agronomy-partner review before any
field use (Blueprint section 11). Machine translation alone is unacceptable for
pesticide guidance.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent
_LANGS = ("si", "ta", "en")


@lru_cache
def _bundle(lang: str) -> dict:
    path = _DIR / f"{lang}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def localize(key: str, lang: str = "si", /, **kwargs) -> str:
    lang = lang if lang in _LANGS else "en"
    template = _bundle(lang).get(key) or _bundle("en").get(key) or key
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template
