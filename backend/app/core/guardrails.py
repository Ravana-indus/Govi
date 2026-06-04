"""Shared guardrail layer.

- Confidence gating per agent (escalate below threshold).
- Basic prompt-injection scrubbing for any user text fed to the model.
- Abuse/profanity hook (stubbed; wire a real classifier in prod).
- "No guarantees" policy reminder appended to risk-bearing advice.
"""
from __future__ import annotations

import re

from app.config import settings

_INJECTION_PATTERNS = [
    re.compile(r"ignore (all|previous) instructions", re.I),
    re.compile(r"system prompt", re.I),
    re.compile(r"you are now", re.I),
]


def scrub_user_text(text: str | None) -> str:
    """Neutralize obvious prompt-injection before text reaches the model."""
    if not text:
        return ""
    cleaned = text
    for pat in _INJECTION_PATTERNS:
        cleaned = pat.sub("[filtered]", cleaned)
    return cleaned.strip()[:4000]


def is_abusive(text: str | None) -> bool:
    # Placeholder. Wire a real profanity/abuse classifier in prod.
    return False


def crop_should_escalate(confidence: float, *, usable: bool = True,
                         threshold: float | None = None) -> bool:
    if not usable:
        return True
    thr = settings.crop_confidence_threshold if threshold is None else threshold
    return confidence < thr


def price_confidence(days_old: int, n_markets: int) -> float:
    """Confidence falls as data gets stale or sparse."""
    conf = 1.0
    if days_old > settings.price_stale_days:
        conf -= min(0.5, 0.1 * (days_old - settings.price_stale_days))
    if n_markets <= 1:
        conf -= 0.2
    return round(max(0.1, conf), 2)
