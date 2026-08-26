from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field

# Role names are case-sensitive and must match what is stored in the DB.
RoleName = Literal["admin", "faculty"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Self-registration request for a new FACULTY member.

    ``role`` is accepted only to keep the client payload self-describing; the
    server ignores any value other than ``faculty`` so end users can never
    self-promote to ``admin`` (admin accounts are bootstrapped exclusively via
    ``seed_admin``).
    """

    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8)
    role: RoleName = "faculty"


class RegisterResponse(BaseModel):
    user_id: str
    email: EmailStr
    status: str = "pending"


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
