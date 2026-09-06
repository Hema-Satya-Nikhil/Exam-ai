"""Admin authority + RBAC test suite.

Verifies: admin login from a seeded admin, admin-only route access, faculty
approval/rejection (is_active toggling), faculty denied access to admin-only
routes, and audit-logging of admin actions. Runs on in-memory SQLite.
"""
from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
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

SQLITE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    SQLITE_URL,
    echo=False,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


async def _get_test_db():
    async with TestSession() as session:
        yield session


from app.main import app  # noqa: E402
from app.api.dependencies.auth import get_db  # noqa: E402

client = TestClient(app, raise_server_exceptions=True)

ADMIN_EMAIL = "admin.seed@example.com"
ADMIN_PASS = "AdminPass#2024!"
FACULTY_EMAIL = "faculty.seed@example.com"
FACULTY_PASS = "FacultyPass#2024!"


@pytest_asyncio.fixture(autouse=True)
async def _db_lifecycle():
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _get_test_db
    try:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        admin_role = Role(name="admin", description="Administrator")
        faculty_role = Role(name="faculty", description="Faculty member")
        async with TestSession() as session:
            session.add_all([admin_role, faculty_role])
            await session.flush()
            admin = User(
                email=ADMIN_EMAIL,
                full_name="Admin Seed",
                password_hash=security.hash_password(ADMIN_PASS),
                is_active=True,
                roles=[admin_role],
            )
            pending = User(
                email=FACULTY_EMAIL,
                full_name="Pending Faculty",
                password_hash=security.hash_password(FACULTY_PASS),
                is_active=False,
                roles=[faculty_role],
            )
            session.add_all([admin, pending])
            await session.commit()
        yield
    finally:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous


def _login(email: str, password: str):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _headers(token: str):
    return {"Authorization": f"Bearer {token}"}


async def _get_user_id(email: str) -> str:
    async with TestSession() as session:
        u = (await session.execute(select(User).where(User.email == email))).scalars().first()
        return u.id


def _uid(email: str) -> str:
    return asyncio.run(_get_user_id(email))

# ---------------------------------------------------------------------------
# Admin login + admin-only route access
# ---------------------------------------------------------------------------


def test_admin_login():
    r = _login(ADMIN_EMAIL, ADMIN_PASS)
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client.get("/api/auth/me", headers=_headers(token))
    assert me.status_code == 200
    assert "admin" in me.json()["roles"]


def test_admin_can_list_all_users():
    token = _login(ADMIN_EMAIL, ADMIN_PASS).json()["access_token"]
    r = client.get("/api/admin/users", headers=_headers(token))
    assert r.status_code == 200
    emails = [u["email"] for u in r.json()["users"]]
    assert ADMIN_EMAIL in emails
    assert FACULTY_EMAIL in emails


def test_admin_can_view_pending_faculty():
    token = _login(ADMIN_EMAIL, ADMIN_PASS).json()["access_token"]
    r = client.get("/api/admin/users/pending", headers=_headers(token))
    assert r.status_code == 200
    emails = [u["email"] for u in r.json()["users"]]
    assert FACULTY_EMAIL in emails


# ---------------------------------------------------------------------------
# Faculty denied admin-only routes
# ---------------------------------------------------------------------------


def test_faculty_pending_cannot_login():
    r = _login(FACULTY_EMAIL, FACULTY_PASS)
    # Pending accounts are refused with a distinct 403 + approval-pending message.
    assert r.status_code == 403
    assert "awaiting administrator approval" in r.json()["detail"].lower()


def test_unauth_denied_admin_route():
    assert client.get("/api/admin/users").status_code == 401


# ---------------------------------------------------------------------------
# Admin approve / reject faculty
# ---------------------------------------------------------------------------


def test_admin_approve_faculty_then_faculty_can_login():
    token = _login(ADMIN_EMAIL, ADMIN_PASS).json()["access_token"]

    # pending faculty still blocked
    assert _login(FACULTY_EMAIL, FACULTY_PASS).status_code == 403

    user_id = _uid(FACULTY_EMAIL)
    r = client.post(f"/api/admin/users/{user_id}/approve", headers=_headers(token))
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    # now faculty can log in
    fac = _login(FACULTY_EMAIL, FACULTY_PASS)
    assert fac.status_code == 200

    # but faculty must NOT get admin-only access
    fac_token = fac.json()["access_token"]
    denied = client.get("/api/admin/users", headers=_headers(fac_token))
    assert denied.status_code == 403

    # faculty CAN still use their authenticated session
    me = client.get("/api/auth/me", headers=_headers(fac_token))
    assert me.status_code == 200


