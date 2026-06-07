# Agent Orchestrator Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a hybrid deterministic router plus advisory agent so Govi reliably routes price, crop-health, and general farming-help questions.

**Architecture:** Add a structured `RouterDecision` layer in `backend/app/core/router.py`, then update the orchestrator to dispatch on that decision. Keep price responses database-only through the existing price agent; add `backend/app/agents/advisory.py` for general farming advice with a mandatory hotline warning.

**Tech Stack:** FastAPI backend, SQLAlchemy sessions, dataclasses, existing model gateway, existing i18n JSON bundles, pytest.

---

## File Structure

- Create `backend/app/core/router.py`: hybrid deterministic router, `RouterDecision`, and constrained LLM fallback.
- Create `backend/app/agents/advisory.py`: general farming advice agent with KB-preferred context and hotline warning.
- Modify `backend/app/core/orchestrator.py`: replace raw `classify_intent` dispatch with `router.route`.
- Modify `backend/app/i18n/en.json`: add advisory warning, fallback, and out-of-scope strings.
- Modify `backend/app/i18n/si.json`: add Sinhala advisory warning, fallback, and out-of-scope strings.
- Modify `backend/app/i18n/ta.json`: add Tamil advisory warning, fallback, and out-of-scope strings.
- Create `backend/tests/test_router.py`: route-level tests.
- Create `backend/tests/test_advisory_agent.py`: advisory-agent contract tests.
- Modify `backend/tests/test_phase3.py`: integration tests for advisory routing and assisted mode.

## Dirty Worktree Guard

The repository currently has unrelated unstaged changes in backend and infra files. Before implementation, run:

```bash
git status --short --branch
```

Expected: dirty worktree is visible. Do not revert user changes. Only edit files listed in this plan.

In this workspace, these implementation files already have pre-existing unstaged changes:

- `backend/app/core/orchestrator.py`
- `backend/app/i18n/en.json`
- `backend/app/i18n/si.json`
- `backend/app/i18n/ta.json`
- `backend/tests/test_phase3.py`

For those files, inspect the pre-existing diff before editing and stage only the plan's hunks with `git add -p`. Do not use full-file `git add` for already-dirty files unless the diff contains only work from this plan.

---

### Task 1: Router Unit Tests

**Files:**
- Create: `backend/tests/test_router.py`
- No production code changes in this task.

- [ ] **Step 1: Write failing router tests**

Create `backend/tests/test_router.py`:

```python
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
```

- [ ] **Step 2: Run router tests and verify they fail**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_router.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.router'`.

- [ ] **Step 3: Commit failing tests**

```bash
git add backend/tests/test_router.py
git commit -m "test: add router decision tests"
```

---

### Task 2: Router Implementation

**Files:**
- Create: `backend/app/core/router.py`
- Test: `backend/tests/test_router.py`

- [ ] **Step 1: Implement the router**

Create `backend/app/core/router.py`:

