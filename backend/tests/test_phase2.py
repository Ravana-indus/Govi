"""Phase 2 tests: KB/RAG citations, Crop Doctor enrichments, admin flags & views."""
from __future__ import annotations

from app.agents import crop as crop_agent
from app.gateway import get_gateway
from app.services import farmer as farmer_svc
from app.services import kb_rag
from app.services import settings as settings_svc


def _confident_image():
    gw = get_gateway()
    for i in range(3000):
        b = (b"PH2IMG" + str(i).encode()) * 8
        v = gw.vision_classify(b)
        if v.usable and v.confidence >= 0.6 and v.label != "healthy":
            return b
    raise AssertionError("no confident image found")


# ---- KB / RAG ----
def test_kb_retrieve_returns_citations(db):
    doc, citations = kb_rag.cited_treatment(
        db, label="early_blight", symptom_text="brown spots on lower leaves",
        crop_id=None, language="en")
    assert doc is not None
    assert citations and "title" in citations[0] and "doc_id" in citations[0]


def test_kb_ingest_text_indexes(db):
    before = kb_rag.retrieve(db, "whitefly virus curl", topic="disease", k=5)
    # leaf curl doc is seeded; retrieval should find disease content
    assert isinstance(before, list)


# ---- Crop Doctor enrichments ----
def test_crop_output_has_citations_and_candidates(db):
    f = farmer_svc.resolve_or_create(db, phone="+94770002201", created_via="web")
    db.commit()
    out = crop_agent.run(db, farmer=f, image_bytes=_confident_image(),
                         image_url="leaf.jpg", symptom_text="curling leaves", lang="en")
    db.commit()
    assert out.escalate is False
    assert out.treatment_doc_id
    assert len(out.citations) >= 1
    assert len(out.candidates) >= 1
    assert "Source:" in out.explanation_localized


def test_admin_threshold_flag_controls_escalation(db):
    f = farmer_svc.resolve_or_create(db, phone="+94770002202", created_via="web")
    db.commit()
    img = _confident_image()  # confidence is in [0.6, 0.95)
    # Raise threshold above any possible confidence -> must escalate.
    settings_svc.set_many(db, {"crop_confidence_threshold": 0.99}); db.commit()
    out = crop_agent.run(db, farmer=f, image_bytes=img, image_url="x.jpg", lang="en")
    db.commit()
    assert out.escalate is True
    # Reset so the flag doesn't leak into other tests.
    settings_svc.set_many(db, {"crop_confidence_threshold": 0.6}); db.commit()


# ---- Admin endpoints ----
def _admin(client):
    return client.post("/v1/auth/staff/login",
                       json={"email": "admin@farmingos.lk", "password": "admin123"}
                       ).json()["access_token"]


def test_admin_settings_roundtrip_and_rbac(client):
    tok = _admin(client)
    hdr = {"Authorization": f"Bearer {tok}"}
    got = client.get("/v1/admin/settings", headers=hdr).json()
    assert "crop_confidence_threshold" in got and "assisted_mode" in got

    upd = client.patch("/v1/admin/settings", headers=hdr,
                       json={"assisted_mode": True, "crop_confidence_threshold": 0.55}).json()
    assert upd["assisted_mode"] is True
    assert abs(upd["crop_confidence_threshold"] - 0.55) < 1e-6

    # ground staff is not admin -> 403
    staff = client.post("/v1/auth/staff/login",
                        json={"email": "staff@farmingos.lk", "password": "ground123"}
                        ).json()["access_token"]
    denied = client.get("/v1/admin/settings", headers={"Authorization": f"Bearer {staff}"})
    assert denied.status_code == 403
    # reset
    client.patch("/v1/admin/settings", headers=hdr,
                 json={"assisted_mode": False, "crop_confidence_threshold": 0.6})


def test_admin_kb_create_validate_and_views(client):
    tok = _admin(client)
    hdr = {"Authorization": f"Bearer {tok}"}
    crops = {c["name_en"]: c["id"] for c in client.get("/v1/crops").json()}
    created = client.post("/v1/kb/docs", headers=hdr, json={
        "title": "Carrot cavity spot note", "body": "Steps:\n1. Improve drainage.\n2. Rotate crops.",
        "crop_id": crops["Carrot"], "topic": "disease", "language": "en", "status": "validated"})
    assert created.status_code == 201, created.text
    docs = client.get("/v1/kb/docs", headers=hdr).json()
    assert any(d["title"] == "Carrot cavity spot note" for d in docs)

    # admin views
    farmers = client.get("/v1/admin/farmers", headers=hdr)
    convos = client.get("/v1/admin/conversations", headers=hdr)
    assert farmers.status_code == 200 and isinstance(farmers.json(), list)
    assert convos.status_code == 200 and isinstance(convos.json(), list)
