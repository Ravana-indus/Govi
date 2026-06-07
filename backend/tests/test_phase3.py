"""Phase 3 tests: channel webhook, voice pipeline, assisted mode, outcomes."""
from __future__ import annotations

import os
import tempfile

from app.gateway import get_gateway


def _admin(client):
    return client.post("/v1/auth/staff/login",
                       json={"email": "admin@farmingos.lk", "password": "admin123"}
                       ).json()["access_token"]


def _officer(client):
    return client.post("/v1/auth/staff/login",
                       json={"email": "officer@farmingos.lk", "password": "officer123"}
                       ).json()["access_token"]


def _onboard(client, phone, lang="en"):
    otp = client.post("/v1/auth/otp/request", json={"phone": phone}).json()["dev_otp"]
    return client.post("/v1/farmers/onboard", json={
        "phone": phone, "code": otp, "preferred_language": lang,
        "gps_lat": 7.47, "gps_lng": 80.62, "district": "Matale", "consent": True,
    }).json()


# ---- Channel: same brain answers a Telegram-shaped webhook ----
def test_telegram_webhook_answers(client):
    update = {"update_id": 1,
              "message": {"from": {"id": 7788}, "chat": {"id": 7788}, "text": "tomato price"}}
    r = client.post("/v1/webhooks/telegram", json=update)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("method") == "sendMessage"
    assert "Tomato" in body.get("text", "") or "LKR" in body.get("text", "")


def test_general_farming_question_routes_to_advisory(client):
    r = client.post("/v1/messages:ingest", json={
        "channel": "tg",
        "external_user_id": "advisory-user",
        "text": "how often should I water tomato plants",
    })

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"] == "farming_tip"
    assert body["agent"] == "advisory"
    assert "0117929494" in body["reply"]


def test_symptom_text_routes_to_crop_health_and_asks_for_photo(client):
    r = client.post("/v1/messages:ingest", json={
        "channel": "tg",
        "external_user_id": "symptom-user",
        "text": "my tomato leaves have black spots",
    })

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"] == "crop_health"
    assert body["agent"] == "crop"
    assert "photo" in body["reply"].lower()


def test_non_agriculture_question_stays_in_agriculture_scope(client):
    r = client.post("/v1/messages:ingest", json={
        "channel": "tg",
        "external_user_id": "other-user",
        "text": "who won the football match",
    })

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"] == "other"
    assert body["agent"] is None
    assert "agriculture" in body["reply"].lower() or "crop" in body["reply"].lower()


def test_assisted_mode_holds_advisory_answer(client):
    admin = {"Authorization": f"Bearer {_admin(client)}"}
    client.patch("/v1/admin/settings", headers=admin, json={"assisted_mode": True})
    try:
        phone = "+94770003004"
        _onboard(client, phone, lang="en")
        r = client.post("/v1/messages:ingest", json={
            "channel": "web",
            "external_user_id": phone,
            "text": "how often should I water tomato plants",
        }).json()
        assert r["intent"] == "farming_tip"
        assert r["agent"] == "advisory"
        assert r["assisted"] is True
        assert r["escalation_id"]
        off = {"Authorization": f"Bearer {_officer(client)}"}
        queue = client.get("/v1/escalations?status=open", headers=off).json()
        match = [e for e in queue if e["id"] == r["escalation_id"]]
        assert match and match[0]["type"] == "assisted"
        assert match[0]["ai_draft"] and "0117929494" in match[0]["ai_draft"]
    finally:
        client.patch("/v1/admin/settings", headers=admin, json={"assisted_mode": False})



def test_missing_price_data_does_not_fall_back_to_advisory(client):
    r = client.post("/v1/messages:ingest", json={
        "channel": "tg",
        "external_user_id": "missing-price-user",
        "text": "beetroot price",
    })

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"] == "price"
    assert body["agent"] == "price"
    assert body["escalation_id"]
    assert body["payload"]["escalate"] is True
    assert "0117929494" not in body["reply"]

# ---- Voice: inbound voice note is transcribed, routed, and gets a voice reply ----
def _voice_bytes(target="tomato price"):
    gw = get_gateway()
    for i in range(8000):
        b = (b"VOICE" + str(i).encode()) * 4
        if gw.transcribe(b, "en").text == target:
            return b
    raise AssertionError("no audio bytes mapped to target phrase")


def test_voice_ingest_transcribes_and_routes(client):
    phone = "+94770003001"
    _onboard(client, phone)
    audio = _voice_bytes("tomato price")
    path = os.path.join(tempfile.gettempdir(), "voice_test.ogg")
    with open(path, "wb") as fh:
        fh.write(audio)
    r = client.post("/v1/messages:ingest", json={
        "channel": "web", "external_user_id": phone, "modality": "voice",
        "media_url": path}).json()
    assert r["transcript"] == "tomato price"
    assert r["intent"] == "price"
    assert r["reply_media_url"]            # a spoken reply was synthesized
    assert r["payload"]["markets"]


# ---- Assisted mode: confident answer is held for an officer ----
def test_assisted_mode_holds_answer(client):
    admin = {"Authorization": f"Bearer {_admin(client)}"}
    client.patch("/v1/admin/settings", headers=admin, json={"assisted_mode": True})
    try:
        phone = "+94770003002"
        _onboard(client, phone, lang="en")
        r = client.post("/v1/messages:ingest", json={
            "channel": "web", "external_user_id": phone, "text": "tomato price"}).json()
        assert r["assisted"] is True
        assert r["escalation_id"]
        assert "officer" in r["reply"].lower()
        # The officer sees the draft in the queue.
        off = {"Authorization": f"Bearer {_officer(client)}"}
        queue = client.get("/v1/escalations?status=open", headers=off).json()
        match = [e for e in queue if e["id"] == r["escalation_id"]]
        assert match and match[0]["type"] == "assisted"
        assert match[0]["ai_draft"] and "LKR" in match[0]["ai_draft"]
    finally:
        client.patch("/v1/admin/settings", headers=admin, json={"assisted_mode": False})


# ---- Outcomes feed the north-star ----
def test_outcome_bumps_northstar(client):
    admin = {"Authorization": f"Bearer {_admin(client)}"}
    before = client.get("/v1/metrics/northstar", headers=admin).json()["advised"]
    tok = _onboard(client, "+94770003003")
    off = {"Authorization": f"Bearer {_officer(client)}"}
    res = client.post("/v1/outcomes", headers=off, json={
        "farmer_id": tok["farmer_id"], "recommended_action": "sell_now",
        "action_taken": True, "outcome_value": 1500.0})
    assert res.status_code == 201
    after = client.get("/v1/metrics/northstar", headers=admin).json()
    assert after["advised"] == before + 1
    assert after["acted"] >= 1
