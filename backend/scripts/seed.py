"""Seed deterministic demo data.

Idempotent for reference data (crops, markets, staff, KB) and always rebuilds
PriceRecords relative to today so the 7-day trend is meaningful on any run date.

Run:  PYTHONPATH=. python scripts/seed.py
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.base import SessionLocal, init_db  # noqa: E402
from app.db.models import (  # noqa: E402
    Crop, KnowledgeDoc, Market, PriceRecord, StaffUser,
)
from app.services import kb_rag  # noqa: E402

CROPS = [
    ("Tomato", "තක්කාලි", "தக்காளி", "vegetable"),
    ("Big Onion", "ලොකු ලූනු", "பெரிய வெங்காயம்", "vegetable"),
    ("Carrot", "කැරට්", "கேரட்", "vegetable"),
    ("Cabbage", "ගෝවා", "முட்டைக்கோஸ்", "vegetable"),
    ("Green Chili", "අමු මිරිස්", "பச்சை மிளகாய்", "vegetable"),
    ("Samba Rice", "සම්බා සහල්", "சம்பா அரிசி", "paddy"),
    ("Beetroot", "බීට්රූට්", "பீட்ரூட்", "vegetable"),  # intentionally never priced
]

MARKETS = [
    ("Dambulla DEC", "DEC", "Matale", 7.8742, 80.6511),
    ("Colombo Manning Market", "DEC", "Colombo", 6.9388, 79.8542),
    ("Nuwara Eliya Economic Centre", "wholesale", "Nuwara Eliya", 6.9497, 80.7891),
    ("Keppetipola DEC", "DEC", "Badulla", 6.8966, 80.9470),
]

STAFF = [
    ("Ground Staff (Matale)", "staff@farmingos.lk", "ground_staff", ["Matale"], "ground123"),
    ("Extension Officer (Matale)", "officer@farmingos.lk", "extension_officer", ["Matale"], "officer123"),
    ("Admin", "admin@farmingos.lk", "admin", [], "admin123"),
]

TOMATO_TREATMENT = """Early blight (Alternaria solani) and late blight are common
fungal diseases of tomato in Sri Lanka, showing brown concentric spots on lower
leaves that spread upward in humid weather.

Steps:
1. Remove and destroy affected lower leaves; do not compost them.
2. Improve airflow — stake plants and widen spacing.
3. Avoid overhead watering; water at the base in the morning.
4. Apply a recommended fungicide (e.g. mancozeb or chlorothalonil) following the
   label dosage, repeating every 7-10 days in wet weather.
5. Rotate away from solanaceous crops (tomato, potato, brinjal) next season.

Inputs:
- Mancozeb 80% WP or chlorothalonil
- Knapsack sprayer, gloves, face mask
- Stakes and twine for support
"""

TOMATO_LEAFCURL = """Tomato leaf curl virus (begomovirus) is spread by whitefly.
Leaves curl upward, thicken, and yellow at the margins; plants stunt and set few
fruit. There is no cure once infected — management targets the whitefly vector and
removal of sources.

Steps:
1. Uproot and bag severely infected plants early to remove virus sources.
2. Control whitefly: yellow sticky traps and a recommended insecticide rotation.
3. Use virus-tolerant varieties and certified clean seedlings next planting.
4. Mulch and keep field borders weed-free to reduce whitefly shelter.

Inputs:
- Yellow sticky traps
- Recommended whitefly insecticide (rotate modes of action)
- Tolerant tomato variety seed
"""

ONION_BLOTCH = """Purple blotch (Alternaria porri) of big onion shows small white
flecks that enlarge into sunken purple lesions with concentric rings on leaves,
worsening in wet, humid weather and reducing bulb size.

Steps:
1. Remove crop debris and rotate away from onion/garlic for 2-3 seasons.
2. Improve drainage and avoid excess nitrogen.
3. Apply a protectant fungicide (mancozeb) on a 7-10 day schedule in wet weather.
4. Cure harvested bulbs well before storage.

Inputs:
- Mancozeb 80% WP
- Knapsack sprayer, gloves, face mask
"""

TOMATO_TREATMENT_SI = """තක්කාලි වල early blight සහ late blight යනු තෙතමනය සහිත
කාලගුණයේ පහළ කොළ වල දුඹුරු ලප ඇති කරන සුලභ දිලීර රෝග වේ.

Steps:
1. රෝගී පහළ කොළ ඉවත් කර විනාශ කරන්න; ඒවා කොම්පෝස්ට් කිරීමෙන් වළකින්න.
2. වාතාශ්‍රය වැඩි කරන්න — පැළ ඔප්පු කර පරතරය වැඩි කරන්න.
3. උදෑසන මුල අසලින් ජලය දෙන්න; උඩින් ජලය දැමීමෙන් වළකින්න.
4. නිර්දේශිත දිලීර නාශකයක් (mancozeb) ලේබලය අනුව දින 7-10 කට වරක් යොදන්න.

