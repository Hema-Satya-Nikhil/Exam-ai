"""Admin bootstrap test suite — initial administrator seed + RBAC.

Runs on an in-memory SQLite database (aiosqlite) so no real PostgreSQL is
required, mirroring ``test_auth.py`` / ``test_export_service.py``.

Coverage (task requirement):
  1. admin creation (only when the email does not already exist)
  2. password hashing (bcrypt; plaintext never stored)
  3. ADMIN role assignment
  4. idempotent second seed (no duplicate users / roles, password preserved)
  5. login with the seeded admin (normal auth flow)
  6. faculty user cannot access admin-only functionality (403)
  7. admin can approve/reject pending faculty accounts

Only dummy credentials are used here — the real admin password lives solely in
the local ``.env`` and never appears in source, tests, logs, or output.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.future import select
from sqlalchemy.pool import StaticPool

from app.core import security
from app.db.base import Base
from app.models.academic import Role, User
from app.services import admin_service

# ---------------------------------------------------------------------------
# Test database — a single shared in-memory SQLite connection
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    SQLITE_URL,
    echo=False,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


async def _get_test_db():
    """Override for app.api.dependencies.auth.get_db."""
    async with TestSession() as session:
        yield session


# ---------------------------------------------------------------------------
# App — the DB dependency override is installed/restored by _db_lifecycle so
# multiple test modules sharing the same app instance do not clobber each other.
# ---------------------------------------------------------------------------

from app.main import app  # noqa: E402
from app.api.dependencies.auth import get_db  # noqa: E402

client = TestClient(app, raise_server_exceptions=True)

# Dummy account used by this suite; the real ADMIN_* credentials live in .env.
ADMIN_TEST_EMAIL = "admin.seed@example.com"
ADMIN_TEST_PASSWORD = "SeedPass#2024!X"


@pytest_asyncio.fixture(autouse=True)
async def _db_lifecycle():
    """Create tables, yield, then drop tables + restore the get_db override."""
    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _get_test_db
    try:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
    finally:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override


async def _seed_admin(session: AsyncSession):
    """Seed the admin once and return the result + entity."""
    result = await admin_service.seed_admin(
        session, email=ADMIN_TEST_EMAIL, password=ADMIN_TEST_PASSWORD
    )
    user = (await session.execute(
        select(User).where(User.email == ADMIN_TEST_EMAIL)
    )).scalars().first()
    return result, user
# ---------------------------------------------------------------------------
# 1 — Admin creation
# ---------------------------------------------------------------------------

async def test_admin_creation_creates_user_once():
    async with TestSession() as session:
        result, user = await _seed_admin(session)
        assert result.action == "created"
        assert user is not None
        assert user.email == ADMIN_TEST_EMAIL
        assert user.is_active is True


# ---------------------------------------------------------------------------
# 2 — Password hashing (plaintext never stored)
# ---------------------------------------------------------------------------

async def test_admin_password_is_hashed_not_plaintext():
    async with TestSession() as session:
        _, user = await _seed_admin(session)
        assert user.password_hash != ADMIN_TEST_PASSWORD
        assert user.password_hash.startswith("$2")  # bcrypt
        assert security.verify_password(ADMIN_TEST_PASSWORD, user.password_hash) is True


# ---------------------------------------------------------------------------
# 3 — ADMIN role assignment (and no duplicate roles)
# ---------------------------------------------------------------------------

async def test_admin_gets_admin_role_and_no_duplicate_roles():
    async with TestSession() as session:
        await admin_service.ensure_roles(session)
        _, user = await _seed_admin(session)
        role_names = {role.name for role in user.roles}
        assert "admin" in role_names
        # Second seed must not create a second admin role row.
        await admin_service.seed_admin(session, email=ADMIN_TEST_EMAIL, password=ADMIN_TEST_PASSWORD)
        admin_role_count = len((await session.execute(
            select(Role).where(Role.name == "admin")
        )).scalars().all())
        assert admin_role_count == 1


# ---------------------------------------------------------------------------
# 4 — Idempotent second seed
# ---------------------------------------------------------------------------

async def test_seed_is_idempotent_and_keeps_password():
    async with TestSession() as session:
        first, user = await _seed_admin(session)
        assert first.action == "created"
        hash_before = user.password_hash
        user_id = user.id

        second, user_again = await _seed_admin(session)
        assert second.action == "exists"
        assert user_again.id == user_id
        assert user_again.password_hash == hash_before  # password never overwritten
        assert user_again.is_active is True

        duplicates = len((await session.execute(
            select(User).where(User.email == ADMIN_TEST_EMAIL)
        )).scalars().all())
        assert duplicates == 1


# ---------------------------------------------------------------------------
# 5 — Login with the seeded admin (normal auth flow)
# ---------------------------------------------------------------------------

async def test_seeded_admin_can_login_and_has_admin_permissions():
    async with TestSession() as session:
        await _seed_admin(session)

    login = client.post(
        "/api/auth/login",
        json={"email": ADMIN_TEST_EMAIL, "password": ADMIN_TEST_PASSWORD},
    )
    assert login.status_code == 200
    data = login.json()
    assert data.get("access_token")
    assert data.get("refresh_token")
    assert data.get("token_type") == "bearer"

    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == ADMIN_TEST_EMAIL
    assert "admin" in me.json()["roles"]
# ---------------------------------------------------------------------------
# 6 — Faculty cannot access admin-only functionality
# ---------------------------------------------------------------------------

def test_faculty_rejected_by_admin_only_dependency():
    from app.api.dependencies.auth import require_roles

    checker = require_roles("admin")

    faculty_ctx = MagicMock()
    faculty_ctx.roles = ["faculty"]
    with pytest.raises(HTTPException) as excinfo:
        checker(current_user=faculty_ctx)
    assert excinfo.value.status_code == 403

    admin_ctx = MagicMock()
    admin_ctx.roles = ["admin"]
    assert checker(current_user=admin_ctx) is admin_ctx


async def test_faculty_role_never_granted_admin():
    """A faculty-role account stays non-admin even after seeding both roles."""
    async with TestSession() as session:
        faculty_role = await admin_service.get_or_create_role(session, "faculty", "Faculty member")
        faculty = User(
            email="faculty.seed@example.com",
            full_name="Faculty Seed",
            password_hash=security.hash_password("FacultyPass#2024!"),
            is_active=True,
            roles=[faculty_role],
        )
        session.add(faculty)
        await session.commit()

    login = client.post(
        "/api/auth/login",
        json={"email": "faculty.seed@example.com", "password": "FacultyPass#2024!"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert "admin" not in me.json()["roles"]


# ---------------------------------------------------------------------------
# 7 — Admin can approve / reject pending faculty accounts
# ---------------------------------------------------------------------------

async def test_admin_can_approve_and_reject_pending_faculty():
    async with TestSession() as session:
        faculty_role = await admin_service.get_or_create_role(session, "faculty", "Faculty member")
        pending = User(
            email="pending.faculty@example.com",
            full_name="Pending Faculty",
            password_hash=security.hash_password("PendingPass#2024!"),
            is_active=False,  # pending account — awaiting admin approval
            roles=[faculty_role],
        )
        session.add(pending)
        await session.commit()
        pending_id = pending.id

    # Pending (inactive) account cannot log in yet — distinct 403, not generic 401.
    blocked = client.post(
        "/api/auth/login",
        json={"email": "pending.faculty@example.com", "password": "PendingPass#2024!"},
    )
    assert blocked.status_code == 403
    assert "awaiting administrator approval" in blocked.json()["detail"].lower()

    # Admin approves -> active -> login works.
    async with TestSession() as session:
        assert await admin_service.approve_faculty(session, pending_id) is True
    approved = client.post(
        "/api/auth/login",
        json={"email": "pending.faculty@example.com", "password": "PendingPass#2024!"},
    )
    assert approved.status_code == 200

    # Admin rejects -> inactive -> login refused again.
    async with TestSession() as session:
        assert await admin_service.reject_faculty(session, pending_id) is True
        user_check = (await session.execute(
            select(User).where(User.id == pending_id)
        )).scalars().first()
        assert user_check is not None and user_check.is_active is False

    re_login = client.post(
        "/api/auth/login",
        json={"email": "pending.faculty@example.com", "password": "PendingPass#2024!"},
    )
    assert re_login.status_code == 403
    assert re_login.json()["detail"]


async def test_approve_reject_unknown_user_returns_false():
    async with TestSession() as session:
        assert await admin_service.approve_faculty(session, "missing-user-id") is False
        assert await admin_service.reject_faculty(session, "missing-user-id") is False