# FarmingOS — System Architecture & Build Blueprint

## 0 · How to read this

This is a **build-ready specification** for an implementing engineer or coding agent. It is deliberately decision-complete: where a choice exists, a default is named so the builder can proceed without blocking. Anything marked **[LATER]** is post-MVP.

**What we are building:** a multi-channel AI assistant for smallholder farmers with two agents — a **Price Intelligence** agent and a **Crop Doctor** agent — reachable via **web, WhatsApp, and Telegram**, backed by a **knowledge base**, a **farmer database**, an **onboarding flow**, and operator **portals** (ground-staff price updates, admin/KB, extension-officer escalations).

**Design principles (non-negotiable, enforce in every component):**
1. Voice-first and bilingual (Sinhala + Tamil) — text is the fallback, not the default.
2. Offline/low-bandwidth tolerant — assume a low-end Android on 3G.
3. Confidence-aware with human-in-the-loop — never emit risky advice at low confidence; escalate.
4. Verifiable outcome over information — every interaction should drive and log a concrete action.
5. Farmers never pay and own their data — monetize the ecosystem; consent-first.
6. Channel-agnostic core — the brain is independent of WhatsApp/Telegram/web.

## 1 · System Architecture

Layered, channel-agnostic. One core brain; thin channel adapters; clear service boundaries.

```
 Farmers                         Operators
  │  (WhatsApp / Telegram / Web)  │ (Web portals)
  ▼                               ▼
┌──────────────────┐      ┌────────────────────────┐
│  Channel Adapters │      │  Portal Frontends (SPA) │
│  WA · TG · WebChat│      │  price · admin · officer│
└────────┬──────────┘      └───────────┬────────────┘
         │  normalized Message            │ REST/JSON
         ▼                                ▼
        ┌─────────────────────────────────────┐
        │            API Gateway (REST)         │
        │      auth · rate-limit · i18n         │
        └───────────────┬─────────────────────┘
                        ▼
        ┌─────────────────────────────────────┐
        │         Orchestrator / Router         │
        │  intent → agent · context · memory    │
        └───┬───────────────┬─────────────┬────┘
            ▼               ▼             ▼
     ┌───────────┐   ┌────────────┐  ┌──────────────┐
     │ Price Agent│   │Crop Doctor │  │ KB / RAG svc │
     └─────┬──────┘   └─────┬──────┘  └──────┬───────┘
           ▼                ▼                ▼
     ┌──────────────────────────────────────────────┐
     │      Domain Services & Model Gateway          │
     │ farmer · price · diagnosis · escalation · LLM │
     │ ASR/TTS · vision · embeddings (pluggable)     │
     └───────────────────────┬──────────────────────┘
                             ▼
     ┌──────────────────────────────────────────────┐
     │  Data: Postgres(+pgvector) · Redis · S3(images)│
     └──────────────────────────────────────────────┘
```

**Flow:** an inbound message (text/voice/image) is normalized by a channel adapter → gateway authenticates and resolves the farmer → orchestrator classifies intent, loads conversation context, and routes to an agent → the agent calls domain services + the model gateway (with RAG) → response is localized and returned through the same adapter. Every turn is persisted; low-confidence turns create an **Escalation** for a human officer.

## 2 · Tech Stack (recommended defaults)

| Layer | Default | Why | Acceptable alt |
|---|---|---|---|
| Backend | **Python 3.11 + FastAPI** | async, great AI/ML ecosystem, fast to build | Node + NestJS |
| DB | **PostgreSQL 15 + pgvector** | relational + native vector search for RAG in one store | Postgres + Qdrant |
| Cache/queue | **Redis** | session/context cache, rate limits, simple job queue | RabbitMQ |
| Object storage | **S3-compatible** (AWS S3 / Cloudflare R2) | crop images, voice notes | MinIO (self-host) |
| LLM | **Provider-agnostic via Model Gateway** | swap models; avoid lock-in | OpenAI / Anthropic / Gemini / local |
| Vision (disease) | Vision-LLM or fine-tuned classifier behind an adapter | start with a vision-LLM, graduate to a trained model | PlantVillage-trained CNN |
| ASR / TTS | Sinhala+Tamil-capable speech service behind adapter | voice-first requirement | Google STT/TTS, Bhashini-style |
| Embeddings | Multilingual embedding model | bilingual RAG | any multilingual encoder |
| Web frontends | **React + Vite** (or Next.js) SPA(s) | portals + web chat | SvelteKit |
| Auth | **JWT access/refresh + OTP** (phone) | farmers have phones not emails | OAuth for staff |
| Channels | **WhatsApp Cloud API**, **Telegram Bot API** | official, documented | 360dialog (WA BSP) |
| Infra | Docker + a managed container host | reproducible deploys | Fly.io / Render / AWS ECS |
| Observability | structured logging + OpenTelemetry + Sentry | debug agents, track cost | — |

