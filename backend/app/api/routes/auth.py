from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user, get_db
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair, UserContext
from app.services.auth_service import AuthService

router = APIRouter()
auth_service = AuthService()


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
    user = await auth_service.authenticate_user(db, request.email, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await auth_service.issue_token_pair(db, user)


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
    current_user: UserContext = Depends(get_current_user),
) -> UserContext:
    return current_user
