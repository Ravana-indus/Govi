"""Price Intelligence agent.

Inputs: crop (resolved or named), farmer GPS, optional quantity.
Logic: latest prices across nearest markets -> net after transport -> 7-day
trend -> sell/hold/go-to recommendation, with confidence and a localized
explanation. Pure logic; no channel imports.

Guardrail: stale (> price_stale_days) or sparse data lowers confidence and is
disclosed; we never fabricate a forecast for perishables. No data at all -> the
agent flags an escalation so staff add prices.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.schemas import PriceAgentOutput, PriceMarketOption
from app.config import settings
from app.core import guardrails
from app.i18n import localize
from app.services import price as price_svc


def _crop_name(crop, lang: str) -> str:
    return {
        "si": crop.name_si, "ta": crop.name_ta, "en": crop.name_en,
    }.get(lang) or crop.name_en


def _decide(trend: str, options: list[dict]) -> str:
    best = options[0]
    if trend == "rising":
        return "hold"
    # Worth travelling to a richer market?
    if (best["distance_km"] is not None and best["distance_km"] > 25
            and len(options) > 1
            and best["net_after_transport"] > options[1]["net_after_transport"] * 1.05):
        return f"go_to:{best['name']}"
    return "sell_now"


def run(db: Session, *, lang: str = "si", crop_id: str | None = None,
        crop_text: str | None = None, gps_lat: float | None = None,
        gps_lng: float | None = None, quantity: float | None = None) -> PriceAgentOutput:
    crop = price_svc.get_crop(db, crop_id) if crop_id else price_svc.resolve_crop(db, crop_text)
    requested_markets = price_svc.resolve_markets(db, crop_text)

    if not crop:
        return PriceAgentOutput(
            recommendation="hold", confidence=0.2,
            explanation_localized=localize("price.which_crop", lang),
        )

    crop_label = _crop_name(crop, lang)
    options = price_svc.market_options(
        db, crop_id=crop.id, gps_lat=gps_lat, gps_lng=gps_lng,
        n=settings.price_nearest_markets,
        market_ids=[market.id for market in requested_markets] or None,
    )

    if not options:
        return PriceAgentOutput(
            crop=crop_label, recommendation="hold", confidence=0.15,
            explanation_localized=localize("price.no_data", lang, crop=crop_label),
            escalate=True, escalate_reason=f"No recent prices for {crop.name_en}",
        )

    best = options[0]
    trend = price_svc.trend(db, crop_id=crop.id, market_id=best["market_id"])
    confidence = guardrails.price_confidence(days_old=best["days_old"], n_markets=len(options))
    reco = _decide(trend, options)

    # Localized recommendation phrase
    if reco.startswith("go_to:"):
        reco_text = localize("price.reco.go_to", lang, market=best["name"])
    else:
        reco_text = localize(f"price.reco.{reco}", lang)

    explanation = localize(
        "price.summary", lang,
        crop=crop_label, price=best["net_after_transport"], currency=best["currency"],
        unit=best["unit"], market=best["name"],
        distance=best["distance_km"] if best["distance_km"] is not None else "?",
        trend=localize(f"price.trend.{trend}", lang), reco=reco_text,
    )
    if best["days_old"] > settings.price_stale_days:
        explanation += " " + localize("price.stale", lang, days=best["days_old"])

    return PriceAgentOutput(
        crop=crop_label,
        markets=[PriceMarketOption(**{k: o[k] for k in (
            "name", "type", "price_min", "price_max", "unit", "currency",
            "net_after_transport", "distance_km", "days_old")}) for o in options],
        trend=trend,
        recommendation=reco,
        confidence=confidence,
        explanation_localized=explanation,
        escalate=False,
    )