**Repo shape:** a monorepo with `backend/`, `web/` (frontends), `infra/`, `docs/`. Keep the **core brain** (orchestrator + agents + services) free of any channel SDK import.

## 3 · Data Model

Core entities (Postgres). PK = uuid, plus `created_at`/`updated_at` everywhere.

**Farmer** — `id, phone (unique), name, preferred_language (si|ta|en), gps_lat, gps_lng, district, dsd (division), village, farmer_org_id?, consent_data (bool), consent_ts, status, created_via (wa|tg|web|staff)`

**Plot** — `id, farmer_id→Farmer, name, area_value, area_unit, soil_type?, irrigation_type?, gps_lat, gps_lng`

**PlotCrop** — `id, plot_id→Plot, crop_id→Crop, season (maha|yala|perennial), planted_date?, expected_harvest_date?, stage`

**Crop** — `id, name_en, name_si, name_ta, category (vegetable|paddy|tea|fruit|spice), default_calendar_ref?`

**Market** — `id, name, type (farmgate|wholesale|retail|DEC), district, gps_lat, gps_lng`

**PriceRecord** — `id, market_id→Market, crop_id→Crop, price_min, price_max, unit (kg), currency (LKR), observed_date, source (staff|feed|api), entered_by→StaffUser?, confidence`

**KnowledgeDoc** — `id, title, body, crop_id?, topic (pest|disease|fertilizer|calendar|subsidy|general), language, source, validated_by?, version, status`

**KnowledgeChunk** — `id, doc_id→KnowledgeDoc, chunk_text, embedding vector, ordinal`

**Conversation** — `id, farmer_id→Farmer, channel (wa|tg|web), state, last_intent, opened_at, closed_at?`

**Message** — `id, conversation_id→Conversation, direction (in|out), modality (text|voice|image), content_text, media_url?, transcript?, agent (price|crop|router), confidence?, tokens?, cost?`

**DiagnosisCase** — `id, farmer_id, plot_crop_id?, image_url, model_label, model_confidence, treatment_doc_id?, status (auto_resolved|escalated|officer_resolved), outcome (saved|lost|unknown)`

**Escalation** — `id, conversation_id, farmer_id, type (price|crop|other), reason, assigned_officer_id?, status (open|claimed|resolved), resolution_note, sla_due`

**StaffUser** — `id, name, phone/email, role (ground_staff|extension_officer|admin), district_scope[], password_hash/otp, status`

**OutcomeLog** — `id, farmer_id, interaction_ref, recommended_action, action_taken (bool), outcome_value?, captured_via, ts` — powers the north-star metric.

**[LATER]:** `Subsidy`, `Buyer`, `Order`, `CreditProfile`, `InsurancePolicy`.

**Indexes:** `PriceRecord(crop_id, market_id, observed_date desc)`; `KnowledgeChunk` ivfflat on `embedding`; `Farmer(phone)`; `Escalation(status, district)`.

## 4 · Agent Layer (orchestrator, agents, RAG, guardrails)

**Model Gateway** — a single internal interface every agent uses: `complete(prompt, tools)`, `embed(text)`, `transcribe(audio, lang)`, `speak(text, lang)`, `vision_classify(image)`. Each method is a **pluggable provider** selected by env var, with a **deterministic mock provider** for offline/dev. This is the seam that keeps the system provider-agnostic and testable.

**Orchestrator / Router** — input: normalized message + farmer context + recent conversation memory. Steps: (1) if media is an image → route to Crop Doctor; (2) else classify intent (price | crop_health | calendar[LATER] | input_cost[LATER] | greeting | other) via a fast LLM/intent classifier; (3) attach context (farmer profile, plot/crops, location); (4) dispatch to the agent; (5) apply guardrails; (6) localize + return. Maintain short-term memory in Redis keyed by conversation.

