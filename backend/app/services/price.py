"""Price service: market-aware pricing data for the Price Intelligence agent.

Pure data + math; no LLM, no channel imports. The agent layer turns these
structures into a localized recommendation.
"""
from __future__ import annotations

from datetime import date, timedelta
from difflib import SequenceMatcher
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Crop, Market, PriceRecord
from app.services.geo import haversine_km


# --------------------------------------------------------------------------- #
# Crop resolution
# --------------------------------------------------------------------------- #
_CROP_STOPWORDS = {
    "a", "an", "and", "at", "for", "from", "in", "is", "kg", "market", "price",
    "prices", "pricing", "rate", "rates", "sell", "the", "to", "today",
}

_CROP_ALIASES = {
    "Tomato": ("tomato", "tomatoes", "tomoto", "tomatto"),
    "Big Onion": ("big onion", "onion", "onions"),
    "Green Chili": ("green chili", "green chilli", "chili", "chilli"),
    "Samba Rice": ("samba rice", "rice"),
}


def _normalize(text: str | None) -> str:
    return " ".join((text or "").lower().strip().split())


def _ascii_words(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


def _contains_term(text: str, term: str) -> bool:
    term = term.lower().strip()
    if not term:
        return False
    if term.isascii():
        return bool(re.search(rf"\b{re.escape(term)}\b", text))
    return term in text


def _crop_terms(crop: Crop) -> list[str]:
    terms = [crop.name_en, crop.name_si, crop.name_ta]
    terms.extend(_CROP_ALIASES.get(crop.name_en, ()))
    return [t.lower().strip() for t in terms if t]


def _crop_fuzzy_terms(crop: Crop) -> set[str]:
    terms: set[str] = set()
    for term in _crop_terms(crop):
        if not term.isascii():
            continue
        for word in _ascii_words(term):
            if len(word) >= 4 and word not in _CROP_STOPWORDS:
                terms.add(word)
    return terms


def resolve_crop(db: Session, text: str | None) -> Crop | None:
    """Match a crop by any of its localized names appearing in free text."""
    if not text:
        return None
    t = _normalize(text)
    crops = list(db.scalars(select(Crop)))
    for crop in crops:
        for term in _crop_terms(crop):
            if _contains_term(t, term):
                return crop

    words = [
        word for word in _ascii_words(t)
        if len(word) >= 4 and word not in _CROP_STOPWORDS
    ]
    best: tuple[float, Crop | None] = (0.0, None)
    for crop in crops:
        for word in words:
            for term in _crop_fuzzy_terms(crop):
                score = SequenceMatcher(None, word, term).ratio()
                if score > best[0]:
                    best = (score, crop)
    if best[0] >= 0.82:
        return best[1]
    return None


def get_crop(db: Session, crop_id: str) -> Crop | None:
    return db.get(Crop, crop_id)


def resolve_markets(db: Session, text: str | None) -> list[Market]:
    """Match explicitly requested markets such as Dambulla or Colombo."""
    if not text:
        return []
    t = _normalize(text)
    matches: list[Market] = []
    for market in db.scalars(select(Market).order_by(Market.name)):
        terms = [market.name, market.district]
        terms.extend(
            word for word in _ascii_words(market.name)
            if len(word) >= 5 and word not in {"market", "centre", "center", "economic"}
        )
        if any(_contains_term(t, term) for term in terms if term):
            matches.append(market)
    return matches


# --------------------------------------------------------------------------- #
# Latest prices + market options
# --------------------------------------------------------------------------- #
def _latest_per_market(db: Session, crop_id: str) -> dict[str, PriceRecord]:
    rows = db.scalars(
        select(PriceRecord)
        .where(PriceRecord.crop_id == crop_id)
        .order_by(PriceRecord.observed_date.desc(), PriceRecord.created_at.desc())
    )
    latest: dict[str, PriceRecord] = {}
    for r in rows:
        latest.setdefault(r.market_id, r)  # first seen per market = most recent
    return latest


def days_old(record: PriceRecord, today: date | None = None) -> int:
    today = today or date.today()
    return (today - record.observed_date).days


def market_options(db: Session, *, crop_id: str, gps_lat: float | None,
                   gps_lng: float | None, n: int | None = None,
                   market_ids: list[str] | None = None) -> list[dict]:
    """Ranked market options with net price after estimated transport.

    Sorted by net_after_transport descending (best take-home first)."""
    n = n or settings.price_nearest_markets
    latest = _latest_per_market(db, crop_id)
    if market_ids:
        wanted = set(market_ids)
        latest = {market_id: rec for market_id, rec in latest.items() if market_id in wanted}
    options: list[dict] = []
    for market_id, rec in latest.items():
        market = db.get(Market, market_id)
        midpoint = (rec.price_min + rec.price_max) / 2.0
        distance = None
        net = midpoint
        if gps_lat is not None and gps_lng is not None \
                and market and market.gps_lat is not None:
            distance = haversine_km(gps_lat, gps_lng, market.gps_lat, market.gps_lng)
            net = round(midpoint - settings.price_transport_lkr_per_km * distance, 1)
        options.append({
            "market_id": market_id,
            "name": market.name if market else "?",
            "type": market.type if market else None,
            "price_min": rec.price_min,
            "price_max": rec.price_max,
            "unit": rec.unit,
            "currency": rec.currency,
            "observed_date": rec.observed_date.isoformat(),
            "days_old": days_old(rec),
            "distance_km": distance,
            "net_after_transport": net,
        })
    options.sort(key=lambda o: o["net_after_transport"], reverse=True)
    return options[:n]


def trend(db: Session, *, crop_id: str, market_id: str, window_days: int = 7) -> str:
    """rising | flat | falling over the trailing window for a market."""
    since = date.today() - timedelta(days=window_days)
    rows = list(db.scalars(
        select(PriceRecord)
        .where(PriceRecord.crop_id == crop_id,
               PriceRecord.market_id == market_id,
               PriceRecord.observed_date >= since)
        .order_by(PriceRecord.observed_date.asc())
    ))
    if len(rows) < 2:
        return "flat"
    first = (rows[0].price_min + rows[0].price_max) / 2.0
    last = (rows[-1].price_min + rows[-1].price_max) / 2.0
    if last > first * 1.03:
        return "rising"
    if last < first * 0.97:
        return "falling"
    return "flat"


# --------------------------------------------------------------------------- #
# Staff-portal write paths
# --------------------------------------------------------------------------- #
def create_price(db: Session, *, market_id: str, crop_id: str, price_min: float,
                 price_max: float, observed_date: date, unit: str = "kg",
                 currency: str = "LKR", source: str = "staff",
                 entered_by: str | None = None, confidence: float = 1.0) -> PriceRecord:
    rec = PriceRecord(
        market_id=market_id, crop_id=crop_id, price_min=price_min,
        price_max=price_max, observed_date=observed_date, unit=unit,
        currency=currency, source=source, entered_by=entered_by, confidence=confidence,
    )
    db.add(rec)
    db.flush()
    return rec


def list_prices(db: Session, *, crop_id=None, market_id=None,
                date_from: date | None = None, date_to: date | None = None,
                limit: int = 200) -> list[PriceRecord]:
    stmt = select(PriceRecord)
    if crop_id:
        stmt = stmt.where(PriceRecord.crop_id == crop_id)
    if market_id:
        stmt = stmt.where(PriceRecord.market_id == market_id)
    if date_from:
        stmt = stmt.where(PriceRecord.observed_date >= date_from)
    if date_to:
        stmt = stmt.where(PriceRecord.observed_date <= date_to)
    stmt = stmt.order_by(PriceRecord.observed_date.desc()).limit(limit)
    return list(db.scalars(stmt))


def coverage_today(db: Session, *, district: str | None = None) -> dict:
    """Which market x crop combinations have a price observed today.

    Powers the ground-staff 'today's coverage' dashboard."""
    today = date.today()
    markets = list(db.scalars(
        select(Market).where(Market.district == district) if district
        else select(Market)
    ))
    crops = list(db.scalars(select(Crop)))
    todays = set(
        (r.market_id, r.crop_id)
        for r in db.scalars(
            select(PriceRecord).where(PriceRecord.observed_date == today)
        )
    )
    missing = []
    covered = 0
    for m in markets:
        for c in crops:
            if (m.id, c.id) in todays:
                covered += 1
            else:
                missing.append({"market": m.name, "market_id": m.id,
                                "crop": c.name_en, "crop_id": c.id})
    total = max(1, len(markets) * len(crops))
    return {
        "date": today.isoformat(),
        "covered": covered,
        "total": total,
        "coverage_pct": round(100 * covered / total, 1),
        "missing": missing[:100],
    }