Inputs:
- Mancozeb 80% WP
- ඉසින යන්ත්‍රය, අත්වැසුම්, මුව ආවරණ
"""

FERTILIZER_GENERAL = """Balanced fertilizer guidance for vegetables: base your
program on a soil test where possible. Split nitrogen into 2-3 applications to
reduce leaching; apply phosphorus at planting; supply potassium for fruit quality.
Incorporate compost or well-rotted manure to build soil organic matter. Avoid over-
application of urea, which can worsen some leaf diseases and burn roots.
"""


def get_or_create(db, model, defaults=None, **keys):
    obj = db.scalar(select(model).filter_by(**keys))
    if obj:
        return obj, False
    obj = model(**keys, **(defaults or {}))
    db.add(obj)
    db.flush()
    return obj, True


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        crops = {}
        for en, si, ta, cat in CROPS:
            c, _ = get_or_create(db, Crop, name_en=en,
                                 defaults={"name_si": si, "name_ta": ta, "category": cat})
            crops[en] = c

        markets = {}
        for name, mtype, district, lat, lng in MARKETS:
            m, _ = get_or_create(db, Market, name=name,
                                 defaults={"type": mtype, "district": district,
                                           "gps_lat": lat, "gps_lng": lng})
            markets[name] = m

        for name, email, role, scope, pw in STAFF:
            s = db.scalar(select(StaffUser).filter_by(email=email))
            if not s:
                s = StaffUser(name=name, email=email, role=role,
                              district_scope=scope, password_hash=hash_password(pw),
                              status="active")
                db.add(s)
        db.flush()

        # Knowledge docs (validated -> retrievable + indexed). Idempotent by title.
        DOCS = [
            ("Tomato blight management", TOMATO_TREATMENT, "Tomato", "disease", "en"),
            ("තක්කාලි දිලීර රෝග කළමනාකරණය", TOMATO_TREATMENT_SI, "Tomato", "disease", "si"),
            ("Tomato leaf curl virus management", TOMATO_LEAFCURL, "Tomato", "disease", "en"),
            ("Big Onion purple blotch management", ONION_BLOTCH, "Big Onion", "disease", "en"),
            ("Balanced fertilizer guidance for vegetables", FERTILIZER_GENERAL, None, "fertilizer", "en"),
        ]
        for title, body, crop_name, topic, language in DOCS:
            if db.scalar(select(KnowledgeDoc).filter_by(title=title)):
                continue
            kb_rag.ingest_text(
                db, title=title, body=body,
                crop_id=crops[crop_name].id if crop_name else None,
                topic=topic, language=language,
                source="Dept. of Agriculture (demo)", validated_by="agronomy_partner",
                status="validated")

        # Prices — rebuilt relative to today so trends are always live.
        db.query(PriceRecord).delete()
        today = date.today()

        def price(market, crop, d_ago, pmin, pmax):
            db.add(PriceRecord(
                market_id=markets[market].id, crop_id=crops[crop].id,
                price_min=pmin, price_max=pmax, observed_date=today - timedelta(days=d_ago),
                unit="kg", currency="LKR", source="staff", confidence=1.0))

        # Tomato — rising at Dambulla, steady (higher) at Colombo, mid at Nuwara Eliya
        price("Dambulla DEC", "Tomato", 5, 118, 130)
        price("Dambulla DEC", "Tomato", 2, 124, 136)
        price("Dambulla DEC", "Tomato", 0, 130, 145)
        price("Colombo Manning Market", "Tomato", 4, 165, 185)
        price("Colombo Manning Market", "Tomato", 1, 168, 186)
        price("Colombo Manning Market", "Tomato", 0, 170, 188)
        price("Nuwara Eliya Economic Centre", "Tomato", 0, 140, 160)
        # Big Onion
        price("Dambulla DEC", "Big Onion", 0, 200, 230)
        price("Colombo Manning Market", "Big Onion", 0, 230, 260)
        # Carrot / Cabbage (Nuwara Eliya up-country)
        price("Nuwara Eliya Economic Centre", "Carrot", 0, 150, 175)
        price("Nuwara Eliya Economic Centre", "Cabbage", 0, 90, 110)

        db.commit()
        print("Seed complete:")
        print(f"  crops={db.scalar(select(__import__('sqlalchemy').func.count()).select_from(Crop))}"
              f" markets={len(MARKETS)} staff={len(STAFF)}")
        print("  Staff logins: staff@farmingos.lk/ground123, "
              "officer@farmingos.lk/officer123, admin@farmingos.lk/admin123")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