```python
"""Structured message router for the conversational orchestrator."""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re

from sqlalchemy.orm import Session

from app.core.intent import detect_language_command
from app.gateway import get_gateway
from app.services import price as price_svc

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RouterDecision:
    intent: str
    agent: str | None
    confidence: float
    crop_id: str | None = None
    crop_text: str | None = None
    market_ids: list[str] = field(default_factory=list)
    reason: str = ""


_GREETINGS = (
    "hi", "hello", "hey", "good morning", "good evening",
    "ආයුබෝ", "හලෝ", "සුබ", "வணக்கம்", "ஹலோ",
)

_PRICE_TERMS = (
    "price", "prices", "pricing", "rate", "rates", "sell", "market",
    "wholesale", "kg", "dambulla", "manning", "colombo", "nuwara eliya",
    "keppetipola", "මිල", "අගය", "විකුණ", "වෙළඳ",
    "விலை", "சந்தை", "விற்க", "கிலோ",
)

_CROP_HEALTH_TERMS = (
    "disease", "sick", "pest", "blight", "spot", "spots", "leaf", "leaves",
    "rot", "fungus", "yellow", "wilt", "wilting", "insect", "curl",
    "රෝග", "පළිබෝධ", "කොළ", "පැළ", "දිලීර",
    "நோய்", "பூச்சி", "இலை", "செடி", "பூஞ்சை",
)

_FARMING_TERMS = (
    "water", "watering", "irrigate", "irrigation", "fertilizer", "fertiliser",
    "compost", "soil", "seed", "seedling", "plant", "plants", "planting",
    "harvest", "prune", "pruning", "nursery", "field", "farm", "crop",
    "tomato", "onion", "chili", "chilli", "rice", "beetroot",
    "වතුර", "පොහොර", "බීජ", "වගා", "අස්වැන්න", "පස",
    "நீர்", "உரம்", "விதை", "பயிர்", "அறுவடை", "மண்",
)


def _norm(text: str | None) -> str:
    return " ".join((text or "").lower().strip().split())


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    for term in terms:
        term = term.lower()
        if term.isascii():
            if re.search(rf"\b{re.escape(term)}\b", text):
                return True
        elif term in text:
            return True
    return False


def _is_greeting(text: str) -> bool:
    return any(text == term or text.startswith(term) for term in _GREETINGS)


def _fallback_route_with_llm(text: str) -> RouterDecision:
    prompt = (
        "Classify this farmer message as exactly one token: farming_tip or other.\n"
        "Use farming_tip only for agriculture, crop cultivation, irrigation, "
        "soil, fertilizer, harvest, pest prevention, or farm planning questions.\n"
        f"Message: {text}\n"
        "Token:"
    )
    try:
        raw = get_gateway().complete(prompt, max_tokens=4).text.strip().lower()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Router LLM fallback failed: %s", exc)
        raw = ""
    if raw == "farming_tip":
        return RouterDecision(
            intent="farming_tip", agent="advisory", confidence=0.55,
            crop_text=text, reason="llm_fallback",
        )
    return RouterDecision(intent="other", agent=None, confidence=0.4, reason="fallback")


def route(
    db: Session,
    *,
    text: str | None,
    modality: str,
    has_image: bool,
    previous_intent: str | None,
    context_text: str = "",
) -> RouterDecision:
    clean = _norm(text)
    context = _norm(context_text)
    crop = price_svc.resolve_crop(db, clean)
    markets = price_svc.resolve_markets(db, clean)

    if has_image or modality == "image":
        return RouterDecision(
            intent="crop_health", agent="crop", confidence=1.0,
            crop_id=crop.id if crop else None, crop_text=text, reason="image",
        )

    if detect_language_command(clean):
        return RouterDecision(intent="language", agent=None, confidence=1.0, reason="language")

    if clean and (_has_any(clean, _PRICE_TERMS) or markets):
        return RouterDecision(
            intent="price", agent="price", confidence=0.95,
            crop_id=crop.id if crop else None, crop_text=text,
            market_ids=[m.id for m in markets], reason="price_terms",
        )

    if previous_intent == "price":
        context_crop = price_svc.resolve_crop(db, context)
        context_markets = price_svc.resolve_markets(db, context)
        if crop or markets or context_crop or context_markets:
            return RouterDecision(
                intent="price", agent="price", confidence=0.82,
                crop_id=(crop or context_crop).id if (crop or context_crop) else None,
                crop_text=context_text or text,
                market_ids=[m.id for m in (markets or context_markets)],
                reason="price_followup",
            )

    if clean and _has_any(clean, _CROP_HEALTH_TERMS):
        return RouterDecision(
            intent="crop_health", agent="crop", confidence=0.9,
            crop_id=crop.id if crop else None, crop_text=text, reason="crop_health_terms",
        )

    if clean and _is_greeting(clean):
        return RouterDecision(intent="greeting", agent=None, confidence=0.9, reason="greeting")

    if clean and _has_any(clean, _FARMING_TERMS):
        return RouterDecision(
            intent="farming_tip", agent="advisory", confidence=0.7,
            crop_id=crop.id if crop else None, crop_text=text, reason="farming_terms",
        )

    if clean:
        return _fallback_route_with_llm(clean)

    return RouterDecision(intent="other", agent=None, confidence=0.5, reason="empty")
```

- [ ] **Step 2: Run router tests**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_router.py -q
```

Expected: PASS.

- [ ] **Step 3: Commit router implementation**

```bash
git add backend/app/core/router.py
git commit -m "feat: add structured message router"
```

---

### Task 3: Advisory Agent Tests

**Files:**
- Create: `backend/tests/test_advisory_agent.py`
- No production code changes in this task.

- [ ] **Step 1: Write failing advisory-agent tests**

Create `backend/tests/test_advisory_agent.py`:

```python
from __future__ import annotations

