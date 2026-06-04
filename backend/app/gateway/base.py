"""Model gateway interface.

Every agent and service talks to *this* interface, never to a vendor SDK. A
provider is selected per capability by env var (see app/gateway/__init__.py).
The mock provider returns deterministic, schema-valid outputs so the whole
system — and CI — runs with zero external keys.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.gateway.types import Completion, Transcript, VisionResult


class ModelProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def complete(self, prompt: str, *, system: str | None = None,
                 max_tokens: int = 512) -> Completion: ...

    @abstractmethod
    def embed(self, text: str) -> list[float]: ...

    @abstractmethod
    def transcribe(self, audio: bytes, lang: str) -> Transcript: ...

    @abstractmethod
    def speak(self, text: str, lang: str) -> bytes: ...

    @abstractmethod
    def vision_classify(self, image: bytes, *, crop: str | None = None) -> VisionResult: ...
