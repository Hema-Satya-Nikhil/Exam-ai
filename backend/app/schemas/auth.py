from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field

# Role names are case-sensitive and must match what is stored in the DB.
RoleName = Literal["admin", "faculty"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# Keep TokenResponse as alias so existing code that imports it still works.
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserContext(BaseModel):
    """Lightweight user representation attached to every authenticated request."""

    user_id: str
    email: EmailStr
    full_name: str
    roles: list[RoleName]
    is_active: bool = True

    def has_role(self, *names: str) -> bool:
        return bool(set(self.roles) & set(names))