from app.agents import advisory
from app.gateway.types import Completion


class _FakeGateway:
    name = "fake"

    def complete(self, prompt: str, *, system: str | None = None, max_tokens: int = 512):
        return Completion(text="Water tomato plants early in the morning and keep the soil evenly moist.")


def test_advisory_appends_hotline_warning(db, monkeypatch):
    monkeypatch.setattr(advisory, "get_gateway", lambda: _FakeGateway())

    out = advisory.run(
        db,
        lang="en",
        question="how often should I water tomato plants",
        crop_id=None,
        context_text="",
    )

    assert out["agent"] == "advisory"
    assert out["confidence"] == 0.65
    assert "Water tomato plants" in out["reply"]
    assert "0117929494" in out["reply"]


def test_advisory_fallback_still_includes_hotline(db, monkeypatch):
    class BrokenGateway:
        name = "broken"

        def complete(self, prompt: str, *, system: str | None = None, max_tokens: int = 512):
            raise RuntimeError("provider down")

    monkeypatch.setattr(advisory, "get_gateway", lambda: BrokenGateway())

    out = advisory.run(
        db,
        lang="en",
        question="how often should I water tomato plants",
        crop_id=None,
        context_text="",
    )

    assert "general farming guidance" in out["reply"].lower()
    assert "0117929494" in out["reply"]
```

- [ ] **Step 2: Run advisory tests and verify they fail**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_advisory_agent.py -q
```

Expected: FAIL with `ImportError` or `ModuleNotFoundError` for `app.agents.advisory`.

- [ ] **Step 3: Commit failing tests**

```bash
git add backend/tests/test_advisory_agent.py
git commit -m "test: add advisory agent contract tests"
```

---

### Task 4: Advisory Agent Implementation

**Files:**
- Create: `backend/app/agents/advisory.py`
- Modify: `backend/app/i18n/en.json`
- Modify: `backend/app/i18n/si.json`
- Modify: `backend/app/i18n/ta.json`
- Test: `backend/tests/test_advisory_agent.py`

- [ ] **Step 1: Add i18n strings**

Add these keys to `backend/app/i18n/en.json` before `onboarding.welcome`:

```json
  "advisory.warning": "This is general guidance. Please confirm with an agriculture officer or call 0117929494.",
  "advisory.fallback": "I can give general farming guidance, but I could not prepare a detailed answer right now.",
  "other.agriculture_only": "I can help with crop prices, crop disease, and farming guidance. Please ask an agriculture question.",
```

Add these keys to `backend/app/i18n/si.json` before `onboarding.welcome`:

```json
  "advisory.warning": "මෙය සාමාන්‍ය මඟ පෙන්වීමක් පමණි. කරුණාකර කෘෂිකර්ම නිලධාරියෙකුගෙන් තහවුරු කරගන්න හෝ 0117929494 අමතන්න.",
  "advisory.fallback": "මට සාමාන්‍ය වගා මඟ පෙන්වීමක් ලබා දිය හැක, නමුත් දැන් විස්තරාත්මක පිළිතුරක් සකස් කළ නොහැක.",
  "other.agriculture_only": "මට භෝග මිල, භෝග රෝග, සහ වගා මඟ පෙන්වීම් ගැන උදව් කළ හැක. කරුණාකර කෘෂිකර්ම ප්‍රශ්නයක් අහන්න.",
```

Add these keys to `backend/app/i18n/ta.json` before `onboarding.welcome`:

```json
  "advisory.warning": "இது பொதுவான வழிகாட்டல் மட்டுமே. தயவுசெய்து வேளாண் அலுவலரிடம் உறுதிப்படுத்தவும் அல்லது 0117929494 அழைக்கவும்.",
  "advisory.fallback": "நான் பொதுவான விவசாய வழிகாட்டலை வழங்க முடியும், ஆனால் இப்போது விரிவான பதிலைத் தயாரிக்க முடியவில்லை.",
  "other.agriculture_only": "நான் பயிர் விலை, பயிர் நோய், மற்றும் விவசாய வழிகாட்டலில் உதவ முடியும். தயவுசெய்து வேளாண்மை தொடர்பான கேள்வியை கேளுங்கள்.",
```

- [ ] **Step 2: Implement advisory agent**

Create `backend/app/agents/advisory.py`:

