# FarmingOS runbook

## 1. Local dev (keyless: SQLite + in-memory cache + mock provider)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                      # defaults are already keyless
PYTHONPATH=. python scripts/seed.py
uvicorn app.main:app --reload             # http://localhost:8000/docs
```

The app auto-creates the SQLite schema on startup (`init_db`). No migrations
needed for the dev path.

## 2. Tests & the scripted demo

```bash
cd backend
pytest -q                                 # 17 tests, mock provider, no keys
PYTHONPATH=. python scripts/demo_e2e.py   # narrated end-to-end walkthrough
```

## 3. Full stack with Docker (Postgres + pgvector, Redis, MinIO)

```bash
docker compose -f infra/docker-compose.yml up --build
# web → http://localhost:8080   api → http://localhost:8000   minio console → :9001
```

The backend container runs `alembic upgrade head` before serving.

## 4. Database migrations (canonical Postgres path)

The SQLite dev path uses `init_db()`. For Postgres, generate and apply Alembic
migrations (the env is wired to the ORM metadata and the `DATABASE_URL`):

```bash
cd backend
export DATABASE_URL=postgresql+psycopg2://farmingos:secret@localhost:5432/farmingos
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

The `KnowledgeChunk.embedding` column is JSON on SQLite and should be switched to
pgvector `Vector(<dim>)` with an `ivfflat` index on Postgres — edit the generated
migration to use `pgvector.sqlalchemy.Vector` and add:
`CREATE INDEX ... USING ivfflat (embedding vector_cosine_ops);`

## 5. Switching to a real model provider

Set env and restart — no code change (the gateway is the seam):

```bash
MODEL_PROVIDER=openai        # or anthropic / gemini
LLM_API_KEY=sk-...
VISION_PROVIDER=...          # ASR_PROVIDER / TTS_PROVIDER similarly
```

Implement the provider against `app/gateway/base.ModelProvider` (see
`app/gateway/openai_provider.py` for the stub) and register it in
`app/gateway/__init__.get_gateway`.

## 6. Channels (Phase 3)

- **Telegram**: set `TELEGRAM_BOT_TOKEN`; for dev run the long-poll runner
  `TELEGRAM_BOT_TOKEN=... API_BASE=http://localhost:8000/v1 PYTHONPATH=. python scripts/run_telegram.py`,
  or set a webhook to `POST /v1/webhooks/telegram` in prod. Adapter:
  `app/channels/telegram.py`. Voice notes are downloaded via getFile → ASR;
  the reply is sent back as text (and, on web, a synthesized voice note).
- **WhatsApp Cloud API**: needs a Meta Business account, a verified number,
  pre-approved templates, and a **public HTTPS** webhook with verify-token +
  signature checks. Cannot run in a no-inbound sandbox. Adapter:
  `app/channels/whatsapp.py`; webhook: `GET/POST /v1/webhooks/whatsapp`.

## 6b. Deploy to a real host (pilot)

**Render (one-click blueprint):** push to GitHub, then Render → New → Blueprint →
point at the repo. `infra/render.yaml` provisions Postgres, Redis, the API
(Docker), and the web app. After the first deploy, run the initial migration and
switch the embedding column to pgvector (section 4). Set `CORS_ORIGINS`,
`JWT_SECRET` (auto-generated), and any channel/model secrets in the dashboard.

**Anywhere else:** the stack is plain Docker — `infra/docker-compose.yml` runs the
full system locally/VM; Fly.io/Railway/ECS work with the same two Dockerfiles.
Prod env template: `backend/.env.prod.example`.

Going fully live also needs (see docs/PILOT_READINESS.md): a real model provider,
WhatsApp Business verification + templates + public HTTPS webhook, an SMS gateway
for OTP, and agronomy-validated KB content.

## 7. Security checklist before any pilot

- Replace `JWT_SECRET` (32+ chars) and rotate regularly.
- Swap PBKDF2 password hashing for argon2 (`argon2-cffi` is in requirements).
- Lock CORS `allow_origins` to known frontends.
- Enforce WhatsApp signature verification (stub in `whatsapp.py`).
- Confirm district scoping on all staff queries (already enforced server-side).
- PDPA: consent is captured + timestamped at onboarding; wire data
  access/erasure endpoints before launch.

## 8. Common issues

- **`Unable to evaluate type annotation 'str | None'`** on Python < 3.10:
  `eval_type_backport` (in requirements for `python_version < "3.10"`) handles
  pydantic; the ORM models already use `Optional[...]`. Prefer Python 3.11.
- **429 from `/messages:ingest`** in load tests: the in-memory limiter is per
  process; use `REDIS_URL` for a shared limiter across replicas.
