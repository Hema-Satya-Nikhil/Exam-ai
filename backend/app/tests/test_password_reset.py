"""Password-reset (forgot-password OTP) test suite.

In-memory SQLite via aiosqlite (same pattern as test_auth.py). Email delivery
is the Noop test adapter — **no real email is ever sent**; the adapter records
(email, otp) pairs so the flow can be exercised end-to-end without exposing
OTPs through any API.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
from app.main import app
from app.api.dependencies.auth import get_db
from app.models.academic import RefreshSession, Role, User
from app.models.password_reset import PasswordResetOtp
from app.services.email_service import NoopEmailService, set_email_service
from app.services.password_reset_service import (
    PasswordResetService,
    _hash_otp,
    generate_otp,
)

SQLITE_URL = "sqlite+aiosqlite:///:memory:"
# StaticPool keeps ONE shared in-memory connection so seeded users are visible
# to every session (same pattern as test_admin_seed.py).
test_engine = create_async_engine(SQLITE_URL, echo=False, poolclass=StaticPool)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

ACTIVE_FACULTY = ("reset.flow@example.com", "Reset Flow", "OriginalPass1!")
PENDING_USER = ("pending.reset@example.com", "Pending User", "PendingPass1!")
PREEXISTING_JTI = "jti-preexisting-session"

reset_service = PasswordResetService()


async def _get_test_db():
    async with TestSession() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create tables + swap the get_db override (restored afterwards, per the
    project convention in test_admin_seed.py so module-level overrides from
    other suites — e.g. test_auth.py — keep working)."""
    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _get_test_db
    try:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        set_email_service(NoopEmailService())  # fresh recorder per test
        yield
    finally:
        set_email_service(None)
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override


async def _seed_users_async() -> dict[str, User]:
    async with TestSession() as session:
        faculty_role = Role(name=f"faculty-{uuid4().hex[:8]}", description="Faculty")
        users = {
            "active": User(
                email=ACTIVE_FACULTY[0], full_name=ACTIVE_FACULTY[1],
                password_hash=security.hash_password(ACTIVE_FACULTY[2]),
                is_active=True, roles=[faculty_role],
            ),
            "pending": User(
                email=PENDING_USER[0], full_name=PENDING_USER[1],
                password_hash=security.hash_password(PENDING_USER[2]),
                is_active=False, roles=[faculty_role],
            ),
        }
        session.add_all(users.values())
        await session.commit()
        return users


def _seed_users() -> dict[str, User]:
    """Synchronous seeding helper (the tests themselves are sync TestClient)."""
    import asyncio

    return asyncio.run(_seed_users_async())


def _client() -> TestClient:
    return TestClient(app)


def _mail() -> NoopEmailService:
    from app.services import email_service as mod

    return mod.get_email_service()  # type: ignore[return-value]


def _last_otp() -> str:
    return _mail().sent[-1][1]


def _request_otp(client: TestClient, email: str) -> None:
    resp = client.post("/api/auth/forgot-password", json={"email": email})
    assert resp.status_code == 200, resp.text
    assert resp.json()["message"].startswith("If an account exists")


def _backdate_last_record(seconds: int) -> None:
    """Move the newest OTP row's created_at back so the resend cooldown passes."""
    import asyncio

    async def _run() -> None:
        async with TestSession() as session:
            result = await session.execute(
                select(PasswordResetOtp).order_by(PasswordResetOtp.created_at.desc()).limit(1)
            )
            record = result.scalars().first()
            record.created_at = datetime.now(timezone.utc) - timedelta(seconds=seconds)
            await session.commit()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

GENERIC = "If an account exists for this email, a password reset OTP has been sent."


def test_forgot_password_unknown_email_generic_response():
    _seed_users()
    client = _client()
    resp = client.post("/api/auth/forgot-password", json={"email": "ghost@example.com"})
    assert resp.status_code == 200
    assert resp.json()["message"] == GENERIC
    assert len(_mail().sent) == 0  # no OTP sent, no enumeration


