"""Application settings.

Single source of truth for configuration. Everything is overridable by env var
so the same image runs in dev (SQLite + mock providers, zero external keys) and
in prod (Postgres + pgvector + Redis + S3 + real model providers).
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # pydantic v2 reserves the "model_" namespace; we use model_provider etc.
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", protected_namespaces=()
    )

    # --- Core ---
    app_env: str = "dev"
    api_prefix: str = "/v1"
    default_language: str = "si"  # si | ta | en

    # --- Data stores ---
    # Dev default is SQLite so the system runs with no external services.
    # Prod: postgresql+psycopg2://user:pass@host:5432/farmingos
    database_url: str = "sqlite:///./farmingos.db"
    redis_url: str | None = None  # None -> in-memory cache fallback

    # --- Auth ---
    jwt_secret: str = "dev-insecure-secret-change-me-in-production-0123456789"
    jwt_alg: str = "HS256"
    # Comma-separated allowed origins for CORS; "*" only sane in dev.
    cors_origins: str = "*"
    access_token_ttl_min: int = 30
    refresh_token_ttl_days: int = 30
    expose_otp_in_dev: bool = True  # return OTP in API response when app_env=dev

    # --- Model gateway provider selection ---
    model_provider: str = "mock"   # mock | openai | anthropic | gemini
    vision_provider: str = "mock"  # mock | vision-llm | classifier
    asr_provider: str = "mock"
    tts_provider: str = "mock"
    embed_provider: str = "mock"
    llm_api_key: str | None = None

    # --- Local media dir (dev fallback for synthesized voice replies, etc.) ---
    media_dir: str = "./media"

    # --- Object storage (crop images, voice notes) ---
    s3_endpoint: str | None = None
    s3_bucket: str = "farmingos-media"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None

    # --- Channels ---
    whatsapp_token: str | None = None
    whatsapp_verify_token: str | None = None
    whatsapp_app_secret: str | None = None  # for X-Hub-Signature-256 verification
    wa_phone_id: str | None = None
    telegram_bot_token: str | None = None
    telegram_mode: str = "poll"  # poll | webhook

    # --- Agent tuning / guardrails ---
    price_nearest_markets: int = 3
    price_stale_days: int = 3            # prices older than this lower confidence
    price_transport_lkr_per_km: float = 0.3  # rough net-price estimate (LKR per kg per km)
    crop_confidence_threshold: float = 0.6   # below -> escalate

    # --- Cost / abuse controls ---
    rate_limit_per_min: int = 30
    max_media_mb: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
