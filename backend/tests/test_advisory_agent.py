from __future__ import annotations

from app.agents import advisory
from app.gateway.types import Completion


class _FakeGateway:
    name = "fake"

    def complete(self, prompt: str, *, system: str | None = None, max_tokens: int = 512):
        return Completion(text="Water tomato plants early in the morning and keep the soil evenly moist.")


def test_advisory_appends_hotline_warning(db, monkeypatch):
    monkeypatch.setattr(advisory, "get_gateway", lambda: _FakeGateway())

    out = advisory.run(
        db,
        lang="en",
        question="how often should I water tomato plants",
        crop_id=None,
        context_text="",
    )

    assert out["agent"] == "advisory"
    assert out["confidence"] == 0.65
    assert "Water tomato plants" in out["reply"]
    assert "0117929494" in out["reply"]


def test_advisory_fallback_still_includes_hotline(db, monkeypatch):
    class BrokenGateway:
        name = "broken"

        def complete(self, prompt: str, *, system: str | None = None, max_tokens: int = 512):
            raise RuntimeError("provider down")

    monkeypatch.setattr(advisory, "get_gateway", lambda: BrokenGateway())

    out = advisory.run(
        db,
        lang="en",
        question="how often should I water tomato plants",
        crop_id=None,
        context_text="",
    )

    assert "general farming guidance" in out["reply"].lower()
    assert "0117929494" in out["reply"]
