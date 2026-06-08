"""Price Intelligence agent unit tests (against seeded data + mock gateway)."""
from __future__ import annotations

from app.agents import price as price_agent
from app.agents.schemas import PriceAgentOutput


def test_price_ranks_by_net_after_transport(db):
    # Farmer near Matale asking for tomato.
    out = price_agent.run(db, lang="en", crop_text="tomato", gps_lat=7.47, gps_lng=80.62)
    assert isinstance(out, PriceAgentOutput)
    assert out.crop == "Tomato"
    assert out.markets, "expected market options"
    nets = [m.net_after_transport for m in out.markets]
    assert nets == sorted(nets, reverse=True), "markets must be ranked by net desc"
    assert out.confidence > 0.9  # fresh, multi-market data
    assert out.escalate is False


def test_price_recommendation_is_valid_token(db):
    out = price_agent.run(db, lang="en", crop_text="tomato", gps_lat=7.47, gps_lng=80.62)
    assert out.recommendation == "sell_now" or out.recommendation == "hold" \
        or out.recommendation.startswith("go_to:")


def test_price_unknown_crop_asks_which(db):
    out = price_agent.run(db, lang="en", crop_text="spaceship")
    assert out.markets == []
    assert out.confidence <= 0.3
    assert "crop" in out.explanation_localized.lower()


def test_price_resolves_common_crop_typo_and_market(db):
    out = price_agent.run(db, lang="en", crop_text="tomoto price in colombo")

    assert out.crop == "Tomato"
    assert out.markets
    assert out.markets[0].name == "Colombo Manning Market"
    assert "Colombo Manning Market" in out.explanation_localized


def test_price_no_data_escalates(db):
    # Beetroot is intentionally never priced (in seed or other tests) -> escalate.
    out = price_agent.run(db, lang="en", crop_text="beetroot", gps_lat=7.47, gps_lng=80.62)
    assert out.escalate is True
    assert out.escalate_reason


def test_price_localized_explanation_differs_by_language(db):
    en = price_agent.run(db, lang="en", crop_text="tomato", gps_lat=7.47, gps_lng=80.62)
    si = price_agent.run(db, lang="si", crop_text="tomato", gps_lat=7.47, gps_lng=80.62)
    assert en.explanation_localized != si.explanation_localized
