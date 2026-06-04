"""Prices, markets, crops — the ground-staff price portal's backend.

The portal IS the Day-1 price integration (no external feed dependency). Writes
are role-gated (ground_staff/admin), district-scoped server-side, and audited.
Reads of reference data (crops, markets) are open so the farmer app can populate
pickers.
"""
from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_staff
from app.api.schemas import (
    BulkResult, MarketIn, MarketOut, PriceIn, PriceOut, PricePatch,
)
from app.db.base import get_db
from app.db.models import Crop, Market, PriceRecord, StaffUser
from app.services import audit
from app.services import price as price_svc

router = APIRouter(tags=["prices"])


def _check_district(staff: StaffUser, market: Market) -> None:
    """Enforce district scope server-side (never trust the client)."""
    if staff.role == "admin" or not staff.district_scope:
        return
    if market.district and market.district not in staff.district_scope:
        raise HTTPException(403, f"Out of district scope: {market.district}")


# ---- Reference data (open) ----
@router.get("/crops")
def list_crops(db: Session = Depends(get_db)):
    return [
        {"id": c.id, "name_en": c.name_en, "name_si": c.name_si,
         "name_ta": c.name_ta, "category": c.category}
        for c in db.scalars(select(Crop).order_by(Crop.name_en))
    ]


@router.get("/markets", response_model=list[MarketOut])
def list_markets(db: Session = Depends(get_db)):
    return list(db.scalars(select(Market).order_by(Market.name)))


@router.post("/markets", response_model=MarketOut, status_code=201)
def create_market(body: MarketIn, db: Session = Depends(get_db),
                  staff: StaffUser = Depends(require_staff("admin"))):
    market = Market(**body.model_dump())
    db.add(market)
    db.flush()
    audit.record(db, actor_id=staff.id, actor_role=staff.role,
                 action="create", entity="market", entity_id=market.id)
    db.commit()
    return market


# ---- Prices ----
@router.get("/prices", response_model=list[PriceOut])
def list_prices(crop: str | None = None, market: str | None = None,
                date_from: date | None = None, date_to: date | None = None,
                db: Session = Depends(get_db),
                staff: StaffUser = Depends(require_staff("ground_staff", "admin"))):
    return price_svc.list_prices(db, crop_id=crop, market_id=market,
                                 date_from=date_from, date_to=date_to)


@router.post("/prices", response_model=PriceOut, status_code=201)
def create_price(body: PriceIn, db: Session = Depends(get_db),
                 staff: StaffUser = Depends(require_staff("ground_staff", "admin"))):
    market = db.get(Market, body.market_id)
    if not market:
        raise HTTPException(404, "Market not found")
    _check_district(staff, market)
    rec = price_svc.create_price(
        db, market_id=body.market_id, crop_id=body.crop_id,
        price_min=body.price_min, price_max=body.price_max,
        observed_date=body.observed_date, unit=body.unit, currency=body.currency,
        source="staff", entered_by=staff.id,
    )
    audit.record(db, actor_id=staff.id, actor_role=staff.role, action="create",
                 entity="price", entity_id=rec.id,
                 detail=f"{body.crop_id}@{body.market_id} {body.price_min}-{body.price_max}")
    db.commit()
    return rec


@router.post("/prices:bulk", response_model=BulkResult)
async def bulk_prices(file: UploadFile = File(...), db: Session = Depends(get_db),
                      staff: StaffUser = Depends(require_staff("ground_staff", "admin"))):
    """CSV columns: market_id,crop_id,price_min,price_max,observed_date[,unit]."""
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    created, errors = 0, []
    for i, row in enumerate(reader, start=2):  # row 1 = header
        try:
            market = db.get(Market, row["market_id"])
            if not market:
                raise ValueError(f"unknown market_id {row['market_id']}")
            _check_district(staff, market)
            price_svc.create_price(
                db, market_id=row["market_id"], crop_id=row["crop_id"],
                price_min=float(row["price_min"]), price_max=float(row["price_max"]),
                observed_date=date.fromisoformat(row["observed_date"].strip()),
                unit=row.get("unit", "kg"), source="staff", entered_by=staff.id,
            )
            created += 1
        except (KeyError, ValueError, HTTPException) as e:
            errors.append(f"row {i}: {e}")
    audit.record(db, actor_id=staff.id, actor_role=staff.role, action="bulk_create",
                 entity="price", detail=f"created={created} errors={len(errors)}")
    db.commit()
    return BulkResult(created=created, errors=errors)


@router.patch("/prices/{price_id}", response_model=PriceOut)
def patch_price(price_id: str, body: PricePatch, db: Session = Depends(get_db),
                staff: StaffUser = Depends(require_staff("ground_staff", "admin"))):
    rec = db.get(PriceRecord, price_id)
    if not rec:
        raise HTTPException(404, "Price not found")
    _check_district(staff, db.get(Market, rec.market_id))
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(rec, k, v)
    db.flush()
    audit.record(db, actor_id=staff.id, actor_role=staff.role, action="update",
                 entity="price", entity_id=rec.id)
    db.commit()
    return rec


@router.get("/prices/coverage")
def coverage(db: Session = Depends(get_db),
             staff: StaffUser = Depends(require_staff("ground_staff", "admin"))):
    district = None if staff.role == "admin" else (
        staff.district_scope[0] if staff.district_scope else None)
    return price_svc.coverage_today(db, district=district)
