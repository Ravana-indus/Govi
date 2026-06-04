"""Example real provider (seam demonstration).

Implements the same ModelProvider interface as the mock. Wiring a real model is
a config change (MODEL_PROVIDER=openai + LLM_API_KEY), not a code change. Network
calls are intentionally left as TODOs so the slice has zero external dependencies.
"""
from __future__ import annotations

from app.config import settings
from app.gateway.base import ModelProvider
from app.gateway.types import Completion, Transcript, VisionResult


class OpenAIProvider(ModelProvider):
    name = "openai"

    def __init__(self) -> None:
        if not settings.llm_api_key:
            raise RuntimeError(
                "MODEL_PROVIDER=openai requires LLM_API_KEY. "
                "Use MODEL_PROVIDER=mock for keyless dev/CI."
            )

    def complete(self, prompt, *, system=None, max_tokens=512) -> Completion:  # noqa: D401
        raise NotImplementedError("Wire the OpenAI chat.completions call here.")

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError("Wire text-embedding-3-* here.")

    def transcribe(self, audio: bytes, lang: str) -> Transcript:
        raise NotImplementedError("Wire Whisper / a Sinhala-Tamil ASR here.")

    def speak(self, text: str, lang: str) -> bytes:
        raise NotImplementedError("Wire a Sinhala-Tamil TTS here.")

    def vision_classify(self, image: bytes, *, crop=None) -> VisionResult:
        raise NotImplementedError("Wire a vision-LLM or trained classifier here.")
