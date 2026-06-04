"""End-to-end HTTP tests via TestClient (mock provider, seeded DB)."""
from __future__ import annotations

from datetime import date


def _ref(client):
    crops = {c["name_en"]: c["id"] for c in client.get("/v1/crops").json()}
    markets = {m["name"]: m["id"] for m in client.get("/v1/markets").json()}
    return crops, markets


def _onboard(client, phone, lang="en", gps=(7.47, 80.62)):
    otp = client.post("/v1/auth/otp/request", json={"phone": phone}).json()["dev_otp"]
    resp = client.post("/v1/farmers/onboard", json={
        "phone": phone, "code": otp, "preferred_language": lang,
        "gps_lat": gps[0], "gps_lng": gps[1], "district": "Matale", "consent": True,
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


def _staff_token(client, email, password):
    r = client.post("/v1/auth/staff/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_onboard_and_price_ingest(client):
    phone = "+94771230001"
    _onboard(client, phone)
    r = client.post("/v1/messages:ingest", json={
        "channel": "web", "external_user_id": phone, "text": "what is the tomato price?",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"] == "price"
    assert body["agent"] == "price"
    assert body["payload"]["markets"], "expected market options"
    assert body["confidence"] and body["confidence"] > 0.5

    conv = client.get(f"/v1/conversations/{body['conversation_id']}").json()
    directions = {m["direction"] for m in conv["messages"]}
    assert {"in", "out"} <= directions


def test_staff_price_entry_and_district_scope(client):
    token = _staff_token(client, "staff@farmingos.lk", "ground123")
    crops, markets = _ref(client)
    hdr = {"Authorization": f"Bearer {token}"}

    # In-scope (Dambulla is in Matale) -> allowed
    ok = client.post("/v1/prices", headers=hdr, json={
        "market_id": markets["Dambulla DEC"], "crop_id": crops["Samba Rice"],
        "price_min": 210, "price_max": 230, "observed_date": date.today().isoformat(),
    })
    assert ok.status_code == 201, ok.text

    # Out-of-scope (Colombo not in Matale) -> 403
    denied = client.post("/v1/prices", headers=hdr, json={
        "market_id": markets["Colombo Manning Market"], "crop_id": crops["Samba Rice"],
        "price_min": 240, "price_max": 260, "observed_date": date.today().isoformat(),
    })
    assert denied.status_code == 403, denied.text


def test_no_data_escalates_then_resolves_after_staff_entry(client):
    phone = "+94771230002"
    _onboard(client, phone)
    crops, markets = _ref(client)

    # Green Chili has no seeded price -> escalate
    first = client.post("/v1/messages:ingest", json={
        "channel": "web", "external_user_id": phone, "text": "green chili price?",
    }).json()
    assert first["payload"]["escalate"] is True
    assert first["escalation_id"]

    # Officer can see the escalation in their queue
    officer = _staff_token(client, "officer@farmingos.lk", "officer123")
    queue = client.get("/v1/escalations?status=open",
                       headers={"Authorization": f"Bearer {officer}"}).json()
    assert any(e["type"] == "price" for e in queue)

    # Staff adds a green chili price...
    staff = _staff_token(client, "staff@farmingos.lk", "ground123")
    client.post("/v1/prices", headers={"Authorization": f"Bearer {staff}"}, json={
        "market_id": markets["Dambulla DEC"], "crop_id": crops["Green Chili"],
        "price_min": 300, "price_max": 340, "observed_date": date.today().isoformat(),
    })

    # ...and now the same question returns a real answer.
    second = client.post("/v1/messages:ingest", json={
        "channel": "web", "external_user_id": phone, "text": "green chili price?",
    }).json()
    assert second["payload"]["escalate"] is False
    assert second["payload"]["markets"]
