# FarmingOS — Pilot readiness checklist

Use this before a district field pilot. Items marked ✅ are implemented in this
repo; ☐ are deploy-time / operational steps that can't be done from a sandbox.

## Functional (in code)
- ✅ End-to-end farmer loop: onboarding → price advice → crop diagnosis → escalation.
- ✅ Bilingual (si/ta/en): UI bundles + KB content i18n; key-parity test guards coverage.
- ✅ Confidence-aware with human-in-the-loop: thresholds, escalations, **assisted mode**.
- ✅ Channels: web (live), Telegram (poll + webhook), WhatsApp (webhook + signature).
- ✅ Voice pipeline: ASR in → route → TTS out (mock providers; real behind the gateway).
- ✅ Operator surfaces: ground-staff price portal, Admin/KB console, Officer console.
- ✅ North-star analytics + dashboard (advised → acted → outcome, SLA, by-intent).

## Privacy & security
- ✅ PDPA: consent captured + timestamped; data **export** and **erasure** endpoints.
- ✅ Argon2 password hashing (pbkdf2 fallback); JWT access/refresh; phone-OTP for farmers.
- ✅ RBAC + server-side district scoping; immutable audit log on staff mutations.
- ✅ Security headers; env-driven CORS; WhatsApp HMAC signature verification.
- ☐ Set a strong `JWT_SECRET`, real `CORS_ORIGINS`, and rotate secrets.
- ☐ Appoint a data controller; publish si/ta privacy notice; legal review of consent copy.
- ☐ Professional translation + agronomy-partner review of all safety/treatment text.

## Deploy
- ✅ Dockerized; `infra/render.yaml` one-click blueprint; `docker-compose` for the full stack.
- ✅ CI runs the suite on the mock provider (no keys).
- ☐ Provision Postgres+pgvector, Redis, S3; run `alembic upgrade head`; switch the
  `KnowledgeChunk.embedding` column to pgvector + an ivfflat index.
- ☐ Swap `MODEL_PROVIDER=mock` → a real LLM/vision/ASR/TTS provider; load-test latency.
- ☐ WhatsApp: Meta Business verification + approved message templates + public HTTPS webhook.
- ☐ Wire an SMS gateway for OTP delivery (currently dev-returns the code).
- ☐ Seed validated KB content with agronomy partners; onboard ground staff per district.

## Quality bar
- ✅ 33 automated tests (unit, agent contracts, HTTP integration) green on mocks.
- ☐ Evaluate ASR accuracy on rural Sinhala/Tamil dialects + code-mixing.
- ☐ Run assisted-mode (Wizard-of-Oz) first to validate demand while autonomous agents harden.