**Price Intelligence Agent** — 
Inputs: crop (resolved/he asks), quantity?, farmer GPS. 
Logic: query latest `PriceRecord` for the crop across nearest N markets; compute net price after estimated transport from GPS→market; compute 7-day trend; produce a recommendation (sell now / hold / which market). 
Guardrail: if data is stale (> X days) or sparse → lower confidence, say so, do **not** fabricate a forecast for perishables. 
Output contract:
```
{ "agent":"price", "crop":"tomato",
  "markets":[{"name":"Dambulla DEC","price_min":120,"price_max":150,"net_after_transport":110,"distance_km":42}],
  "trend":"rising|flat|falling", "recommendation":"sell_now|hold|go_to:<market>",
  "confidence":0.0-1.0, "explanation_localized":"...", "escalate":false }
```

**Crop Doctor Agent** — 
Inputs: image (+ optional symptom text), crop, location. 
Logic: `vision_classify(image)` → candidate disease/pest + confidence; retrieve treatment from KB (RAG) scoped to crop+label; assemble a step-by-step, locally-valid treatment with safety notes. 
Guardrail: confidence < threshold (default 0.6) or image unusable → set `escalate=true`, create an Escalation, ask for a clearer photo. Always include a 'when to consult an officer' line. 
Output contract:
```
{ "agent":"crop", "label":"early_blight", "confidence":0.0-1.0,
  "treatment_steps":["..."], "inputs_needed":["..."], "safety":"...",
  "escalate":bool, "diagnosis_case_id":"uuid", "explanation_localized":"..." }
```

**Knowledge Base / RAG** — ingestion pipeline: doc → clean → chunk (≈500 tokens, overlap) → embed → store in `KnowledgeChunk`. Retrieval: top-k by vector similarity filtered by `crop_id`/`topic`/`language`, fed to the agent prompt. KB content is **authored/validated by agronomy partners** (research institutes/universities) via the admin portal; every answer should be traceable to a `KnowledgeDoc` (cite `doc_id`).

**Guardrail layer (shared):** confidence thresholds per agent; profanity/abuse filter; 'no medical/financial guarantees' policy; assisted-mode switch (below).

## 5 · API Surface (REST, versioned /v1)

Representative endpoints the frontends and adapters call. All JSON; auth via Bearer JWT except farmer-OTP and channel webhooks.

**Auth & onboarding**
- `POST /v1/auth/otp/request` · `POST /v1/auth/otp/verify` (farmer phone OTP → tokens)
- `POST /v1/auth/staff/login` (staff)
- `POST /v1/farmers` (create) · `GET/PATCH /v1/farmers/{id}` · `POST /v1/farmers/{id}/plots`

**Conversation core (channel-agnostic)**
- `POST /v1/messages:ingest` — body: `{channel, external_user_id, modality, text|media_url}` → returns normalized response. Adapters call this.
- `GET /v1/conversations/{id}` · `GET /v1/farmers/{id}/conversations`

**Agents (also callable directly for portals/testing)**
- `POST /v1/agents/price` → Price output contract
- `POST /v1/agents/crop` (multipart image) → Crop output contract

**Prices (ground-staff portal)**
- `GET /v1/prices?crop&market&from&to` · `POST /v1/prices` (single) · `POST /v1/prices:bulk` (CSV) · `PATCH /v1/prices/{id}`
- `GET /v1/markets` · `POST /v1/markets`

**Knowledge base (admin portal)**
- `GET/POST /v1/kb/docs` · `PATCH /v1/kb/docs/{id}` · `POST /v1/kb/docs/{id}:reindex`

**Escalations (officer console)**
- `GET /v1/escalations?status&district` · `POST /v1/escalations/{id}:claim` · `POST /v1/escalations/{id}:resolve`

**Channel webhooks**
- `POST /v1/webhooks/whatsapp` (+ `GET` verify) · `POST /v1/webhooks/telegram`

**Analytics**
- `GET /v1/metrics/northstar` (% advised farmers who took action & saw outcome), usage, cost, escalation SLA.

## 6 · Channels & Adapters

**Adapter contract:** every channel adapter does two jobs — (a) normalize inbound platform payload → `{channel, external_user_id, modality, text|media_url}` and POST to `/v1/messages:ingest`; (b) take the core response and render it per platform (text, voice note, quick-reply buttons, image). The core never imports a channel SDK.