def test_admin_reject_faculty_blocks_login():
    token = _login(ADMIN_EMAIL, ADMIN_PASS).json()["access_token"]
    user_id = _uid(FACULTY_EMAIL)
    client.post(f"/api/admin/users/{user_id}/approve", headers=_headers(token))
    assert _login(FACULTY_EMAIL, FACULTY_PASS).status_code == 200

    r = client.post(f"/api/admin/users/{user_id}/reject", headers=_headers(token))
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    # Rejected accounts are refused with a distinct 403 (not generic 401).
    rej = _login(FACULTY_EMAIL, FACULTY_PASS)
    assert rej.status_code == 403
    assert rej.json()["detail"]


# ---------------------------------------------------------------------------
# Audit logging of admin actions
# ---------------------------------------------------------------------------


def test_admin_actions_are_audit_logged():
    from app.models.audit import AuditLog

    token = _login(ADMIN_EMAIL, ADMIN_PASS).json()["access_token"]
    user_id = _uid(FACULTY_EMAIL)
    client.post(f"/api/admin/users/{user_id}/approve", headers=_headers(token))

    r = client.get("/api/admin/audit-logs", headers=_headers(token))
    assert r.status_code == 200
    actions = [log["action"] for log in r.json()["audit_logs"]]
    assert "approve_faculty" in actions
    admin_id = _uid(ADMIN_EMAIL)
    assert any(log["actor_user_id"] == admin_id for log in r.json()["audit_logs"])


def test_admin_self_disable_prevented():
    token = _login(ADMIN_EMAIL, ADMIN_PASS).json()["access_token"]
    admin_id = _uid(ADMIN_EMAIL)
    r = client.post(f"/api/admin/users/{admin_id}/disable", headers=_headers(token))
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Admin access to a staff (faculty+admin) resource
# ---------------------------------------------------------------------------


def test_admin_access_to_protected_resource():
    token = _login(ADMIN_EMAIL, ADMIN_PASS).json()["access_token"]
    me = client.get("/api/auth/me", headers=_headers(token))
    assert me.status_code == 200
    assert "admin" in me.json()["roles"]


# ---------------------------------------------------------------------------
# Faculty self-registration -> pending -> admin approval (new flow)
# ---------------------------------------------------------------------------

NEW_EMAIL = "newfac@example.com"
NEW_PASS = "NewFac#2024!"
NEW_NAME = "New Faculty"


def _register(email=NEW_EMAIL, full_name=NEW_NAME, password=NEW_PASS, role="faculty"):
    return client.post(
        "/api/auth/register",
        json={"email": email, "full_name": full_name, "password": password, "role": role},
    )


def test_register_creates_inactive_faculty_pending_approval():
    # Self-registration succeeds and returns a pending status (no tokens issued).
    r = _register()
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["email"] == NEW_EMAIL

    # Inactive account -> cannot sign in yet (distinct 403, not generic 401).
    assert _login(NEW_EMAIL, NEW_PASS).status_code == 403

    # It shows up in the admin's pending list.
    token = _login(ADMIN_EMAIL, ADMIN_PASS).json()["access_token"]
    pending = client.get("/api/admin/users/pending", headers=_headers(token))
    assert pending.status_code == 200
    assert NEW_EMAIL in [u["email"] for u in pending.json()["users"]]

    # Admin approves -> faculty can now sign in.
    user_id = body["user_id"]
    appr = client.post(f"/api/admin/users/{user_id}/approve", headers=_headers(token))
    assert appr.status_code == 200
    assert appr.json()["status"] == "approved"
    assert _login(NEW_EMAIL, NEW_PASS).status_code == 200


def test_register_duplicate_email_returns_conflict():
    assert _register().status_code == 201
    dup = _register()
    assert dup.status_code == 409


def test_register_cannot_self_promote_to_admin():
    r = _register(role="admin")
    assert r.status_code == 201
    assert r.json()["status"] == "pending"

    token = _login(ADMIN_EMAIL, ADMIN_PASS).json()["access_token"]
    client.post(f"/api/admin/users/{r.json()['user_id']}/approve", headers=_headers(token))

    fac = _login(NEW_EMAIL, NEW_PASS)
    assert fac.status_code == 200
    fac_token = fac.json()["access_token"]
    me = client.get("/api/auth/me", headers=_headers(fac_token))
    assert me.status_code == 200
    assert me.json()["roles"] == ["faculty"]
    # A self-promoted account still cannot reach admin-only routes.
    assert client.get("/api/admin/users", headers=_headers(fac_token)).status_code == 403