def test_forgot_password_existing_active_email_sends_otp():
    _seed_users()
    client = _client()
    resp = client.post("/api/auth/forgot-password", json={"email": ACTIVE_FACULTY[0].upper()})
    assert resp.status_code == 200
    assert resp.json()["message"] == GENERIC
    otp = _last_otp()
    assert len(otp) == 6 and otp.isdigit()
    assert otp not in resp.text  # OTP never in API response


def test_forgot_password_pending_account_gets_generic_no_otp():
    _seed_users()
    client = _client()
    resp = client.post("/api/auth/forgot-password", json={"email": PENDING_USER[0]})
    assert resp.status_code == 200
    assert resp.json()["message"] == GENERIC
    assert len(_mail().sent) == 0  # pending account cannot reset


def test_otp_stored_hashed_not_plaintext():
    _seed_users()
    client = _client()
    _request_otp(client, ACTIVE_FACULTY[0])
    import asyncio

    async def _check():
        async with TestSession() as session:
            rows = (await session.execute(select(PasswordResetOtp))).scalars().all()
            return rows[0]

    record = asyncio.run(_check())
    assert record.otp_hash != _last_otp()
    assert record.otp_hash == _hash_otp(_last_otp())
    assert record.attempt_count == 0
    assert record.verified_at is None and record.used_at is None


def test_otp_expiration_rejected():
    _seed_users()
    client = _client()
    _request_otp(client, ACTIVE_FACULTY[0])
    import asyncio

    async def _expire():
        async with TestSession() as session:
            record = (
                (await session.execute(select(PasswordResetOtp))).scalars().first()
            )
            record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            await session.commit()

    asyncio.run(_expire())
    resp = client.post(
        "/api/auth/verify-reset-otp", json={"email": ACTIVE_FACULTY[0], "otp": _last_otp()}
    )
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


def test_wrong_otp_counts_attempts_then_invalidates():
    _seed_users()
    client = _client()
    _request_otp(client, ACTIVE_FACULTY[0])
    for _ in range(settings.otp_max_attempts - 1):
        resp = client.post(
            "/api/auth/verify-reset-otp",
            json={"email": ACTIVE_FACULTY[0], "otp": "000000"},
        )
        assert resp.status_code == 400
        assert "incorrect" in resp.json()["detail"].lower()
    # Final allowed attempt exceeded -> invalidated
    resp = client.post(
        "/api/auth/verify-reset-otp", json={"email": ACTIVE_FACULTY[0], "otp": "000000"}
    )
    assert resp.status_code == 400
    assert "too many" in resp.json()["detail"].lower()
    # Even the correct OTP no longer works after invalidation
    resp = client.post(
        "/api/auth/verify-reset-otp", json={"email": ACTIVE_FACULTY[0], "otp": _last_otp()}
    )
    assert resp.status_code == 400

def test_resend_invalidates_previous_otp():
    _seed_users()
    client = _client()
    _request_otp(client, ACTIVE_FACULTY[0])
    old_otp = _last_otp()
    _backdate_last_record(seconds=settings.otp_resend_cooldown_seconds + 5)
    _request_otp(client, ACTIVE_FACULTY[0])
    new_otp = _last_otp()
    assert new_otp != old_otp
    # Old OTP no longer verifies
    resp = client.post(
        "/api/auth/verify-reset-otp", json={"email": ACTIVE_FACULTY[0], "otp": old_otp}
    )
    assert resp.status_code == 400
    # New OTP verifies and returns a reset token
    resp = client.post(
        "/api/auth/verify-reset-otp", json={"email": ACTIVE_FACULTY[0], "otp": new_otp}
    )
    assert resp.status_code == 200
    assert "access_token" not in resp.json()  # NOT a login JWT
    assert len(resp.json()["reset_token"]) >= 16


def test_resend_cooldown_rate_limited():
    _seed_users()
    client = _client()
    _request_otp(client, ACTIVE_FACULTY[0])
    resp = client.post("/api/auth/forgot-password", json={"email": ACTIVE_FACULTY[0]})
    assert resp.status_code == 429