**WhatsApp (WhatsApp Cloud API):**
- Inbound via **webhook** (`/v1/webhooks/whatsapp`) with verify token + signature check.
- Requires a Meta Business account, a verified number, and **pre-approved message templates** for any business-initiated message; free-form replies allowed only inside the 24-hour customer-service window.
- Supports voice notes (download media → ASR) and images (→ Crop Doctor).
- **Reality:** webhooks need a public HTTPS endpoint and Meta approval — plan a few days of approval lead time. Cannot run inside a no-inbound sandbox; deploy to a real host.

**Telegram (Bot API):**
- Two modes: **webhook** (prod) or **long-polling** `getUpdates` (works even without a public endpoint — good for early dev/pilot).
- Native support for voice, photos, inline keyboards. Fastest channel to stand up first.

**Web chat:**
- A lightweight chat widget in the farmer web app hitting `/v1/messages:ingest` with `channel=web`. Full control; best for demos and the onboarding wizard.

**Voice pipeline (all channels):** inbound voice note → `transcribe(audio, lang)` → agent → optional `speak(text, lang)` to return a voice reply. Detect language from the farmer profile, allow per-message override.

**SMS/USSD [LATER]:** for feature phones via an SMS gateway (e.g., a local aggregator) — text-only, menu-driven fallback.

## 7 · Web Portals & Roles

Four frontends (can be one SPA with role-gated routes). All bilingual.

**A. Farmer Web App** (role: farmer) — onboarding wizard, web chat to the assistant, price lookup, crop-photo upload, profile/plots. Mobile-first PWA; installable; offline cache of last answers.

**B. Ground-Staff Price Portal** (role: ground_staff) — the data lifeline for the Price Agent. Features: quick daily price entry per market/crop (min/max/unit), **bulk CSV upload**, edit/correct, 'today's coverage' dashboard (which markets/crops are missing), district-scoped. Optimized for fast repeated entry on mobile.

**C. Admin / Knowledge-Base Portal** (role: admin) — manage `KnowledgeDoc`s (create/edit/validate/version), trigger reindex, manage crops/markets, manage staff users & roles, view farmers and conversations, system analytics & cost, feature flags (assisted mode, confidence thresholds).

**D. Extension-Officer Console** (role: extension_officer) — the human-in-the-loop queue: incoming Escalations (price/crop), claim → view farmer context + image + AI's draft → edit/approve answer → resolve; log outcome. District-scoped; SLA timers. This console is also what powers **assisted mode** for the pilot.

**RBAC:** roles = farmer, ground_staff, extension_officer, admin. Enforce district scoping for staff. All portal actions audit-logged.

## 8 · Onboarding Flow

Goal: a farmer is registered and gets first value in under 3 minutes, on any channel.

**Steps (conversational on WA/TG, wizard on web):**
1. **Language** — choose Sinhala / Tamil / English (sets `preferred_language`).
2. **Identify** — phone is the identity (auto on WA/TG from the platform id; OTP on web).
3. **Locate** — capture GPS (share-location on WA/TG) or pick district→DSD→village. Drives nearest-market and localized advice.
4. **Profile crops** — add 1–3 crops + rough plot size + season. Minimal; expandable later.
5. **Consent** — explicit data-use consent (store `consent_data`, `consent_ts`); explain data is theirs and earns them better service, not surveillance.
6. **First value** — immediately offer: 'Ask me a price' or 'Send a photo of a sick plant.' Land the aha-moment in the first session.

**Channels of entry:** organic (farmer messages the WA/TG number from a poster/officer), staff-assisted (ground staff registers them in-portal), or via a Farmer Organization batch import. Re-engagement: a farmer messaging again is recognized by phone/platform id; no re-onboarding.

**Edge cases:** no GPS → district picker; shared phones → allow multiple profiles per phone [LATER]; low literacy → voice prompts throughout.

## 9 · External Integrations

