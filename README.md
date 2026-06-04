# FarmingOS

A channel-agnostic AI assistant for smallholder farmers — a **Price Intelligence**
agent and a **Crop Doctor** agent, reachable via web (and, in later phases,
WhatsApp & Telegram), backed by a knowledge base, a farmer database, and operator
portals.

This repository is **Phase 0 + Phase 1** of the [build blueprint](docs/BLUEPRINT.md):
a runnable vertical slice that proves the architecture end to end on a
**deterministic mock model provider** — so it runs, and CI passes, with **zero
external API keys**.

---

## What works today

- **Farmer onboarding** (phone + OTP, language, location, crops, consent) in one call.
- **Price Intelligence agent** — finds the latest staff-entered prices across the
  nearest markets, computes **net price after estimated transport**, a 7-day
  trend, and a **sell / hold / go-to-market recommendation** with a confidence
  score and a **localized** explanation (Sinhala / Tamil / English).
- **Crop Doctor agent** — vision classify → retrieve a *validated, cited*
  treatment from the KB → step-by-step advice with safety notes; **escalates** to
  a human officer on low confidence, an unusable photo, or when no citable doc
  exists.
- **Orchestrator** — normalizes a message, classifies intent (image ⇒ Crop
  Doctor), attaches farmer context, dispatches, applies guardrails, persists every
  turn, and creates an **Escalation** when needed.
- **Ground-staff price portal** API — daily entry, **bulk CSV**, district-scoped &
  audited, plus a **today's-coverage** dashboard.
- **Officer / KB / metrics** endpoints — escalation queue (claim/resolve), KB doc
  CRUD + reindex, and the **north-star** metric (% advised → acted → outcome).
- **Web app (React + Vite)** — farmer onboarding wizard, chat widget (text +
  photo), and the ground-staff price portal. Admin & officer consoles are
  labeled placeholders (their APIs already exist and are tested).
- **17 passing tests** (unit + agent contracts + HTTP integration) on the mock provider.

## Deferred to later phases (seams are in place)

KB ingestion at scale & the admin authoring UI (Phase 2); WhatsApp/Telegram
adapters & the voice ASR/TTS pipeline (Phase 3); full Sinhala/Tamil content
hardening & PDPA flows (Phase 4). Channel adapters, the model-gateway provider
interface, and the escalation/assisted-mode hooks are already stubbed so these
slot in without refactoring the core.

---

## Quickstart (no Docker, no keys)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

PYTHONPATH=. python scripts/seed.py        # reference data + demo prices + KB + staff
PYTHONPATH=. python scripts/demo_e2e.py    # scripted end-to-end walkthrough
pytest -q                                  # 17 tests, all on the mock provider

uvicorn app.main:app --reload              # API at http://localhost:8000  (docs: /docs)
```

Frontend:

```bash
cd web
npm install
npm run dev                                # http://localhost:5173 (proxies /v1 to :8000)
```

Demo staff logins: `staff@farmingos.lk / ground123`, `officer@farmingos.lk /
officer123`, `admin@farmingos.lk / admin123`.

## Full stack (Docker — Postgres + pgvector, Redis, MinIO)

```bash
docker compose -f infra/docker-compose.yml up --build
# web → http://localhost:8080   api → http://localhost:8000
```

See [docs/RUNBOOK.md](docs/RUNBOOK.md) for migrations, switching to a real model
provider, and deployment notes. API reference: [docs/API.md](docs/API.md).

---

## Repository layout

```
farmingos/
  backend/      FastAPI app — core brain (orchestrator, agents, services, gateway),
                channel adapters, db models, i18n, seed + demo scripts, tests
  web/          React + Vite SPA (farmer app, price portal, admin/officer placeholders)
  infra/        Dockerfiles, docker-compose (pg+pgvector/redis/minio), nginx
  docs/         BLUEPRINT.md, API.md, RUNBOOK.md
  .github/      CI (runs backend tests on the mock provider; builds the web app)
```

## Design principles (enforced)

Voice-first & bilingual · offline/low-bandwidth tolerant · **confidence-aware with
human-in-the-loop** · verifiable outcome over information · farmers never pay & own
their data · **channel-agnostic core** (no channel SDK imported by the brain).
# Govi
