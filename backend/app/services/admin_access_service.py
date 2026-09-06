"""Admin access request workflow service (multi-admin onboarding).

Security model
--------------
* A request is a *workflow state* — it never grants anything by itself.
* Only an authenticated ADMIN (route RBAC) may list/approve/reject; approval
  additionally requires the reviewer's DB user row to be authoritative.
* Self-approval / self-rejection is forbidden.
* Approval is ATOMIC and row-locked (``with_for_update``) so two concurrent
  approvals produce exactly one ADMIN grant, one APPROVED state and one audit
  event.
* Only the protected Main Admin (``users.is_primary_admin``) may remove another
  admin's ADMIN role — never itself, never the Main Admin.
* Every state change is audit-logged (ADMIN_ACCESS_REQUESTED / _APPROVED /
  _REJECTED / ADMIN_ROLE_REMOVED) with no secrets in payloads.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import User
from app.models.admin_access import AdminAccessRequest
from app.models.audit import AuditLog
from app.services.admin_service import get_or_create_role

ADMIN_ROLE = "admin"
FACULTY_ROLE = "faculty"
PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AdminRequestError(Exception):
    """Client-facing admin-request failure (detail is safe to show)."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


async def _log_action(
    session: AsyncSession,
    actor_user_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str,
    payload: dict | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload or {},
        )
    )
    await session.flush()


async def _get_db_user(session: AsyncSession, user_id: str) -> User | None:
    return (await session.execute(select(User).where(User.id == user_id))).scalars().first()


async def has_role(user: User, role_name: str) -> bool:
    return any(role.name == role_name for role in user.roles)


def _serialize(req: AdminAccessRequest, requester: User | None, reviewer: User | None) -> dict:
    return {
        "request_id": req.id,
        "requester_id": req.user_id,
        "requester_email": requester.email if requester else None,
        "requested_role": req.requested_role,
        "status": req.status,
        "requested_at": req.requested_at.isoformat() if req.requested_at else None,
        "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
        "reviewer": reviewer.email if reviewer else None,
        "review_reason": req.review_reason,
    }


async def list_requests(session: AsyncSession, status: str | None = None) -> list[dict]:
    """Newest-first admin requests with safe requester/reviewer data."""
    stmt = select(AdminAccessRequest).order_by(AdminAccessRequest.requested_at.desc())
    if status:
        stmt = stmt.where(AdminAccessRequest.status == status.lower())
    rows = (await session.execute(stmt)).scalars().all()
    result: list[dict] = []
    for req in rows:
        requester = req.user  # selectin-loaded
        reviewer = await _get_db_user(session, req.reviewed_by) if req.reviewed_by else None
        result.append(
            {
                "request_id": req.id,
                "requester_id": req.user_id,
                "requester_name": requester.full_name if requester else None,
                "requester_email": requester.email if requester else None,
                "requester_is_active": requester.is_active if requester else None,
                "requested_role": req.requested_role,
                "status": req.status,
                "requested_at": req.requested_at.isoformat() if req.requested_at else None,
                "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
                "reviewer": reviewer.email if reviewer else None,
                "review_reason": req.review_reason,
            }
        )
    return result


async def _load_pending_locked(session: AsyncSession, request_id: str) -> AdminAccessRequest:
    """Load a request with a row lock, enforcing existence + PENDING state."""
    stmt = (
        select(AdminAccessRequest)
        .where(AdminAccessRequest.id == request_id)
        .with_for_update()
    )
    req = (await session.execute(stmt)).scalars().first()
    if req is None:
        raise AdminRequestError(404, "Admin access request not found.")
    if req.status != PENDING:
        raise AdminRequestError(
            409, f"This admin access request has already been {req.status}."
        )
    return req


async def approve_request(session: AsyncSession, request_id: str, reviewer: User) -> dict:
    """Atomically approve a PENDING request: grant ADMIN + activate + audit."""
    req = await _load_pending_locked(session, request_id)

    if req.user_id == reviewer.id:
        raise AdminRequestError(403, "You cannot approve your own admin access request.")

    requester = await _get_db_user(session, req.user_id)
    if requester is None:
        raise AdminRequestError(404, "The requesting user no longer exists.")

    if await has_role(requester, ADMIN_ROLE):
        # Already an admin — nothing to grant; leave the pending request alone.
        raise AdminRequestError(409, "This user already has admin access.")

    admin_role = await get_or_create_role(session, ADMIN_ROLE, "Administrator")
    if not await has_role(requester, ADMIN_ROLE):
        requester.roles.append(admin_role)

    # Approval doubles as the existing account-approval step: the applicant can
    # now authenticate (the account was created inactive by registration).
    requester.is_active = True

    req.status = APPROVED
    req.reviewed_at = _now()
    req.reviewed_by = reviewer.id

    await _log_action(
        session,
        reviewer.id,
        "ADMIN_ACCESS_APPROVED",
        "admin_access_request",
        req.id,
        {
            "target_user_id": requester.id,
            "target_email": requester.email,
            "resulting_status": APPROVED,
        },
    )
    await session.commit()
    return _serialize(req, requester, reviewer)


async def reject_request(
    session: AsyncSession, request_id: str, reviewer: User, reason: str | None = None
) -> dict:
    """Reject a PENDING request. Never grants ADMIN."""
    req = await _load_pending_locked(session, request_id)

    if req.user_id == reviewer.id:
        raise AdminRequestError(403, "You cannot review your own admin access request.")

    requester = await _get_db_user(session, req.user_id)

    req.status = REJECTED
    req.reviewed_at = _now()
    req.reviewed_by = reviewer.id
    req.review_reason = (reason or "").strip() or None

    await _log_action(
        session,
        reviewer.id,
        "ADMIN_ACCESS_REJECTED",
        "admin_access_request",
        req.id,
        {
            "target_user_id": req.user_id,
            "target_email": requester.email if requester else None,
            "resulting_status": REJECTED,
        },
    )
    await session.commit()
    return _serialize(req, requester, reviewer)


async def remove_admin_role(session: AsyncSession, actor: User, target_user_id: str) -> dict:
    """Main-Admin-only: remove another admin's ADMIN role (keeps the account).

    The Main Admin can never be a target, and the actor can never target
    themselves — enforced here even if a client bypasses the route checks.
    """
    if not actor.is_primary_admin:
        raise AdminRequestError(403, "Only the main administrator can remove admin access.")
    if target_user_id == actor.id:
        raise AdminRequestError(
            400, "The main administrator cannot remove their own admin access."
        )

    target = await _get_db_user(session, target_user_id)
    if target is None:
        raise AdminRequestError(404, "User not found")
    if target.is_primary_admin:
        raise AdminRequestError(403, "The main administrator account cannot be modified.")

    if not await has_role(target, ADMIN_ROLE):
        raise AdminRequestError(409, "This user does not have admin access.")

    admin_role = next(role for role in target.roles if role.name == ADMIN_ROLE)
    target.roles.remove(admin_role)

    # Keep a base role so the account remains a functional faculty member.
    if not await has_role(target, FACULTY_ROLE):
        faculty_role = await get_or_create_role(session, FACULTY_ROLE, "Faculty member")
        target.roles.append(faculty_role)

    await _log_action(
        session,
        actor.id,
        "ADMIN_ROLE_REMOVED",
        "user",
        target.id,
        {"target_email": target.email, "previous_role": ADMIN_ROLE},
    )
    await session.commit()
    return {
        "user_id": target.id,
        "email": target.email,
        "roles": [role.name for role in target.roles],
    }



