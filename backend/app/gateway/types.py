"""Typed I/O for the model gateway."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Completion:
    text: str
    tokens: int = 0
    cost: float = 0.0


@dataclass
class Transcript:
    text: str
    lang: str
    confidence: float = 1.0


@dataclass
class VisionResult:
    label: str
    confidence: float
    candidates: list[tuple[str, float]] = field(default_factory=list)
    usable: bool = True
