from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user, get_db
from app.models.academic import User
from app.models.audit import AuditLog
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenPair,
    UserContext,
    VerifyResetOtpRequest,
    VerifyResetOtpResponse,
)
from app.services.auth_service import AuthService
from app.services.password_reset_service import PasswordResetError, PasswordResetService

router = APIRouter()
auth_service = AuthService()
password_reset_service = PasswordResetService()


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Login — issue access + refresh token pair",
)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    """Authenticate with email / password.

    Returns:
    - ``access_token`` — short-lived (15 min), use as ``Authorization: Bearer``
    - ``refresh_token`` — long-lived, use *only* with ``POST /api/auth/refresh``
    """
    user, reason = await auth_service.authenticate_user_with_reason(db, request.email, request.password)
    if user is None:
        if reason == "pending_approval":
            # The credentials are valid; the account simply is not activated yet.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is awaiting administrator approval.",
            )
        if reason in ("account_rejected", "account_disabled"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been deactivated. Please contact an administrator.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await auth_service.issue_token_pair(db, user)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Faculty self-registration (pending admin approval)",
)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """Register a new faculty account.

    The account is created **inactive** (`is_active=False`) and must be
    approved by an administrator before the user can sign in. Registration
    is intentionally restricted to the `faculty` role — administrators are
    bootstrapped only via `seed_admin`, so self-promotion is impossible.
    """
    existing = await auth_service.get_user_by_email(db, request.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    user = await auth_service.register_faculty(
        db,
        request.email,
        request.full_name,
        request.password,
        role=request.role,
        request_admin=request.request_admin,
    )

    # Audit the admin-access request (actor = the requesting user). Never logs
    # passwords or any secret. Part of the SAME transaction as registration.
    admin_request_status: str | None = None
    if request.request_admin:
        db.add(
            AuditLog(
                actor_user_id=user.id,
                action="ADMIN_ACCESS_REQUESTED",
                entity_type="user",
                entity_id=user.id,
                payload={"email": user.email, "requested_role": "admin"},
            )
        )
        admin_request_status = "pending"

    await db.commit()
    return RegisterResponse(
        user_id=user.id, email=user.email, admin_request_status=admin_request_status
    )


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Rotate refresh token and issue new access token",
)
async def refresh(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenPair:
    """Exchange a valid refresh token for a new token pair.

    The old refresh token is revoked (token rotation).
    Raises 401 if the refresh token is expired, revoked, or invalid.
    """
    token_pair = await auth_service.refresh_tokens(db, request.refresh_token)
    if token_pair is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid, expired, or has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_pair


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout — revoke the current refresh session",
)
async def logout(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke the refresh session.

    The associated access token will naturally expire (15 min).  Clients
    should discard both tokens immediately on logout.
    """
    await auth_service.revoke_refresh_token(db, request.refresh_token)
    # Always return 204 — don't leak whether the token was valid


@router.get(
    "/me",
    response_model=UserContext,
    summary="Return the currently authenticated user",
)
async def me(
    current_user: User = Depends(get_current_user),
) -> UserContext:
    return UserContext(
        user_id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        roles=[role.name.lower() for role in current_user.roles],
        is_active=current_user.is_active,
    )


# ---------------------------------------------------------------------------
# Password reset (forgot-password OTP flow) — public, unauthenticated
# ---------------------------------------------------------------------------

@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Request a password-reset OTP",
)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ForgotPasswordResponse:
    """Email a one-time 6-digit code to the registered address.

    The response is intentionally identical whether or not the account
    exists, is pending approval, or is disabled — account existence is never
    revealed. Rate-limited per email via a resend cooldown (429).
    """
    try:
        message = await password_reset_service.request_reset(db, request.email)
    except PasswordResetError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    return ForgotPasswordResponse(message=message)


@router.post(
    "/verify-reset-otp",
    response_model=VerifyResetOtpResponse,
    summary="Verify the password-reset OTP",
)
async def verify_reset_otp(
    request: VerifyResetOtpRequest,
    db: AsyncSession = Depends(get_db),
) -> VerifyResetOtpResponse:
    """Validate the OTP and return a short-lived, single-use reset token.

    This token authorizes **only** the password change — it is not a login
    token and grants no other access. Failed attempts are limited; exceeding
    the limit invalidates the OTP.
    """
    try:
        reset_token = await password_reset_service.verify_otp(db, request.email, request.otp)
    except PasswordResetError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    return VerifyResetOtpResponse(reset_token=reset_token)


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    summary="Complete the password reset",
)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ResetPasswordResponse:
    """Set a new password using a valid single-use reset token.

    Only ``password_hash`` changes (bcrypt via the existing hashing service);
    role, account status and admin-approval state are untouched, and all
    existing refresh sessions are revoked.
    """
    try:
        message = await password_reset_service.reset_password(
            db, request.reset_token, request.new_password
        )
    except PasswordResetError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    return ResetPasswordResponse(message=message)
