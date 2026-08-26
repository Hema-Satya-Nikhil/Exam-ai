from __future__ import annotations

from collections.abc import Callable

from fastapi import HTTPException, status

from app.schemas.auth import RoleName, UserContext


def require_roles(*allowed_roles: RoleName) -> Callable[[UserContext], UserContext]:
    def dependency(user: UserContext) -> UserContext:
        if not set(user.roles).intersection(allowed_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return dependency
