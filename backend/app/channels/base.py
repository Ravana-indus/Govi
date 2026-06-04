"""Channel adapter contract.

Every adapter does exactly two jobs:
  (a) normalize an inbound platform payload -> NormalizedMessage and hand it to
      the core (orchestrator / messages:ingest);
  (b) render the core's response for its platform (text, voice note, buttons).

The core never imports a channel SDK; channels never embed business logic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class NormalizedMessage:
    channel: str                 # wa | tg | web
    external_user_id: str        # phone or platform id (farmer identity seed)
    modality: str = "text"       # text | voice | image
    text: str | None = None
    media_url: str | None = None


class ChannelAdapter(ABC):
    channel: str = "base"

    @abstractmethod
    def normalize(self, payload: dict) -> NormalizedMessage: ...

    @abstractmethod
    def render(self, reply: dict) -> dict:
        """Shape the core reply for this platform's send API."""
