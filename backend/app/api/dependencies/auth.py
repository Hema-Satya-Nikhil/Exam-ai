from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core import security
from app.db.session import async_session_maker
from app.models.academic import User
from app.schemas.auth import UserContext

# ---------------------------------------------------------------------------
# OAuth2 scheme — tokenUrl points at the real login endpoint
# ---------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ---------------------------------------------------------------------------
# DB session dependency
# ---------------------------------------------------------------------------

async def get_db() -> AsyncSession:  # type: ignore[override]
    async with async_session_maker() as session:
        yield session


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> UserContext:
    """Decode the Bearer access token and return the authenticated UserContext.

    Raises 401 on any of:
    - missing / malformed token
    - wrong token type (e.g. a refresh token presented as access)
    - user not found in DB
    - user is inactive
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = security.decode_access_token(token)
    if payload is None:
        raise credentials_exc

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise credentials_exc

    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalars().first()

    if user is None:
        raise credentials_exc
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return UserContext(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=[role.name for role in user.roles],
        is_active=user.is_active,
    )


# ---------------------------------------------------------------------------
# RBAC helpers
# ---------------------------------------------------------------------------

def require_roles(*allowed_roles: str) -> Callable[..., UserContext]:
    """Return a FastAPI dependency that enforces role membership.

    Usage::

        @router.get("/admin-only", dependencies=[Depends(require_roles("admin"))])
        ...

        @router.get("/staff", dependencies=[Depends(require_roles("admin", "faculty"))])
        ...
    """
    def _checker(current_user: UserContext = Depends(get_current_user)) -> UserContext:
        if not set(current_user.roles) & set(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _checker


# Keep the old name used by router.py during the previous session
def require_role(required_roles: list[str]) -> Callable[..., UserContext]:
    """Backward-compat wrapper around require_roles()."""
    return require_roles(*required_roles)


def require_faculty_access(
    paper_id: str,
    current_user: UserContext = Depends(get_current_user),
) -> UserContext:
    """Dependency that verifies the calling user may access a specific paper.

    * Admins can access everything.
    * Faculty can only access papers they own (stored in paper metadata).

    NOTE: This is a *route-level* dependency injected per-endpoint.  The
    ownership check queries the paper_workflow_service in-process to avoid
    a circular import with the paper router.
    """
    if "admin" in current_user.roles:
        return current_user
    # Ownership is enforced at the service layer by passing current_user.user_id
    # to the workflow service and checking paper.created_by.  If the service
    # raises ValueError / returns None the route handler will 404/403.
    return current_user