| Integration | Use | Phase | Notes |
|---|---|---|---|
| **Ground-staff price entry** | primary price data source | **Day 1** | The portal IS the integration; do not block on external feeds. |
| HARTI / Dambulla DEC price data | automated price ingestion | Phase 2 | Validate availability/format first (load-bearing for the price agent). May be manual scrape → review. |
| Weather API | irrigation/sowing alerts, calendar | Phase 2 | e.g. a forecast API keyed by GPS. |
| ASR/TTS provider (Sinhala/Tamil) | voice pipeline | Phase 1–2 | Behind the model gateway; evaluate accuracy on local dialects. |
| Vision model / dataset | crop disease accuracy | Phase 1→3 | Start vision-LLM; collect labeled images to fine-tune. |
| SMS gateway | OTP + feature-phone fallback | Phase 1 (OTP), 3 (USSD) | Local aggregator. |
| DOA / subsidy systems | subsidy checks, gov dashboard | [LATER] | After traction; avoid early procurement dependency. |
| Buyers / marketplace, banks, insurers | market linkage, credit, insurance | [LATER] | Phases 3–4 of the product strategy. |

**Principle:** the system must be fully functional on **Day 1 with only staff-entered prices + KB**. Every external feed is an enhancement, never a launch blocker.

## 10 · Security, Privacy & Compliance

- **Auth:** farmers = phone + OTP → short-lived JWT + refresh; staff = credential login with role claims. Rotate secrets; store only password hashes (argon2/bcrypt).
- **RBAC:** farmer / ground_staff / extension_officer / admin; enforce **district scoping** for staff queries server-side (never trust the client).
- **Sri Lanka PDPA (Personal Data Protection Act, No. 9 of 2022):** lawful basis = consent; capture and timestamp consent at onboarding; support data access/erasure requests; appoint a data controller. Tamil/Sinhala consent copy must be understandable.
- **Data ownership:** farmer data is the farmer's; B2B/analytics use only **aggregated/anonymized** data. Make this explicit in-product (trust is the moat).
- **PII handling:** encrypt at rest (DB + S3), TLS in transit; minimize PII in logs; signed, expiring URLs for crop images/voice notes.
- **Webhook security:** verify WhatsApp signature + verify-token; validate Telegram secret token.
- **Abuse/cost controls:** per-user rate limits (Redis), max media size, LLM spend caps + alerts, prompt-injection filtering on user content fed to the LLM.
- **Auditing:** immutable audit log for staff actions (price edits, KB changes, escalation resolutions).

## 11 · Internationalization (Sinhala / Tamil)

- **UI i18n:** all portal/app strings in resource bundles (`si`, `ta`, `en`); no hard-coded text. RTL not required (both scripts are LTR) but test Unicode rendering and fonts (e.g., Noto Sans Sinhala / Tamil).
- **Content i18n:** `KnowledgeDoc` and `Crop` carry per-language fields; RAG retrieves in the farmer's language, with English fallback + on-the-fly translation if a localized doc is missing.
- **Conversation language:** default from `preferred_language`; allow inline switch; the agent always responds in the farmer's language regardless of query language.
- **Voice:** ASR and TTS must support Sinhala and Tamil; budget for accuracy testing on rural dialects and code-mixing (farmers mix English crop/agrochemical names). Keep a human-correction loop to improve transcripts.
- **Number/units/dates:** localize units (kg, perch/acre), currency (LKR), and Maha/Yala season terms.
- **Quality bar:** professional translation + agronomy-partner review for all farmer-facing safety/treatment text — machine translation alone is unacceptable for pesticide guidance.

## 12 · Non-Functional Requirements

