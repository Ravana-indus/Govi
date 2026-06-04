# FarmingOS backend image (Python 3.11 — canonical runtime).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# System deps for psycopg2 build (kept minimal).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=4s --start-period=10s \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

# Prod: run migrations then serve. (Dev/compose can override the command.)
CMD ["sh", "-c", "alembic upgrade head || true; uvicorn app.main:app --host 0.0.0.0 --port 8000"]
