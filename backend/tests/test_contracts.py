"""Agent output contract tests — the shapes the channels/portals rely on."""
from __future__ import annotations

from app.agents import crop as crop_agent
from app.agents import price as price_agent
from app.agents.schemas import CropAgentOutput, PriceAgentOutput
from app.gateway import get_gateway
from app.services import farmer as farmer_svc


def test_price_output_contract(db):
    out = price_agent.run(db, lang="en", crop_text="tomato", gps_lat=7.47, gps_lng=80.62)
    payload = out.model_dump()
    for key in ("agent", "crop", "markets", "trend", "recommendation",
                "confidence", "explanation_localized", "escalate"):
        assert key in payload
    assert payload["agent"] == "price"
    assert payload["trend"] in ("rising", "flat", "falling")
    assert 0.0 <= payload["confidence"] <= 1.0


def _confident_image() -> bytes:
    gw = get_gateway()
    for i in range(1000):
        b = (b"LEAF" + str(i).encode()) * 4
        v = gw.vision_classify(b)
        if v.usable and v.confidence >= 0.6 and v.label != "healthy":
            return b
    raise AssertionError("no confident image found")


def test_crop_output_contract(db):
    farmer = farmer_svc.resolve_or_create(db, phone="+94770000900", created_via="web")
    db.commit()
    out = crop_agent.run(db, farmer=farmer, image_bytes=_confident_image(),
                         image_url="leaf.jpg", lang="en")
    db.commit()
    payload = out.model_dump()
    for key in ("agent", "label", "confidence", "treatment_steps", "inputs_needed",
                "safety", "escalate", "diagnosis_case_id", "explanation_localized"):
        assert key in payload
    assert payload["agent"] == "crop"
    assert payload["escalate"] is False
    assert payload["treatment_doc_id"], "confident diagnosis must cite a KB doc"
    assert len(payload["treatment_steps"]) >= 1


def test_crop_escalation_contract(db):
    farmer = farmer_svc.resolve_or_create(db, phone="+94770000901", created_via="web")
    db.commit()
    out = crop_agent.run(db, farmer=farmer, image_bytes=b"x", image_url="blur.jpg", lang="en")
    db.commit()
    assert isinstance(out, CropAgentOutput)
    assert out.escalate is True
    assert out.diagnosis_case_id
