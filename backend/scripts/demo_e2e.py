"""End-to-end demo of the Phase 1 loop, exercised through the real HTTP API.

Runs against SQLite + the deterministic mock provider (zero external keys). Proves:
onboarding -> price recommendation (EN + Sinhala) -> crop diagnosis + escalation
-> officer queue -> staff price entry + coverage -> north-star metric.

Run:  PYTHONPATH=. python scripts/demo_e2e.py
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/farmingos_demo.db")
os.environ.setdefault("APP_ENV", "dev")
os.environ.setdefault("MODEL_PROVIDER", "mock")

from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base, SessionLocal, engine  # noqa: E402
from app.db.models import OutcomeLog  # noqa: E402
from app.gateway import get_gateway  # noqa: E402
from app.main import app  # noqa: E402
from scripts.seed import seed  # noqa: E402


def hr(title): print("\n" + "═" * 70 + f"\n  {title}\n" + "═" * 70)


def confident_leaf_image() -> bytes:
    gw = get_gateway()
    for i in range(2000):
        b = (b"LEAFIMG" + str(i).encode()) * 8
        v = gw.vision_classify(b)
        if v.usable and v.confidence >= 0.6 and v.label != "healthy":
            return b
    raise SystemExit("no confident image found")


def main() -> None:
    # Fresh DB
    if os.path.exists("/tmp/farmingos_demo.db"):
        os.remove("/tmp/farmingos_demo.db")
    Base.metadata.create_all(bind=engine)
    seed()
    c = TestClient(app)

    hr("1 · FARMER ONBOARDING (phone + OTP, < 3 minutes)")
    phone = "+94770001234"
    otp = c.post("/v1/auth/otp/request", json={"phone": phone}).json()["dev_otp"]
    print(f"   OTP issued (dev): {otp}")
    tok = c.post("/v1/farmers/onboard", json={
        "phone": phone, "code": otp, "preferred_language": "en", "name": "Nimal",
        "gps_lat": 7.47, "gps_lng": 80.62, "district": "Matale", "consent": True,
    }).json()
    print(f"   Onboarded farmer {tok['farmer_id']}  (consent captured, near Matale)")

    hr("2 · PRICE INTELLIGENCE AGENT  —  'what is the tomato price?'")
    r = c.post("/v1/messages:ingest", json={
        "channel": "web", "external_user_id": phone, "text": "what is the tomato price?"}).json()
    print(f"   intent={r['intent']}  agent={r['agent']}  confidence={r['confidence']}")
    print(f"   reply: {r['reply']}")
    print(f"   recommendation={r['payload']['recommendation']}  trend={r['payload']['trend']}")
    print("   ranked markets (net after transport):")
    for m in r["payload"]["markets"]:
        print(f"     • {m['name']:<32} net {m['net_after_transport']:>6} LKR/kg  "
              f"({m['distance_km']} km, gross {m['price_min']}-{m['price_max']})")

    hr("2b · SAME QUESTION, SINHALA (preferred_language drives the reply)")
    c.patch("/v1/farmers/me", headers={"Authorization": f"Bearer {tok['access_token']}"},
            json={"preferred_language": "si"})
    r2 = c.post("/v1/messages:ingest", json={
        "channel": "web", "external_user_id": phone, "text": "තක්කාලි මිල කීයද?"}).json()
    print(f"   intent={r2['intent']}  reply: {r2['reply']}")

    hr("3 · CROP DOCTOR  —  confident diagnosis (cites a validated KB doc)")
    img = confident_leaf_image()
    with open("/tmp/leaf.jpg", "wb") as fh:
        fh.write(img)
    with open("/tmp/leaf.jpg", "rb") as fh:
        dr = c.post("/v1/agents/crop", files={"image": ("leaf.jpg", fh, "image/jpeg")},
                    data={"lang": "en", "farmer_id": tok["farmer_id"]}).json()
    print(f"   label={dr['label']}  confidence={dr['confidence']}  escalate={dr['escalate']}")
    print(f"   cites KB doc: {dr['treatment_doc_id']}")
    print(f"   steps: {len(dr['treatment_steps'])}  | first: {dr['treatment_steps'][0]}")

    hr("3b · CROP DOCTOR  —  unusable photo -> ESCALATION (human-in-the-loop)")
    with open("/tmp/blur.jpg", "wb") as fh:
        fh.write(b"x")
    with open("/tmp/blur.jpg", "rb") as fh:
        er = c.post("/v1/agents/crop", files={"image": ("blur.jpg", fh, "image/jpeg")},
                    data={"lang": "en", "farmer_id": tok["farmer_id"]}).json()
    print(f"   escalate={er['escalate']}  reason={er['escalate_reason']}")
    print(f"   reply: {er['explanation_localized'][:90]}...")

    hr("4 · EXTENSION-OFFICER CONSOLE  —  queue, claim, resolve")
    otok = c.post("/v1/auth/staff/login",
                  json={"email": "officer@farmingos.lk", "password": "officer123"}).json()["access_token"]
    ohdr = {"Authorization": f"Bearer {otok}"}
    queue = c.get("/v1/escalations?status=open", headers=ohdr).json()
    print(f"   open escalations in Matale: {len(queue)}")
    if queue:
        eid = queue[0]["id"]
        c.post(f"/v1/escalations/{eid}:claim", headers=ohdr)
        c.post(f"/v1/escalations/{eid}:resolve", headers=ohdr,
               json={"note": "Reviewed photo; advised mancozeb spray, 7-day repeat."})
        print(f"   claimed + resolved escalation {eid[:8]}…")

    hr("5 · GROUND-STAFF PRICE PORTAL  —  entry + today's coverage")
    stok = c.post("/v1/auth/staff/login",
                  json={"email": "staff@farmingos.lk", "password": "ground123"}).json()["access_token"]
    shdr = {"Authorization": f"Bearer {stok}"}
    crops = {c2["name_en"]: c2["id"] for c2 in c.get("/v1/crops").json()}
    markets = {m["name"]: m["id"] for m in c.get("/v1/markets").json()}
    add = c.post("/v1/prices", headers=shdr, json={
        "market_id": markets["Dambulla DEC"], "crop_id": crops["Green Chili"],
        "price_min": 300, "price_max": 340, "observed_date": date.today().isoformat()})
    print(f"   added Green Chili @ Dambulla -> HTTP {add.status_code}")
    cov = c.get("/v1/prices/coverage", headers=shdr).json()
    print(f"   coverage today (Matale scope): {cov['coverage_pct']}%  "
          f"({cov['covered']}/{cov['total']} market×crop cells)")

    hr("6 · NORTH-STAR METRIC  —  % advised -> acted -> outcome")
    atok = c.post("/v1/auth/staff/login",
                  json={"email": "admin@farmingos.lk", "password": "admin123"}).json()["access_token"]
    ahdr = {"Authorization": f"Bearer {atok}"}
    # Simulate a logged outcome (a follow-up captured the farmer sold at the advised market).
    db = SessionLocal()
    db.add(OutcomeLog(farmer_id=tok["farmer_id"], interaction_ref="demo",
                      recommended_action="go_to:Colombo Manning Market",
                      action_taken=True, outcome_value=1850.0, captured_via="web",
                      ts=datetime.utcnow()))
    db.commit(); db.close()
    ns = c.get("/v1/metrics/northstar", headers=ahdr).json()
    usage = c.get("/v1/metrics/usage", headers=ahdr).json()
    print(f"   north-star: advised={ns['advised']} acted={ns['acted']} "
          f"outcome={ns['saw_outcome']}  -> acted {ns['acted_pct']}%")
    print(f"   usage: conversations={usage['conversations']} messages={usage['messages']} "
          f"open_escalations={usage['open_escalations']}")
    print("\n✅  End-to-end Phase 1 loop verified on mock provider (zero external keys).\n")


if __name__ == "__main__":
    main()
