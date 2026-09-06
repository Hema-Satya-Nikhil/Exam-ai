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
    # When true, the new account ALSO gets a PENDING admin-access request.
    # This never grants the ADMIN role directly and never sets the protected
    # primary-admin flag — an existing administrator must approve the request.
    request_admin: bool = False


class RegisterResponse(BaseModel):
    user_id: str
    email: EmailStr
    status: str = "pending"
    # Present only when the registration included an admin-access request.
    admin_request_status: str | None = None


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


# ---------------------------------------------------------------------------
# Password reset (forgot-password OTP flow)
# ---------------------------------------------------------------------------

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    """Deliberately generic — never reveals whether the account exists."""

    message: str = (
        "If an account exists for this email, a password reset OTP has been sent."
    )


class VerifyResetOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class VerifyResetOtpResponse(BaseModel):
    """Short-lived, single-use password-reset authorization (NOT a login JWT)."""

    reset_token: str


class ResetPasswordRequest(BaseModel):
    reset_token: str = Field(..., min_length=16, max_length=256)
    new_password: str = Field(..., min_length=8)


class ResetPasswordResponse(BaseModel):
    message: str = "Password reset successfully."