- **Offline/low-bandwidth:** web app is a PWA caching last answers and the onboarding shell; compress images client-side before upload; keep responses short for low data cost; degrade voice→text gracefully.
- **Performance targets:** text response p95 < 3s (excluding model latency you can't control); image diagnosis < 10s; price lookup < 1s (DB-backed).
- **Reliability:** stateless API behind a load balancer; queue long tasks (vision, ASR) via Redis; idempotent webhook handling (platforms retry).
- **Scalability:** start single-region; the brain is stateless so it scales horizontally; DB is the bottleneck — index well, read-replica [LATER].
- **Observability:** structured logs with conversation/farmer ids; trace each turn (intent→agent→model calls→cost); dashboards for usage, escalation SLA, model spend, and the **north-star** (% advised → acted → outcome).
- **Cost control:** cache embeddings and frequent answers; use a small/cheap model for intent routing and a larger one only for generation; cap tokens; log per-message cost.
- **Testing:** unit (services, guardrails), contract tests for agent I/O, integration (webhook→ingest→response) using the **mock model provider** so CI runs with no external keys.

## 13 · Phased Build Roadmap

Each phase ends with a demoable milestone and explicit acceptance criteria. Estimates assume a small team (≈2–3 engineers); adjust as needed.

**Phase 0 — Foundations (≈1–2 wks).** Monorepo, Docker, CI, Postgres+pgvector, Redis, S3, JWT auth, the **Model Gateway with mock provider**, base schema, seed data. ✅ *Done when:* app boots, auth works, schema migrates, CI green with mocks.

**Phase 1 — Core loop + Price + Ground-staff portal (≈2–3 wks).** Farmer model + onboarding (web), web chat, orchestrator, **Price Agent**, ground-staff price portal (entry + CSV). ✅ *Done when:* a farmer onboards on web, asks a price, gets a market-aware answer from staff-entered data; staff can manage prices.

**Phase 2 — Crop Doctor + Knowledge Base + Admin (≈3 wks).** KB ingestion/RAG, **Crop Doctor Agent** (vision adapter + mock→real), admin/KB portal, escalation creation on low confidence. ✅ *Done when:* a photo yields a cited treatment or an escalation; admins manage validated KB content.

**Phase 3 — Channels + Voice + Officer console (≈3 wks).** Telegram (polling→webhook), WhatsApp Cloud API (webhooks, templates), voice ASR/TTS, extension-officer console + **assisted mode**. ✅ *Done when:* the same brain answers on WhatsApp & Telegram incl. voice notes; officers resolve escalations; assisted mode can front the pilot.

**Phase 4 — Bilingual hardening + analytics + pilot deploy (≈2–3 wks).** Full Sinhala/Tamil content, PDPA consent flows, north-star analytics, security hardening, deploy to a real host for the field pilot. ✅ *Done when:* end-to-end bilingual, deployed, metrics live, ready for the district pilot.

**[LATER] Phase 5+** — weather/calendar/input-cost agents, market linkage, credit/insurance, gov & subsidy integration, SMS/USSD.

## 14 · Builder Hand-off Notes

Practical notes so an implementing agent can start immediately.

**Suggested repo structure:**
```
farmingos/
  backend/
    app/
      api/            # FastAPI routers (auth, farmers, prices, agents, kb, escalations, webhooks)
      core/           # orchestrator, guardrails, memory
      agents/         # price.py, crop.py (pure logic, no channel imports)
      services/       # farmer, price, diagnosis, kb_rag, escalation
      gateway/        # model gateway + providers (mock, openai, anthropic, gemini...)
      channels/       # whatsapp.py, telegram.py, web.py (adapters)
      db/             # models, migrations, seed
      i18n/           # si.json, ta.json, en.json
    tests/
  web/                # React SPA(s): farmer, price-portal, admin, officer
  infra/              # docker-compose, deploy manifests
  docs/               # this blueprint, API reference, runbooks
```

**Key env vars:** `DATABASE_URL`, `REDIS_URL`, `S3_*`, `JWT_SECRET`, `MODEL_PROVIDER` (mock|openai|…), `LLM_API_KEY`, `VISION_PROVIDER`, `ASR_PROVIDER`, `TTS_PROVIDER`, `WHATSAPP_TOKEN`/`WHATSAPP_VERIFY_TOKEN`/`WA_PHONE_ID`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_MODE` (poll|webhook).

**Model-gateway mock contract:** the mock provider returns deterministic, schema-valid outputs (fixed price reasoning, a canned disease label, echo embeddings) so the entire system runs and CI passes with **zero external keys**. Real providers implement the same interface — swapping is a config change, not a code change.

**Definition of Done (every component):** typed I/O, unit tests against the mock, contract test for any agent output, i18n strings externalized, audit log on mutations, error states handled, README run steps.

**Order of operations for the agent:** Phase 0 scaffolding → schema+seed → model gateway(mock) → orchestrator + Price agent + web chat → ground-staff portal → Crop Doctor + KB → channels → officer console + assisted mode → bilingual + analytics → deploy.

**Reconciliation with the Evaluation Playbook:** ship **assisted mode** early so the same system can run the human-in-the-loop pilot (Wizard-of-Oz) — validate demand while the autonomous agents harden behind the same UI.
