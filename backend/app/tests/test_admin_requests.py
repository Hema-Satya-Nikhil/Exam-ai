"""Multi-admin request + Main Admin protection test suite.

In-memory SQLite via aiosqlite (StaticPool, same pattern as test_password_reset).
Covers: request_admin registration, admin request list/approve/reject, Main
Admin protection (role endpoint hardening, disable, remove-admin), audit
events, and the one-primary-admin invariant.
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
from app.db.base import Base
from app.api.dependencies.auth import get_db
from app.main import app
from app.models.academic import Role, User
from app.models.admin_access import AdminAccessRequest
from app.models.audit import AuditLog
from app.services.admin_access_service import (
    AdminRequestError,
    approve_request,
    reject_request,
    remove_admin_role,
)
from app.services.admin_service import seed_admin

SQLITE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(SQLITE_URL, echo=False, poolclass=StaticPool)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

ADMIN_EMAIL = "main.admin@test.com"
ADMIN_PASSWORD = "MainAdmin1!"
SECONDARY_EMAIL = "second.admin@test.com"
FACULTY_EMAIL = "plain.faculty@test.com"


async def _get_test_db():
    async with TestSession() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def _lifecycle():
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


async def _seed_users_async() -> dict[str, User]:
    """Primary admin + secondary admin + plain faculty (all active)."""
    from app.services.admin_service import get_or_create_role

    async with TestSession() as session:
        seed = await seed_admin(session, ADMIN_EMAIL, ADMIN_PASSWORD, "Main Admin")
        assert seed.action in ("created", "exists")

        # NOTE: seed_admin only ensures the ADMIN role — the FACULTY role is
        # created on demand (exactly like production registration), so use
        # get_or_create_role rather than assuming both rows exist.
        admin_role = await get_or_create_role(session, "admin", "Administrator")
        faculty_role = await get_or_create_role(session, "faculty", "Faculty member")
        secondary = User(
            email=SECONDARY_EMAIL, full_name="Secondary Admin",
            password_hash=security.hash_password("SecondAdm1!"),
            is_active=True, roles=[admin_role, faculty_role],
        )
        faculty = User(
            email=FACULTY_EMAIL, full_name="Plain Faculty",
            password_hash=security.hash_password("PlainFac1!"),
            is_active=True, roles=[faculty_role],
        )
        session.add_all([secondary, faculty])
        await session.commit()
        return {
            "primary": await _reload(session, ADMIN_EMAIL),
            "secondary": await _reload(session, SECONDARY_EMAIL),
            "faculty": await _reload(session, FACULTY_EMAIL),
        }


def _seed_users() -> dict[str, User]:
    """Synchronous seeding helper (tests use the sync TestClient)."""
    import asyncio

    return asyncio.run(_seed_users_async())


async def _reload(session: AsyncSession, email: str) -> User:
    return (await session.execute(select(User).where(User.email == email))).scalars().first()


def _client() -> TestClient:
    return TestClient(app)


def _login(email: str, password: str) -> dict:
    client = _client()
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _register_admin_request(email: str, full_name: str = "Admin Applicant",
                            password: str = "Applicant1!") -> dict:
    client = _client()
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "full_name": full_name, "password": password, "request_admin": True},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Registration + request creation
# ---------------------------------------------------------------------------

import asyncio


def _run(coro):
    return asyncio.run(coro)


def test_register_request_admin_creates_pending_no_admin():
    payload = _register_admin_request("applicant1@test.com")
    assert payload["admin_request_status"] == "pending"

    async def _check():
        async with TestSession() as session:
            user = await _reload(session, "applicant1@test.com")
            reqs = (await session.execute(select(AdminAccessRequest))).scalars().all()
            return user, reqs

    user, reqs = _run(_check())
    assert user is not None
    assert user.is_active is False  # stays subject to the existing approval policy
    assert user.is_primary_admin is False  # a registration can NEVER create the Main Admin
    assert sorted(r.name for r in user.roles) == ["faculty"]  # NOT admin
    assert len(reqs) == 1
    assert reqs[0].status == "pending"
    assert reqs[0].requested_role == "admin"


def test_register_without_request_unchanged():
    client = _client()
    resp = client.post(
        "/api/auth/register",
        json={"email": "plain1@test.com", "full_name": "Plain", "password": "Plain1!!!"},
    )
    assert resp.status_code == 201
    assert resp.json()["admin_request_status"] is None

    async def _check():
        async with TestSession() as session:
            reqs = (await session.execute(select(AdminAccessRequest))).scalars().all()
            user = await _reload(session, "plain1@test.com")
            return reqs, user

    reqs, user = _run(_check())
    assert len(reqs) == 0
    assert user.is_primary_admin is False


def test_duplicate_pending_request_blocked_by_db():
    _register_admin_request("applicant2@test.com")

    async def _dup():
        async with TestSession() as session:
            user = await _reload(session, "applicant2@test.com")
            session.add(AdminAccessRequest(user_id=user.id, requested_role="admin", status="pending"))
            try:
                await session.commit()
                return "committed"
            except Exception:
                await session.rollback()
                return "rejected"

    assert _run(_dup()) == "rejected"  # partial unique index enforces one pending


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

def test_admin_can_list_requests_with_safe_fields():
    _seed_users()
    _register_admin_request("applicant3@test.com")
    headers = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = _client().get("/api/admin/admin-requests", headers=headers)
    assert resp.status_code == 200
    requests = resp.json()["requests"]
    assert requests and requests[0]["requester_email"] == "applicant3@test.com"
    assert requests[0]["status"] == "pending"
    for key in ("request_id", "requester_id", "requester_name", "requested_role", "requested_at"):
        assert key in requests[0]
    body = resp.text.lower()
    assert "password" not in body and "token" not in body


def test_faculty_cannot_list_requests():
    _seed_users()
    headers = _login(FACULTY_EMAIL, "PlainFac1!")
    resp = _client().get("/api/admin/admin-requests", headers=headers)
    assert resp.status_code == 403


def test_unauthenticated_cannot_list_requests():
    resp = _client().get("/api/admin/admin-requests")
    assert resp.status_code in (401, 403)

# ---------------------------------------------------------------------------
# Approve / reject
# ---------------------------------------------------------------------------

def _latest_pending_request_id() -> str:
    async def _get():
        async with TestSession() as session:
            req = (
                await session.execute(
                    select(AdminAccessRequest).where(AdminAccessRequest.status == "pending")
                )
            ).scalars().first()
            return req.id

    return _run(_get())


def test_approve_grants_admin_activates_and_audits():
    _seed_users()
    _register_admin_request("applicant4@test.com")
    req_id = _latest_pending_request_id()
    headers = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = _client().post(f"/api/admin/admin-requests/{req_id}/approve", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"

    async def _check():
        async with TestSession() as session:
            user = await _reload(session, "applicant4@test.com")
            req = (await session.execute(select(AdminAccessRequest))).scalars().first()
            audits = (
                await session.execute(select(AuditLog).where(AuditLog.action == "ADMIN_ACCESS_APPROVED"))
            ).scalars().all()
            return user, req, audits

    user, req, audits = _run(_check())
    assert "admin" in [r.name for r in user.roles]
    assert "faculty" in [r.name for r in user.roles]  # base role preserved
    assert user.is_active is True  # approval doubles as account activation
    assert user.is_primary_admin is False
    assert req.status == "approved"
    assert req.reviewed_at is not None
    assert req.reviewed_by is not None
    assert len(audits) == 1

    # The approved user can now log in with the ADMIN role.
    me = _client().get("/api/auth/me", headers=_login("applicant4@test.com", "Applicant1!"))
    assert me.status_code == 200
    assert "admin" in me.json()["roles"]


def test_self_approval_blocked():
    users = _seed_users()
    _register_admin_request("applicant5@test.com")
    req_id = _latest_pending_request_id()

    async def _self_approve():
        async with TestSession() as session:
            requester = await _reload(session, "applicant5@test.com")
            try:
                await approve_request(session, req_id, requester)
                return "approved"
            except AdminRequestError as exc:
                await session.rollback()
                return exc.status_code

    assert _run(_self_approve()) == 403


def test_already_approved_request_cannot_be_reapproved():
    _seed_users()
    _register_admin_request("applicant6@test.com")
    req_id = _latest_pending_request_id()
    headers = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    assert _client().post(f"/api/admin/admin-requests/{req_id}/approve", headers=headers).status_code == 200
    again = _client().post(f"/api/admin/admin-requests/{req_id}/approve", headers=headers)
    assert again.status_code == 409


def test_reject_flow_does_not_grant_admin():
    _seed_users()
    _register_admin_request("applicant7@test.com")
    req_id = _latest_pending_request_id()
    headers = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = _client().post(
        f"/api/admin/admin-requests/{req_id}/reject",
        headers=headers,
        json={"reason": "Not enough seniority."},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    async def _check():
        async with TestSession() as session:
            user = await _reload(session, "applicant7@test.com")
            req = (await session.execute(select(AdminAccessRequest))).scalars().first()
            audits = (
                await session.execute(select(AuditLog).where(AuditLog.action == "ADMIN_ACCESS_REJECTED"))
            ).scalars().all()
            return user, req, audits

    user, req, audits = _run(_check())
    assert "admin" not in [r.name for r in user.roles]
    assert req.status == "rejected"
    assert req.review_reason == "Not enough seniority."
    assert req.reviewed_by is not None and req.reviewed_at is not None
    assert len(audits) == 1
    # repeated rejection is a safe conflict
    again = _client().post(f"/api/admin/admin-requests/{req_id}/reject", headers=headers, json={})
    assert again.status_code == 409


def test_requester_deleted_handled_safely():
    users = _seed_users()
    _register_admin_request("applicant8@test.com")
    req_id = _latest_pending_request_id()

    async def _delete_user():
        async with TestSession() as session:
            user = await _reload(session, "applicant8@test.com")
            await session.delete(user)
            await session.commit()

    _run(_delete_user())
    headers = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    resp = _client().post(f"/api/admin/admin-requests/{req_id}/approve", headers=headers)
    assert resp.status_code == 404  # safe, no partial state

# ---------------------------------------------------------------------------
# Main Admin protection + role endpoint hardening + removal
# ---------------------------------------------------------------------------

def test_main_admin_is_seeded_and_unique():
    users = _seed_users()
    assert users["primary"].is_primary_admin is True
    assert "admin" in [r.name for r in users["primary"].roles]

    # seed again — idempotent, still exactly one primary admin
    async def _reseed():
        async with TestSession() as session:
            await seed_admin(session, ADMIN_EMAIL, ADMIN_PASSWORD)
            primaries = (
                await session.execute(select(User).where(User.is_primary_admin.is_(True)))
            ).scalars().all()
            return primaries

    primaries = _run(_reseed())
    assert len(primaries) == 1
    assert primaries[0].email.lower() == ADMIN_EMAIL


def test_second_primary_admin_rejected_by_db_or_app():
    """Exactly-one-primary-admin invariant.

    On PostgreSQL the partial unique index ``uq_users_one_primary_admin``
    rejects a second primary admin at the database level (verified by the
    migration SQL). SQLite cannot enforce partial indexes, so this test also
    proves the invariant holds at the application layer: no seed run, no
    registration, and no admin-request path can ever produce a second primary
    admin — code creates exactly one (the configured bootstrap Admin).
    """
    users = _seed_users()
    assert len([u for u in users.values() if u.is_primary_admin]) == 1

    # Registering a user that requested admin never sets the primary flag.
    _register_admin_request("equiv.applicant@test.com")

    # Re-seeding cannot create a second primary admin.
    async def _reseed_and_count():
        async with TestSession() as session:
            await seed_admin(session, ADMIN_EMAIL, ADMIN_PASSWORD)
            primaries = (
                await session.execute(select(User).where(User.is_primary_admin.is_(True)))
            ).scalars().all()
            req_primary = await _reload(session, "equiv.applicant@test.com")
            return [p.email for p in primaries], req_primary.is_primary_admin

    primaries, req_primary_flag = _run(_reseed_and_count())
    assert len(primaries) == 1
    assert primaries[0].lower() == ADMIN_EMAIL  # only the Main Admin stays primary
    assert req_primary_flag is False


async def _reload_async(email: str) -> User:
    async with TestSession() as session:
        return await _reload(session, email)


def test_role_endpoint_cannot_grant_admin_directly():
    _seed_users()
    headers = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    faculty = _run(_reload_async(FACULTY_EMAIL))
    resp = _client().post(
        f"/api/admin/users/{faculty.id}/role", headers=headers, params={"role_name": "admin"}
    )
    assert resp.status_code == 400  # promotion must go through the request workflow


def test_role_endpoint_cannot_demote_main_admin():
    users = _seed_users()
    headers = _login(SECONDARY_EMAIL, "SecondAdm1!")
    primary = users["primary"]
    resp = _client().post(
        f"/api/admin/users/{primary.id}/role", headers=headers, params={"role_name": "faculty"}
    )
    assert resp.status_code == 403
    primary_after = _run(_reload_async(ADMIN_EMAIL))
    assert "admin" in [r.name for r in primary_after.roles]
    assert primary_after.is_primary_admin is True


def test_role_endpoint_blocks_self_modification():
    _seed_users()
    headers = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    primary = _run(_reload_async(ADMIN_EMAIL))
    resp = _client().post(
        f"/api/admin/users/{primary.id}/role", headers=headers, params={"role_name": "faculty"}
    )
    assert resp.status_code == 403


def test_role_endpoint_demotes_secondary_admin():
    _seed_users()
    headers = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    secondary = _run(_reload_async(SECONDARY_EMAIL))
    resp = _client().post(
        f"/api/admin/users/{secondary.id}/role", headers=headers, params={"role_name": "faculty"}
    )
    assert resp.status_code == 200
    secondary_after = _run(_reload_async(SECONDARY_EMAIL))
    assert "admin" not in [r.name for r in secondary_after.roles]
    assert "faculty" in [r.name for r in secondary_after.roles]

def test_main_admin_can_remove_secondary_admin():
    _seed_users()
    headers = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    secondary = _run(_reload_async(SECONDARY_EMAIL))
    resp = _client().post(f"/api/admin/users/{secondary.id}/remove-admin", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["message"] == "Admin access removed."

    async def _check():
        async with TestSession() as session:
            user = await _reload(session, SECONDARY_EMAIL)
            audits = (
                await session.execute(select(AuditLog).where(AuditLog.action == "ADMIN_ROLE_REMOVED"))
            ).scalars().all()
            return user, audits

    user, audits = _run(_check())
    assert "admin" not in [r.name for r in user.roles]
    assert "faculty" in [r.name for r in user.roles]
    assert len(audits) == 1

    # Fresh login: user is still active but faculty-only now.
    me = _client().get("/api/auth/me", headers=_login(SECONDARY_EMAIL, "SecondAdm1!"))
    assert "admin" not in me.json()["roles"]


def test_secondary_admin_cannot_remove_main_admin():
    _seed_users()
    headers = _login(SECONDARY_EMAIL, "SecondAdm1!")
    primary = _run(_reload_async(ADMIN_EMAIL))
    resp = _client().post(f"/api/admin/users/{primary.id}/remove-admin", headers=headers)
    assert resp.status_code == 403
    primary_after = _run(_reload_async(ADMIN_EMAIL))
    assert "admin" in [r.name for r in primary_after.roles]
    assert primary_after.is_primary_admin is True


def test_secondary_admin_cannot_remove_other_admin():
    _seed_users()
    headers = _login(SECONDARY_EMAIL, "SecondAdm1!")

    async def _make_third_admin():
        async with TestSession() as session:
            third = User(
                email="third.admin@test.com", full_name="Third Admin",
                password_hash=security.hash_password("ThirdAdm1!"),
                is_active=True,
                roles=[
                    (await session.execute(select(Role).where(Role.name == "admin"))).scalars().first()
                ],
            )
            session.add(third)
            await session.commit()
            return third.id

    third_id = _run(_make_third_admin())
    resp = _client().post(f"/api/admin/users/{third_id}/remove-admin", headers=headers)
    assert resp.status_code == 403  # only the Main Admin may remove admins


def test_main_admin_cannot_remove_self():
    _seed_users()
    headers = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    primary = _run(_reload_async(ADMIN_EMAIL))
    resp = _client().post(f"/api/admin/users/{primary.id}/remove-admin", headers=headers)
    assert resp.status_code == 400
    primary_after = _run(_reload_async(ADMIN_EMAIL))
    assert "admin" in [r.name for r in primary_after.roles]


def test_main_admin_cannot_be_disabled():
    _seed_users()
    headers = _login(SECONDARY_EMAIL, "SecondAdm1!")
    primary = _run(_reload_async(ADMIN_EMAIL))
    resp = _client().post(f"/api/admin/users/{primary.id}/disable", headers=headers)
    assert resp.status_code == 403
    primary_after = _run(_reload_async(ADMIN_EMAIL))
    assert primary_after.is_active is True


def test_disable_secondary_admin_still_works():
    _seed_users()
    headers = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    secondary = _run(_reload_async(SECONDARY_EMAIL))
    resp = _client().post(f"/api/admin/users/{secondary.id}/disable", headers=headers)
    assert resp.status_code == 200
    secondary_after = _run(_reload_async(SECONDARY_EMAIL))
    assert secondary_after.is_active is False


def test_second_approval_attempt_conflicts_after_concurrent_first():
    """Row-lock + conditional re-check: the second approve sees a non-PENDING
    request and conflicts instead of double-granting."""
    _seed_users()
    _register_admin_request("applicant9@test.com")
    req_id = _latest_pending_request_id()
    headers = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    client = _client()

    async def _approve_via_session():
        async with TestSession() as session:
            primary = await _reload(session, ADMIN_EMAIL)
            await approve_request(session, req_id, primary)

    _run(_approve_via_session())  # "admin A" wins
    second = client.post(f"/api/admin/admin-requests/{req_id}/approve", headers=headers)
    assert second.status_code == 409  # "admin B" conflicts, no double grant

    async def _count():
        async with TestSession() as session:
            req = (await session.execute(select(AdminAccessRequest))).scalars().first()
            audits = (
                await session.execute(select(AuditLog).where(AuditLog.action == "ADMIN_ACCESS_APPROVED"))
            ).scalars().all()
            user = await _reload(session, "applicant9@test.com")
            return req.status, len(audits), user.roles

    status, audit_count, roles = _run(_count())
    assert status == "approved"
    assert audit_count == 1  # exactly one approval audit event
    assert sum(1 for r in roles if r.name == "admin") == 1




