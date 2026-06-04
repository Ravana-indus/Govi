"""Deterministic mock provider.

Same output for the same input, always. This lets the entire system run and CI
pass with no external keys, and lets tests target specific branches (e.g. an
unusable image -> low confidence -> escalation) by crafting the input bytes.
"""
from __future__ import annotations

import hashlib

from app.gateway.base import ModelProvider
from app.gateway.types import Completion, Transcript, VisionResult

# Small, fixed disease vocabulary for the Crop Doctor demo.
_DISEASE_VOCAB = ["early_blight", "late_blight", "leaf_curl_virus", "healthy"]
# Deterministic "transcripts" so voice notes route meaningfully in dev/CI.
# A real ASR returns the farmer's actual speech; this stands in for it.
_ASR_PHRASES = [
    "tomato price",
    "my plant has spots on the leaves",
    "what is the price of big onion",
    "hello",
]
_EMBED_DIM = 16


def _hash_float(data: bytes, salt: str = "") -> float:
    """Deterministic float in [0, 1) from bytes."""
    h = hashlib.sha256(salt.encode() + data).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


class MockProvider(ModelProvider):
    name = "mock"

    def complete(self, prompt: str, *, system: str | None = None,
                 max_tokens: int = 512) -> Completion:
        # Deterministic "phrasing" pass: the mock simply returns the structured
        # draft it was handed. Real providers rewrite it into fluent prose.
        text = prompt.strip()
        return Completion(text=text, tokens=len(text.split()), cost=0.0)

    def embed(self, text: str) -> list[float]:
        return [_hash_float(text.encode(), salt=str(i)) for i in range(_EMBED_DIM)]

    def transcribe(self, audio: bytes, lang: str) -> Transcript:
        # Deterministic phrase from the audio bytes so voice routes meaningfully.
        audio = audio or b""
        if len(audio) < 4:
            return Transcript(text="", lang=lang, confidence=0.0)
        idx = int(_hash_float(audio, "asrphrase") * len(_ASR_PHRASES)) % len(_ASR_PHRASES)
        conf = round(0.7 + 0.3 * _hash_float(audio, "asr"), 2)
        return Transcript(text=_ASR_PHRASES[idx], lang=lang, confidence=conf)

    def speak(self, text: str, lang: str) -> bytes:
        # Returns a tiny deterministic "audio" stub.
        return b"MOCK_AUDIO::" + hashlib.sha256(text.encode()).digest()[:8]

    def vision_classify(self, image: bytes, *, crop: str | None = None) -> VisionResult:
        image = image or b""
        # Tiny/empty images are treated as unusable -> forces escalation path.
        if len(image) < 16:
            return VisionResult(label="unusable", confidence=0.0, usable=False)
        r = _hash_float(image, "vision")
        idx = int(r * len(_DISEASE_VOCAB)) % len(_DISEASE_VOCAB)
        label = _DISEASE_VOCAB[idx]
        # Spread confidence across [0.45, 0.95] so both the confident and the
        # escalate-on-low-confidence branches are reachable deterministically.
        confidence = round(0.45 + 0.5 * _hash_float(image, "conf"), 2)
        candidates = [(label, confidence)]
        return VisionResult(label=label, confidence=confidence, candidates=candidates)
