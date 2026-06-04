"""Database engine, session, declarative base, and a portable embedding type.

Canonical target is Postgres 15 + pgvector. For the keyless dev/CI run we use
SQLite; the schema is identical except the embedding column degrades to JSON.
That single seam is the only dialect-specific code in the data layer.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Iterator

from sqlalchemy import DateTime, String, TypeDecorator, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.types import Text

from app.config import settings

# ---------------------------------------------------------------------------
# Engine / session
# ---------------------------------------------------------------------------
_is_sqlite = settings.database_url.startswith("sqlite")
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator["Session"]:  # type: ignore[name-defined]
    """FastAPI dependency yielding a session, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Portable column types
# ---------------------------------------------------------------------------
class Embedding(TypeDecorator):
    """Vector column.

    On Postgres you swap this for pgvector's Vector(dim) (see Alembic migration
    and docs/RUNBOOK). For portability in the keyless dev run we JSON-encode the
    float list into TEXT. RAG retrieval (Phase 2) reads it back as list[float].
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(list(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)


class JSONList(TypeDecorator):
    """A list[str] stored as JSON TEXT (e.g. StaffUser.district_scope)."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return json.dumps(value or [])

    def process_result_value(self, value, dialect):
        return json.loads(value) if value else []


# ---------------------------------------------------------------------------
# Declarative base + shared mixins
# ---------------------------------------------------------------------------
def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class PkMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


def init_db() -> None:
    """Create all tables. Used for the SQLite bootstrap and tests.

    Prod uses Alembic migrations (see app/db/migrations)."""
    from app.db import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=engine)
