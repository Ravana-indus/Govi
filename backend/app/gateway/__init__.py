"""Gateway factory.

Returns a single ModelProvider chosen by MODEL_PROVIDER. (Per-capability routing
— a different provider for vision/asr/tts — is a trivial extension: read
settings.vision_provider etc. and compose. For the slice every capability is
served by the selected provider, defaulting to the deterministic mock.)
"""
from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.gateway.base import ModelProvider
from app.gateway.mock import MockProvider


@lru_cache
def get_gateway() -> ModelProvider:
    provider = settings.model_provider.lower()
    if provider == "mock":
        return MockProvider()
    if provider == "openai":
        from app.gateway.openai_provider import OpenAIProvider

        return OpenAIProvider()
    # anthropic / gemini / local would register here.
    raise RuntimeError(f"Unknown MODEL_PROVIDER={provider!r}")


__all__ = ["get_gateway", "ModelProvider"]
