"""Admin-only account management and audit-log access.

Every mutating admin action (approve / reject / disable) is recorded in
``audit_logs`` with the acting admin's user id. Route-level RBAC is enforced
by ``require_roles(\"admin\")`` attached in ``app/api/router.py``.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user, get_db
from app.models.academic import Role, User, user_roles
from app.models.audit import AuditLog

router = APIRouter()


async def _log_admin_action(
    session: AsyncSession,
    actor_user_id: str,
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


async def _get_user_or_404(session: AsyncSession, user_id: str) -> User:
    user = (await session.execute(select(User).where(User.id == user_id))).scalars().first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _user_dict(user: User) -> dict:
    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "is_primary_admin": user.is_primary_admin,
        "roles": [role.name for role in user.roles],
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


async def _get_db_user(session: AsyncSession, user_id: str) -> User | None:
    """Load the authoritative DB row for the acting user (primary-admin flag)."""
    return (await session.execute(select(User).where(User.id == user_id))).scalars().first()


class RejectAdminRequestBody(BaseModel):
    reason: str | None = None


@router.get("/users")
async def list_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    rows = (await db.execute(select(User).order_by(User.created_at.desc()))).scalars().all()
    return {"users": [_user_dict(u) for u in rows]}


@router.get("/users/pending")
async def list_pending_faculty(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """List inactive (pending approval) faculty accounts."""
    faculty_role = (await db.execute(select(Role).where(Role.name == "faculty"))).scalars().first()
    rows: list[User] = []
    if faculty_role is not None:
        stmt = (
            select(User)
            .join(user_roles, user_roles.c.user_id == User.id)
            .where(user_roles.c.role_id == faculty_role.id, User.is_active.is_(False))
            .order_by(User.created_at.desc())
        )
        rows = (await db.execute(stmt)).scalars().all()
    return {"users": [_user_dict(u) for u in rows]}


@router.post("/users/{user_id}/approve")
async def approve_faculty(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user = await _get_user_or_404(db, user_id)
    user.is_active = True
    await _log_admin_action(db, current_user.user_id, "approve_faculty", "user", user.id, {"email": user.email})
    await db.commit()
    return {"user_id": user.id, "status": "approved", "email": user.email}


@router.post("/users/{user_id}/reject")
async def reject_faculty(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user = await _get_user_or_404(db, user_id)
    user.is_active = False
    await _log_admin_action(db, current_user.user_id, "reject_faculty", "user", user.id, {"email": user.email})
    await db.commit()
    return {"user_id": user.id, "status": "rejected", "email": user.email}


@router.post("/users/{user_id}/disable")
async def disable_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user = await _get_user_or_404(db, user_id)
    if user.id == current_user.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admins cannot disable their own account.")
    if user.is_primary_admin:
        # The protected Main Admin can never be disabled through any admin API.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The main administrator account cannot be disabled.",
        )
    user.is_active = False
    await _log_admin_action(db, current_user.user_id, "disable_user", "user", user.id, {"email": user.email})
    await db.commit()
    return {"user_id": user.id, "status": "disabled", "email": user.email}


@router.post("/users/{user_id}/role")
async def set_user_role(
    user_id: str,
    role_name: Literal["admin", "faculty"],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Modify a user's role — hardened.

    * ADMIN can no longer be granted here: admin promotion happens exclusively
      through the admin-access request approval workflow.
    * The protected Main Admin's roles can never be changed.
    * An admin can never alter its own administrative privileges.
    """
    from app.services.admin_access_service import ADMIN_ROLE, has_role

    actor = await _get_db_user(db, current_user.user_id)
    if actor is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acting admin no longer exists.")

    user = await _get_user_or_404(db, user_id)

    if user.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot modify your own roles through admin management.",
        )
    if user.is_primary_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The main administrator account cannot be modified.",
        )
    if role_name == ADMIN_ROLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Admin access can only be granted by approving an admin access "
                "request — direct promotion is not allowed."
            ),
        )

    # Remaining case: demote a secondary admin to faculty (preserve base role).
    if not await has_role(user, ADMIN_ROLE):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This user does not have admin access to remove.",
        )
    admin_role = next(role for role in user.roles if role.name == ADMIN_ROLE)
    user.roles.remove(admin_role)
    faculty_role = (await db.execute(select(Role).where(Role.name == "faculty"))).scalars().first()
    if faculty_role is not None and not await has_role(user, "faculty"):
        user.roles.append(faculty_role)

    await _log_admin_action(
        db,
        current_user.user_id,
        "set_user_role",
        "user",
        user.id,
        {"previous_role": ADMIN_ROLE, "resulting_roles": [r.name for r in user.roles]},
    )
    await db.commit()
    return _user_dict(user)


# ---------------------------------------------------------------------------
# Admin access requests (multi-admin onboarding)
# ---------------------------------------------------------------------------

@router.get("/admin-requests")
async def list_admin_requests(
    request_status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """List admin access requests (newest first). ADMIN-only."""
    from app.services.admin_access_service import list_requests

    rows = await list_requests(db, request_status)
    return {"requests": rows}


@router.post("/admin-requests/{request_id}/approve")
async def approve_admin_request(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Approve a PENDING admin access request (atomic; grants ADMIN)."""
    from app.services.admin_access_service import AdminRequestError, approve_request

    actor = await _get_db_user(db, current_user.user_id)
    if actor is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acting admin no longer exists.")
    try:
        result = await approve_request(db, request_id, actor)
    except AdminRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    return {"message": "Admin access approved.", **result}


@router.post("/admin-requests/{request_id}/reject")
async def reject_admin_request(
    request_id: str,
    body: RejectAdminRequestBody | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Reject a PENDING admin access request (never grants ADMIN)."""
    from app.services.admin_access_service import AdminRequestError, reject_request

    actor = await _get_db_user(db, current_user.user_id)
    if actor is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acting admin no longer exists.")
    try:
        result = await reject_request(db, request_id, actor, reason=body.reason if body else None)
    except AdminRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    return {"message": "Admin access rejected.", **result}


@router.post("/users/{user_id}/remove-admin")
async def remove_admin_access(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Remove a secondary admin's ADMIN role. Main Admin only."""
    from app.services.admin_access_service import AdminRequestError, remove_admin_role

    actor = await _get_db_user(db, current_user.user_id)
    if actor is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acting admin no longer exists.")
    try:
        result = await remove_admin_role(db, actor, user_id)
    except AdminRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    return {"message": "Admin access removed.", **result}


@router.get("/audit-logs")
async def list_audit_logs(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    limit = max(1, min(limit, 500))
    rows = (await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))).scalars().all()
    logs = [
        {
            "id": log.id,
            "actor_user_id": log.actor_user_id,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "payload": log.payload,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in rows
    ]
    return {"audit_logs": logs}