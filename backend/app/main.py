"""FastAPI application factory.

Mounts the channel-agnostic API under /v1. On dev startup we bootstrap the
SQLite schema; prod runs Alembic migrations instead (see docs/RUNBOOK).
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin, agents, auth, escalations, farmers, kb, messages, metrics, outcomes,
    prices, webhooks,
)
from app.config import settings
from app.db.base import engine, init_db


def create_app() -> FastAPI:
    app = FastAPI(
        title="FarmingOS API",
        version="0.1.0",
        description="Channel-agnostic AI assistant for smallholder farmers "
                    "(Price Intelligence + Crop Doctor).",
    )

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,            # env-driven; set explicit origins in prod
        allow_credentials="*" not in origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _security_headers(request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "geolocation=(self)"
        return resp

    p = settings.api_prefix
    for module in (auth, farmers, messages, agents, prices, kb, escalations,
                   metrics, admin, outcomes, webhooks):
        app.include_router(module.router, prefix=p)

    @app.get("/healthz", tags=["meta"])
    def healthz():
        return {
            "status": "ok",
            "env": settings.app_env,
            "model_provider": settings.model_provider,
            "db": engine.url.get_backend_name(),
        }

    @app.on_event("startup")
    def _startup():
        # Dev/SQLite convenience. Prod uses Alembic migrations.
        if settings.database_url.startswith("sqlite"):
            init_db()
        # Fail loud-ish if shipped with insecure defaults in prod.
        if settings.app_env != "dev":
            import logging
            log = logging.getLogger("farmingos")
            if settings.jwt_secret.startswith("dev-"):
                log.warning("INSECURE: default JWT_SECRET in non-dev env — set a strong secret.")
            if "*" in settings.cors_origins:
                log.warning("INSECURE: wildcard CORS in non-dev env — set CORS_ORIGINS.")

    return app


app = create_app()