```python
"""General farming advice agent.

This agent is for cultivation help that is not market pricing and not crop
disease diagnosis. It can use a general LLM answer, but always labels the answer
as general guidance and gives the farmer the hotline for confirmation.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.gateway import get_gateway
from app.i18n import localize
from app.services import kb_rag

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are Govi, a Sri Lankan farming assistant. Answer only agriculture "
    "cultivation questions. Keep the answer concise for chat. Do not invent "
    "market prices. Do not give exact pesticide dosage or guaranteed outcomes "
    "unless the provided context explicitly supports it."
)


def _warning(lang: str) -> str:
    return localize("advisory.warning", lang)


def _with_warning(text: str, lang: str) -> str:
    base = (text or "").strip() or localize("advisory.fallback", lang)
    warning = _warning(lang)
    if "0117929494" in base:
        return base
    return f"{base}\n\n{warning}"


def _kb_context(db: Session, *, question: str, crop_id: str | None, lang: str) -> str:
    hits = kb_rag.retrieve(db, question, crop_id=crop_id, language=lang, k=2)
    if not hits and lang != "en":
        hits = kb_rag.retrieve(db, question, crop_id=crop_id, language="en", k=2)
    snippets = [chunk.chunk_text for chunk, _score in hits]
    return "\n\n".join(snippets)


def run(
    db: Session,
    *,
    lang: str,
    question: str,
    crop_id: str | None = None,
    context_text: str = "",
) -> dict:
    kb_context = _kb_context(db, question=question, crop_id=crop_id, lang=lang)
    prompt = (
        f"Recent farmer context:\n{context_text or '-'}\n\n"
        f"Validated knowledge context:\n{kb_context or '-'}\n\n"
        f"Farmer question:\n{question}\n\n"
        "Answer:"
    )
    try:
        text = get_gateway().complete(prompt, system=_SYSTEM, max_tokens=220).text
    except Exception as exc:  # noqa: BLE001
        logger.warning("Advisory agent failed: %s", exc)
        text = localize("advisory.fallback", lang)
    return {
        "agent": "advisory",
        "reply": _with_warning(text, lang),
        "confidence": 0.65,
        "payload": {"source": "general_guidance", "has_kb_context": bool(kb_context)},
    }
```

- [ ] **Step 3: Run advisory tests**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_advisory_agent.py -q
```

Expected: PASS.

- [ ] **Step 4: Validate i18n JSON**

Run:

```bash
python -m json.tool backend/app/i18n/en.json >/tmp/en.json
python -m json.tool backend/app/i18n/si.json >/tmp/si.json
python -m json.tool backend/app/i18n/ta.json >/tmp/ta.json
```

Expected: all three commands exit 0.

- [ ] **Step 5: Commit advisory implementation**

```bash
git add backend/app/agents/advisory.py
git add -p backend/app/i18n/en.json backend/app/i18n/si.json backend/app/i18n/ta.json
git commit -m "feat: add farming advisory agent"
```

---

### Task 5: Orchestrator Integration Tests

**Files:**
- Modify: `backend/tests/test_phase3.py`
- Production files unchanged in this task.

- [ ] **Step 1: Add failing integration tests**

Append these tests after `test_price_query_uses_requested_major_market` in `backend/tests/test_phase3.py`:

```python
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
```

- [ ] **Step 2: Run integration tests and verify they fail**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_phase3.py -q
```

Expected: FAIL because the orchestrator still dispatches from `classify_intent` and has no advisory path.

- [ ] **Step 3: Commit failing integration tests**

```bash
git add -p backend/tests/test_phase3.py
git commit -m "test: add orchestrator routing integration tests"
```

---

### Task 6: Orchestrator Dispatch Refactor

**Files:**
- Modify: `backend/app/core/orchestrator.py`
- Test: `backend/tests/test_phase3.py`
- Test: `backend/tests/test_price_agent.py`
- Test: `backend/tests/test_router.py`
- Test: `backend/tests/test_advisory_agent.py`

- [ ] **Step 1: Update imports**

In `backend/app/core/orchestrator.py`, change:

```python
from app.agents import crop as crop_agent
from app.agents import price as price_agent
from app.core import guardrails, memory
from app.core.intent import classify_intent, detect_language_command, detect_text_language
```

to:

```python
from app.agents import advisory as advisory_agent
from app.agents import crop as crop_agent
from app.agents import price as price_agent
from app.core import guardrails, memory, router
from app.core.intent import detect_language_command, detect_text_language
```

- [ ] **Step 2: Replace raw intent classification with route decision**

