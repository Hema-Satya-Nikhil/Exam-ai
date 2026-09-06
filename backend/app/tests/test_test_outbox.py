"""TEST-only OTP outbox endpoint — gating, payloads, and security surface.

The outbox must exist ONLY in APP_ENV=TEST and expose nothing but the
recipient email and the OTP for messages recorded by NoopEmailService.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.pool import StaticPool

from app.core import security
from app.core.config import settings
from app.db.base import Base
from app.api.dependencies.auth import get_db
from app.main import app
from app.models.academic import Role, User
from app.services.email_service import NoopEmailService, get_email_service, set_email_service

SQLITE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(SQLITE_URL, echo=False, poolclass=StaticPool)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

TEST_EMAIL = "outbox.flow@example.com"


async def _get_test_db():
    async with TestSession() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def _lifecycle():
    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _get_test_db
    set_email_service(NoopEmailService())
    try:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with TestSession() as session:
            role = Role(name=f"faculty-{uuid4().hex[:8]}")
            session.add(role)
            await session.flush()
            session.add(
                User(
                    email=TEST_EMAIL,
                    full_name="Outbox Faculty",
                    password_hash=security.hash_password("SecretPass1!"),
                    is_active=True,
                    roles=[role],
                )
            )
            await session.commit()
        yield
    finally:
        set_email_service(None)
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override


def _request_otp(email: str) -> None:
    client = TestClient(app)
    resp = client.post("/api/auth/forgot-password", json={"email": email})
    assert resp.status_code == 200, resp.text


def _mail() -> NoopEmailService:
    return get_email_service()  # type: ignore[return-value]


def test_outbox_exposes_otp_recorded_by_noop_adapter():
    _request_otp(TEST_EMAIL)
    client = TestClient(app)
    resp = client.get("/api/auth/test/outbox", params={"email": TEST_EMAIL})
    assert resp.status_code == 200
    messages = resp.json()["messages"]
    assert messages, "outbox must contain the recorded OTP"
    assert messages[0]["otp"] == _mail().latest_otp(TEST_EMAIL)
    assert messages[0]["email"].lower() == TEST_EMAIL


def test_outbox_returns_only_email_and_otp():
    _request_otp(TEST_EMAIL)
    client = TestClient(app)
    resp = client.get("/api/auth/test/outbox")
    assert resp.status_code == 200
    for message in resp.json()["messages"]:
        assert set(message.keys()) == {"email", "otp"}
    body = resp.text.lower()
    assert "password" not in body
    assert "reset_token" not in body
    assert "access_token" not in body
    assert "refresh_token" not in body


def test_outbox_scoped_to_requested_email():
    _request_otp(TEST_EMAIL)
    client = TestClient(app)
    resp = client.get("/api/auth/test/outbox", params={"email": "someone.else@example.test"})
    assert resp.status_code == 200
    assert resp.json()["messages"] == []


def test_outbox_fails_closed_outside_test_env():
    """The handler itself must refuse when APP_ENV is not TEST (defence in
    depth alongside the conditional router mount)."""
    _request_otp(TEST_EMAIL)
    client = TestClient(app)
    original = settings.app_env
    try:
        for env in ("production", "staging", "development", "PRODUCTION", ""):
            settings.app_env = env
            resp = client.get("/api/auth/test/outbox")
            assert resp.status_code == 404, f"env={env!r} must fail closed"
            assert "otp" not in resp.text.lower()
    finally:
        settings.app_env = original
