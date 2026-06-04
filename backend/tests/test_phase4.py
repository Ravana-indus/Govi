"""Phase 4 tests: i18n parity, PDPA, analytics dashboard, security, content i18n."""
from __future__ import annotations

import hashlib
import hmac

from app.channels.whatsapp import WhatsAppAdapter
from app.core.security import hash_password, verify_password
from app.i18n import _bundle
from app.services import farmer as farmer_svc
from app.services import kb_rag


# ---- Bilingual hardening: no string may ship untranslated ----
def test_i18n_key_parity():
    en, si, ta = set(_bundle("en")), set(_bundle("si")), set(_bundle("ta"))
    assert en, "english bundle must not be empty"
    assert en == si, f"Sinhala missing: {en - si}; extra: {si - en}"
    assert en == ta, f"Tamil missing: {en - ta}; extra: {ta - en}"


def test_kb_prefers_farmer_language(db):
    doc, _ = kb_rag.cited_treatment(db, label="early_blight", symptom_text="",
                                    crop_id=None, language="si")
    assert doc is not None and doc.language == "si"
    doc_en, _ = kb_rag.cited_treatment(db, label="early_blight", symptom_text="",
                                       crop_id=None, language="en")
    assert doc_en is not None and doc_en.language == "en"


# ---- Security ----
def test_password_hash_roundtrip():
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h) is True
    assert verify_password("wrong", h) is False


def test_whatsapp_signature_verification():
    secret, body = "s3cret", b'{"entry":[]}'
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert WhatsAppAdapter.verify_signature(secret, sig, body) is True
    assert WhatsAppAdapter.verify_signature(secret, "sha256=deadbeef", body) is False
    assert WhatsAppAdapter.verify_signature(None, None, body) is True  # unconfigured -> skip


# ---- PDPA ----
def _onboard(client, phone):
    otp = client.post("/v1/auth/otp/request", json={"phone": phone}).json()["dev_otp"]
    return client.post("/v1/farmers/onboard", json={
        "phone": phone, "code": otp, "preferred_language": "en",
        "gps_lat": 7.47, "gps_lng": 80.62, "district": "Matale", "consent": True}).json()


def test_pdpa_export_and_erase(client):
    phone = "+94770004001"
    tok = _onboard(client, phone)
    hdr = {"Authorization": f"Bearer {tok['access_token']}"}
    client.post("/v1/messages:ingest", json={
        "channel": "web", "external_user_id": phone, "text": "tomato price"})

    exported = client.get("/v1/farmers/me/data", headers=hdr).json()
    assert exported["farmer"]["phone"] == phone
    assert isinstance(exported["messages"], list)

    erased = client.post("/v1/farmers/me:erase", headers=hdr)
    assert erased.status_code == 200 and erased.json()["erased"] is True
    after = client.get("/v1/farmers/me/data", headers=hdr).json()
    assert after["farmer"]["phone"].startswith("erased:")
    assert after["farmer"]["name"] is None
    assert after["farmer"]["gps"] == [None, None]


# ---- Analytics dashboard ----
def test_dashboard_metric(client):
    tok = client.post("/v1/auth/staff/login",
                      json={"email": "admin@farmingos.lk", "password": "admin123"}).json()
    hdr = {"Authorization": f"Bearer {tok['access_token']}"}
    d = client.get("/v1/metrics/dashboard", headers=hdr).json()
    for key in ("northstar", "by_intent", "escalations_by_status", "sla_overdue"):
        assert key in d
    assert "advised" in d["northstar"]