def test_full_reset_flow_updates_password_and_revokes_sessions():
    users = _seed_users()
    client = _client()
    email, _, old_password = ACTIVE_FACULTY

    # Existing refresh session must be revoked after reset
    import asyncio

    async def _add_session():
        async with TestSession() as session:
            existing = RefreshSession(
                jti=PREEXISTING_JTI,
                user_id=users["active"].id,
                expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            )
            session.add(existing)
            await session.commit()

    asyncio.run(_add_session())

    _request_otp(client, email)
    otp = _last_otp()
    verify = client.post("/api/auth/verify-reset-otp", json={"email": email, "otp": otp})
    assert verify.status_code == 200
    reset_token = verify.json()["reset_token"]

    done = client.post(
        "/api/auth/reset-password",
        json={"reset_token": reset_token, "new_password": "BrandNewPass9!"},
    )
    assert done.status_code == 200
    assert done.json()["message"] == "Password reset successfully."

    # Old password rejected, new password accepted
    assert client.post("/api/auth/login", json={"email": email, "password": old_password}).status_code == 401
    assert client.post("/api/auth/login", json={"email": email, "password": "BrandNewPass9!"}).status_code == 200

    async def _check_sessions():
        async with TestSession() as session:
            rows = (
                await session.execute(
                    select(RefreshSession).where(RefreshSession.user_id == users["active"].id)
                )
            ).scalars().all()
            user = (
                await session.execute(select(User).where(User.id == users["active"].id))
            ).scalars().first()
            return rows, user

    sessions, user = asyncio.run(_check_sessions())
    # The pre-existing session (created before the reset) must be revoked; the
    # successful post-reset login legitimately created a fresh active session.
    preexisting = [s for s in sessions if s.jti == PREEXISTING_JTI]
    assert preexisting and all(s.revoked for s in preexisting)
    assert security.verify_password("BrandNewPass9!", user.password_hash)
    # Role/status preservation
    assert user.is_active is True
    assert any(r.name.startswith("faculty") for r in user.roles)


def test_reset_token_single_use():
    _seed_users()
    client = _client()
    email = ACTIVE_FACULTY[0]
    _request_otp(client, email)
    _backdate_last_record(seconds=settings.otp_resend_cooldown_seconds + 5)
    verify = client.post(
        "/api/auth/verify-reset-otp", json={"email": email, "otp": _last_otp()}
    )
    reset_token = verify.json()["reset_token"]
    first = client.post(
        "/api/auth/reset-password",
        json={"reset_token": reset_token, "new_password": "FirstReset1!"},
    )
    assert first.status_code == 200
    second = client.post(
        "/api/auth/reset-password",
        json={"reset_token": reset_token, "new_password": "SecondReset2!"},
    )
    assert second.status_code == 400


def test_reset_token_expired_rejected():
    _seed_users()
    client = _client()
    email = ACTIVE_FACULTY[0]
    _request_otp(client, email)
    verify = client.post(
        "/api/auth/verify-reset-otp", json={"email": email, "otp": _last_otp()}
    )
    reset_token = verify.json()["reset_token"]
    import asyncio

    async def _expire():
        async with TestSession() as session:
            record = (
                (await session.execute(select(PasswordResetOtp))).scalars().first()
            )
            record.reset_token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            await session.commit()

    asyncio.run(_expire())
    resp = client.post(
        "/api/auth/reset-password",
        json={"reset_token": reset_token, "new_password": "WhateverPass1!"},
    )
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


def test_reset_password_policy_minimum_length():
    _seed_users()
    client = _client()
    email = ACTIVE_FACULTY[0]
    _request_otp(client, email)
    verify = client.post(
        "/api/auth/verify-reset-otp", json={"email": email, "otp": _last_otp()}
    )
    reset_token = verify.json()["reset_token"]
    # Schema-level rejection (pydantic min_length=8)
    resp = client.post(
        "/api/auth/reset-password",
        json={"reset_token": reset_token, "new_password": "short1!"},
    )
    assert resp.status_code == 422


def test_otp_generation_is_six_digits_and_secure():
    for _ in range(50):
        otp = generate_otp()
        assert len(otp) == 6 and otp.isdigit()