In `handle`, replace the block from:

```python
    intent = classify_intent(clean_text, has_image=has_image)
    current_crop = price_svc.resolve_crop(db, clean_text)
    current_markets = price_svc.resolve_markets(db, clean_text)
    crop_id: str | None = None
    price_text = clean_text
    if previous_intent == "price":
        context_text = _recent_farmer_context(conv.id)
        if intent == "other" and price_svc.resolve_crop(db, context_text):
            intent = "price"
        if intent == "price" and current_crop and not current_markets:
            crop_id = current_crop.id
            price_text = context_text
        elif intent == "price" and not current_crop:
            price_text = context_text
```

with:

```python
    context_text = _recent_farmer_context(conv.id)
    decision = router.route(
        db,
        text=clean_text,
        modality=modality,
        has_image=has_image,
        previous_intent=previous_intent,
        context_text=context_text,
    )
    intent = decision.intent
    crop_id = decision.crop_id
    price_text = decision.crop_text or clean_text
```

- [ ] **Step 3: Add advisory and scoped other dispatch**

In the dispatch section, keep language, greeting, price, and crop branches, then replace the final `else` branch:

```python
    else:
        # --- greeting / other: generate a real LLM reply ---
        reply = _llm_chat(gw, conv.id, clean_text or "", lang)
```

with:

```python
    elif intent == "farming_tip":
        agent_name = "advisory"
        out = advisory_agent.run(
            db,
            lang=lang,
            question=clean_text or "",
            crop_id=crop_id,
            context_text=context_text,
        )
        reply = out["reply"]
        confidence = out["confidence"]
        payload = out["payload"]
    else:
        reply = localize("other.agriculture_only", lang)
```

- [ ] **Step 4: Include advisory in assisted mode**

Change:

```python
    if (agent_name in ("price", "crop") and escalation_id is None
            and bool(settings_svc.get(db, "assisted_mode"))):
```

to:

```python
    if (agent_name in ("price", "crop", "advisory") and escalation_id is None
            and bool(settings_svc.get(db, "assisted_mode"))):
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_router.py tests/test_advisory_agent.py tests/test_price_agent.py tests/test_phase3.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit orchestrator integration**

```bash
git add -p backend/app/core/orchestrator.py
git commit -m "feat: route conversations through structured router"
```

---

### Task 7: Price No-Fabrication Regression Tests

**Files:**
- Modify: `backend/tests/test_phase3.py`
- Test: existing price and phase tests.

- [ ] **Step 1: Add explicit no-fabrication test**

Append this test near the other price route tests in `backend/tests/test_phase3.py`:

```python
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
```

- [ ] **Step 2: Run price regression tests**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_price_agent.py tests/test_phase3.py -q
```

Expected: PASS.

- [ ] **Step 3: Commit regression test**

```bash
git add -p backend/tests/test_phase3.py
git commit -m "test: prevent price fallback fabrication"
```

---

### Task 8: Full Verification

**Files:**
- No planned edits.

- [ ] **Step 1: Run the backend test suite**

Run:

```bash
cd backend
PYTHONPATH=. pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Inspect git diff**

Run:

```bash
git diff --stat HEAD
git status --short
```

Expected: only intentional uncommitted changes remain. If this plan was executed with per-task commits, `git diff --stat HEAD` should be empty for the route/advisory work.

- [ ] **Step 3: Manual smoke test through HTTP**

If a local API server is already running, send:

```bash
curl -s -X POST http://127.0.0.1:8000/v1/messages:ingest \
  -H 'Content-Type: application/json' \
  -d '{"channel":"tg","external_user_id":"smoke-advisory","text":"how often should I water tomato plants"}'
```

Expected response fields:

```json
{
  "intent": "farming_tip",
  "agent": "advisory"
}
```

Expected response text contains `0117929494`.

If no local server is running, skip the curl smoke test because the pytest integration tests already exercise the same route through `TestClient`.

---

## Self-Review Checklist

- Spec coverage: price, crop health, farming tips, hotline warning, assisted mode, and no price fabrication are covered.
- Placeholder scan: no task contains incomplete implementation instructions.
- Type consistency: `RouterDecision.intent`, `agent`, `crop_id`, `crop_text`, and `market_ids` are used consistently across router tests and orchestrator integration.
- Scope: all changes stay inside backend routing/advisory/i18n/tests and do not add external price feeds.
