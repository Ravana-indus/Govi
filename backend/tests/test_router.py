from __future__ import annotations

from app.core.router import RouterDecision, route


def test_router_price_market_question_uses_price_agent(db):
    decision = route(
        db,
        text="tomato price in dambulla",
        modality="text",
        has_image=False,
        previous_intent=None,
        context_text="",
    )

    assert isinstance(decision, RouterDecision)
    assert decision.intent == "price"
    assert decision.agent == "price"
    assert decision.confidence >= 0.9
    assert decision.crop_text == "tomato price in dambulla"
    assert decision.market_ids


def test_router_crop_symptom_without_image_uses_crop_health(db):
    decision = route(
        db,
        text="my tomato leaves have black spots",
        modality="text",
        has_image=False,
        previous_intent=None,
        context_text="",
    )

    assert decision.intent == "crop_health"
    assert decision.agent == "crop"
    assert decision.confidence >= 0.8


def test_router_image_always_uses_crop_health(db):
    decision = route(
        db,
        text="what is this",
        modality="image",
        has_image=True,
        previous_intent=None,
        context_text="",
    )

    assert decision.intent == "crop_health"
    assert decision.agent == "crop"
    assert decision.reason == "image"


def test_router_general_farming_question_uses_advisory(db):
    decision = route(
        db,
        text="how often should I water tomato plants",
        modality="text",
        has_image=False,
        previous_intent=None,
        context_text="",
    )

    assert decision.intent == "farming_tip"
    assert decision.agent == "advisory"
    assert decision.confidence >= 0.6


def test_router_non_agriculture_question_is_other(db):
    decision = route(
        db,
        text="who won the football match",
        modality="text",
        has_image=False,
        previous_intent=None,
        context_text="",
    )

    assert decision.intent == "other"
    assert decision.agent is None


def test_router_price_followup_preserves_market_context(db):
    decision = route(
        db,
        text="tomoto",
        modality="text",
        has_image=False,
        previous_intent="price",
        context_text="pricing in dambulla tomoto",
    )

    assert decision.intent == "price"
    assert decision.agent == "price"
    assert decision.crop_text == "pricing in dambulla tomoto"
    assert decision.market_ids
