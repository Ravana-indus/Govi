"""Test fixtures.

Uses a throwaway SQLite file and the deterministic mock provider, so the whole
suite runs with zero external keys. The DB is created and seeded once per session.
"""
from __future__ import annotations

import os
import tempfile

# Configure the environment BEFORE importing the app (engine binds at import).
_TMP_DB = os.path.join(tempfile.gettempdir(), "farmingos_test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["APP_ENV"] = "dev"
os.environ["MODEL_PROVIDER"] = "mock"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from scripts.seed import seed  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _prepare_db():
    if os.path.exists(_TMP_DB):
        os.remove(_TMP_DB)
    Base.metadata.create_all(bind=engine)
    seed()
    yield
    if os.path.exists(_TMP_DB):
        os.remove(_TMP_DB)


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def client():
    return TestClient(app)
