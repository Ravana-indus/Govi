"""Fast intent classifier.

The blueprint calls for "a fast LLM/intent classifier". For the keyless slice we
use a deterministic bilingual keyword classifier — a legitimately fast, free
classifier. Swapping in an LLM classifier means one call to gateway.complete with
a classification prompt; the orchestrator contract is unchanged.

Intents: language | price | crop_health | greeting | other.
(calendar/input_cost are LATER.)
"""
from __future__ import annotations

import re

INTENTS = ("language", "price", "crop_health", "greeting", "other")

_PRICE_KW = [
    "price", "rate", "cost", "sell", "market", "wholesale", "kg",
    "මිල", "අගය", "විකුණ", "වෙළඳ",           # Sinhala
    "விலை", "சந்தை", "விற்க", "கிலோ",          # Tamil
]
_CROP_KW = [
    "disease", "sick", "pest", "blight", "spot", "leaf", "rot", "fungus",
    "yellow", "wilt", "insect", "curl",
    "රෝග", "පළිබෝධ", "කොළ", "පැළ", "දිලීර",      # Sinhala
    "நோய்", "பூச்சி", "இலை", "செடி", "பூஞ்சை",   # Tamil
]
_GREET_KW = [
    "hi", "hello", "hey", "good morning", "good evening",
    "ආයුබෝ", "හලෝ", "සුබ",
    "வணக்கம்", "ஹலோ",
]

_LANG_COMMANDS = {
    "ta": {
        "ta", "tam", "tamil", "தமிழ்", "தமிழ", "demala", "දෙමළ",
        "change to tamil", "switch to tamil", "language tamil",
    },
    "si": {
        "si", "sin", "sinhala", "සිංහල", "sinhala language",
        "change to sinhala", "switch to sinhala", "language sinhala",
    },
    "en": {
        "en", "eng", "english", "ඉංග්‍රීසි", "ஆங்கிலம்",
        "change to english", "switch to english", "language english",
    },
}


def detect_language_command(text: str | None) -> str | None:
    """Return a supported language code when text is a language switch command."""
    if not text:
        return None
    t = " ".join(text.lower().strip().split())
    for lang, commands in _LANG_COMMANDS.items():
        if t in commands:
            return lang
    return None


def detect_text_language(text: str | None) -> str | None:
    """Best-effort language detection for one short chat turn."""
    if not text:
        return None
    if re.search(r"[\u0d80-\u0dff]", text):
        return "si"
    if re.search(r"[\u0b80-\u0bff]", text):
        return "ta"
    if re.search(r"[a-zA-Z]", text):
        return "en"
    return None


def classify_intent(text: str | None, *, has_image: bool = False) -> str:
    """Return one of INTENTS. An image always routes to the Crop Doctor."""
    if has_image:
        return "crop_health"
    if not text:
        return "other"
    t = text.lower().strip()
    if detect_language_command(t):
        return "language"
    if any(k in t for k in _CROP_KW):
        return "crop_health"
    if any(k in t for k in _PRICE_KW):
        return "price"
    if any(t == k or t.startswith(k) for k in _GREET_KW):
        return "greeting"
    return "other"
