"""
Test configuration for chemrep backend.
Sets up SQLite in-memory database for testing.
"""
import os
import sys
import sqlite3
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, String, Text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.db.base import Base
import src.models  # noqa: F401 — register all models

from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB


def _adapt_types_for_sqlite():
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, PG_UUID):
                col.type = String(36)
            elif isinstance(col.type, JSONB):
                col.type = Text()


_adapt_types_for_sqlite()

import sqlite3
sqlite3.register_adapter(uuid.UUID, lambda u: str(u))

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

Base.metadata.create_all(bind=engine)

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_teacher(db):
    from src.api.routes.auth import _hash
    from src.models.teacher import Teacher

    teacher = Teacher(
        email="teacher@example.com",
        hashed_password=_hash("password123"),
        full_name="Test Teacher",
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    return teacher


@pytest.fixture
def auth_token(test_teacher):
    from src.api.routes.auth import _make_token

    return _make_token(str(test_teacher.id))


@pytest.fixture
async def client(db):
    from src.db.base import get_db
    from main import app

    def override_get_db():
        try:
            yield db
        except Exception:
            db.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
