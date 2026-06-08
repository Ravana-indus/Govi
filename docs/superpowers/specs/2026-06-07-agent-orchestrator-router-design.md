# Agent Orchestrator Router Design

**Goal:** Make Govi route farmer messages reliably between database-backed market prices, crop disease support, and general farming advice.

**Approved approach:** Hybrid deterministic router plus LLM fallback.

**Context:** The backend already has direct `price` and `crop` agents, an orchestrator, a deterministic keyword intent classifier, model gateway providers, guardrails, i18n strings, and tests around price routing and Telegram/web ingestion. The current weakness is that routing is mostly raw keyword classification and general farming questions fall through to generic chat without an explicit farming-advice contract.

## Scope

This design covers the backend conversational brain only:

- Route price questions to the existing Price Intelligence agent.
- Route crop disease/photo/symptom questions to the existing Crop Doctor agent.
- Add an explicit advisory path for general farming tips.
- Keep market price answers strictly database-backed.
- Add a farmer-facing hotline warning to all general farming advice: `0117929494`.

This design does not add external real-time market feeds. "Realtime price" means "latest available staff-entered database price" from the existing `PriceRecord` data model and price portal.

## Route Model

Add a structured router decision object:

```python
@dataclass(frozen=True)
class RouterDecision:
    intent: str
    agent: str | None
    confidence: float
    crop_id: str | None = None
    crop_text: str | None = None
    market_ids: list[str] = field(default_factory=list)
    reason: str = ""
```

Supported intents:

- `language`
- `greeting`
- `price`
- `crop_health`
- `farming_tip`
- `other`

Supported agents:

- `price`
- `crop`
- `advisory`
- `None` for language, greeting, and out-of-scope answers.

## Routing Rules

The router uses deterministic rules first:

1. If the inbound modality has an image, route to `crop_health` with agent `crop`.
2. If the text is a language switch command, route to `language`.
3. If the text contains price or market terms, route to `price`.
4. If the text contains disease, pest, leaf, spot, rot, wilt, insect, fungus, or similar crop-health terms, route to `crop_health`.
5. If the text is a greeting, route to `greeting`.
6. If the text is agriculture-related but not price or disease-specific, route to `farming_tip`.
7. If none of the above match, use a constrained LLM router fallback that may only return `farming_tip` or `other`.

The LLM fallback is intentionally narrow. It must not override explicit price, market, language, or image rules.

## Price Agent Contract

Price answers remain database-only:

- Resolve crop from the current message or recent price context.
- Resolve explicit markets such as Dambulla or Colombo from the current message and recent price context.
- Query latest `PriceRecord` rows through `app.services.price`.
- Return ranked market options and localized explanation.
- If no crop is found, ask which crop.
- If no price data exists, say no recent data is available and create a price escalation.
- Never call the generic chat/advisory LLM to invent price values.

Examples:

- `tomato price in dambulla` routes to `price`, filters to Dambulla DEC, and returns the latest DB price.
- `colombo onion rate` routes to `price`, filters to Colombo Manning Market when present in reference data.
- `beetroot price` routes to `price`; if the database has no beetroot price, it escalates instead of guessing.

## Crop Health Contract

Crop health remains separate from general advice:

- Image messages route directly to Crop Doctor.
- Symptom-only messages route to Crop Doctor intent but ask for a clear, well-lit photo when no image is attached.
- Vision results below the configured confidence threshold escalate.
- Confident disease answers require a validated citable treatment document when possible.
- Unsafe uncertainty escalates to an officer.

Examples:

- `my tomato leaves have black spots` routes to `crop_health` and asks for a photo.
- A leaf image routes to `crop_health` and runs `crop_agent.run`.

## Farming Advisory Contract

Add `backend/app/agents/advisory.py` for general farming tips.

The advisory agent handles questions such as:

- Watering frequency.
- Fertilizer timing at a general level.
- Seedling care.
- Harvest readiness.
- Soil preparation.
- Seasonal planning when it is not asking for market price.

Advisory answer behavior:

- Use recent conversation context and farmer language.
- Prefer validated KB snippets when available.
- If no KB match exists, allow a general LLM answer.
- Keep replies concise for chat.
- Avoid exact pesticide dosage, strong chemical recommendations, or guaranteed outcomes unless supported by validated KB.
- Always append the hotline warning:

```text
This is general guidance. Please confirm with an agriculture officer or call 0117929494.
```

Localized Sinhala and Tamil strings should carry the same meaning and preserve the hotline number.

## Orchestrator Flow

The orchestrator should change from raw `classify_intent` dispatch to structured route dispatch:

1. Resolve farmer, conversation, language, voice transcript, media, and clean text as it does today.
2. Persist inbound message and append farmer memory.
3. Build recent context for follow-up routing.
4. Call the new router with DB session, text, modality, farmer, previous intent, and recent context.
5. Dispatch by `RouterDecision.intent`:
   - `language`: update preference.
   - `greeting`: localized greeting.
   - `price`: call `price_agent.run`.
   - `crop_health`: ask for photo or call `crop_agent.run`.
   - `farming_tip`: call `advisory_agent.run`.
   - `other`: polite agriculture-only fallback.
6. Apply assisted mode to confident agent answers for `price`, `crop`, and `advisory`.
7. Persist outbound message with `agent` and `confidence`.
8. Synthesize voice reply when inbound was voice.

## Error Handling

- Router fallback failure returns `other`, not a crash.
- Advisory LLM failure returns a localized fallback plus the hotline warning.
- Price data absence creates a price escalation and never falls through to advisory.
- Crop uncertainty creates a crop escalation.
- Missing market names simply means "nearest markets" instead of a hard failure.

## Tests

Add focused tests before implementation:

- `tomato price in dambulla` routes to `price`, agent `price`, and returns Dambulla DB market data.
- `tomoto price in colombo` still resolves the crop typo and market.
- `how often should I water tomato plants` routes to `farming_tip`, agent `advisory`, and includes `0117929494`.
- `my tomato leaves have spots` routes to `crop_health` and asks for a photo when no image is attached.
- `beetroot price` remains a price escalation when DB data is missing and does not produce a generic LLM price.
- Assisted mode holds advisory answers the same way it holds confident price/crop answers.
- A non-agriculture question returns the agriculture-only fallback instead of a generic chat answer.

## Files

- Create `backend/app/core/router.py`: structured router and `RouterDecision`.
- Create `backend/app/agents/advisory.py`: general farming advice agent.
- Modify `backend/app/core/orchestrator.py`: dispatch through `RouterDecision`.
- Modify `backend/app/core/intent.py`: keep reusable text/language detectors or move route-specific keyword sets into router.
- Modify `backend/app/i18n/en.json`, `backend/app/i18n/si.json`, and `backend/app/i18n/ta.json`: advisory warning and fallback strings.
- Modify tests under `backend/tests/`: routing, advisory safety warning, price no-fabrication, assisted mode.

## Acceptance Criteria

- Price and market questions route to the price agent and only use database price data.
- Crop disease/image/symptom questions route to crop health handling.
- General farming help routes to advisory and includes `0117929494`.
- Unknown or out-of-scope questions do not receive unconstrained generic chat.
- Existing price, crop, voice, Telegram, and assisted-mode tests still pass.
- New tests cover routing decisions and safety constraints.
