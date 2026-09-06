"""Initial administrator bootstrap + account-management helpers.

This service is the single source of truth for creating / reconciling the
initial ADMIN account. It is idempotent and environment-driven:

* It creates the ADMIN (and FACULTY) role only when missing (never duplicates).
* It creates the admin user only when the configured email does not already
  exist, hashing the password with the existing app hashing service
  (``app.core.security.hash_password``) — plaintext is never persisted.
* On a re-run (user already exists) it NEVER overwrites the existing password;
  it instead ensures the ADMIN role is present and the account is active, and
  reports that the admin already exists.
* No secret value ever appears in the returned :class:`SeedResult`.

It also exposes admin-only account moderation: approving / rejecting pending
(inactive) faculty accounts by toggling ``User.is_active``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.models.academic import Role, User

ADMIN_ROLE = "admin"
FACULTY_ROLE = "faculty"


@dataclass
class SeedResult:
    """Non-sensitive outcome of an admin bootstrap run.

    ``action`` is ``created`` (a new admin was created) or ``exists`` (the
    configured admin email already existed and was reconciled). It never
    contains the password or its hash.
    """

    action: Literal["created", "exists"]
    email: str
    role_assigned: bool
    active: bool


async def get_or_create_role(session: AsyncSession, name: str, description: str) -> Role:
    """Fetch a role by name, creating it once if absent (avoids duplicates)."""
    stmt = select(Role).where(Role.name == name)
    role = (await session.execute(stmt)).scalars().first()
    if role is None:
        role = Role(name=name, description=description)
        session.add(role)
        await session.flush()
    return role


async def ensure_roles(session: AsyncSession) -> dict[str, Role]:
    """Create the standard roles used by the app if they do not exist yet."""
    return {
        ADMIN_ROLE: await get_or_create_role(session, ADMIN_ROLE, "Administrator"),
        FACULTY_ROLE: await get_or_create_role(session, FACULTY_ROLE, "Faculty member"),
    }


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    # Case-insensitive so a re-seed/lookup never misses the admin on casing.
    stmt = select(User).where(func.lower(User.email) == email.strip().lower())
    return (await session.execute(stmt)).scalars().first()


async def seed_admin(
    session: AsyncSession,
    email: str,
    password: str,
    full_name: str = "Initial Administrator",
) -> SeedResult:
    """Idempotently create or reconcile the initial administrator account.

    * Hashing: the raw ``password`` is bcrypt-hashed via
      ``security.hash_password`` before it is persisted — plaintext is never
      stored and the hash is never printed.
    * Existng admin: the existing password is left untouched; the ADMIN role
      and ``is_active`` are reconciled; ``SeedResult(action="exists")``.
    * No admin role exists: it is created once.
    """
    admin_role = await get_or_create_role(session, ADMIN_ROLE, "Administrator")
    existing = await get_user_by_email(session, email)

    if existing is not None:
        if ADMIN_ROLE not in {role.name for role in existing.roles}:
            existing.roles.append(admin_role)
        existing.is_active = True
        # The configured bootstrap account is THE protected Main Admin. The
        # partial unique index guarantees no second primary admin can exist.
        existing.is_primary_admin = True
        await session.commit()
        return SeedResult(
            action="exists",
            email=existing.email,
            role_assigned=ADMIN_ROLE in {role.name for role in existing.roles},
            active=existing.is_active,
        )

    admin = User(
        email=email,
        full_name=full_name,
        password_hash=security.hash_password(password),
        is_active=True,
        is_primary_admin=True,  # bootstrap account = the protected Main Admin
        roles=[admin_role],
    )
    session.add(admin)
    await session.commit()
    return SeedResult(
        action="created",
        email=admin.email,
        role_assigned=ADMIN_ROLE in {role.name for role in admin.roles},
        active=admin.is_active,
    )


async def approve_faculty(session: AsyncSession, user_id: str) -> bool:
    """Admin-only: activate a pending (inactive) faculty account."""
    user = (await session.execute(select(User).where(User.id == user_id))).scalars().first()
    if user is None:
        return False
    user.is_active = True
    await session.commit()
    return True


async def reject_faculty(session: AsyncSession, user_id: str) -> bool:
    """Admin-only: deactivate / reject a faculty account."""
    user = (await session.execute(select(User).where(User.id == user_id))).scalars().first()
    if user is None:
        return False
    user.is_active = False
    await session.commit()
    return True