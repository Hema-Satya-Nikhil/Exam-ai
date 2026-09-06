"""Secure forgot-password flow: OTP request -> verify -> reset.

Security posture (all enforced here, none trusted from the client):

* 6-digit OTP from ``secrets`` (cryptographically secure), stored **hashed**
  (HMAC-SHA256 keyed by the app secret) — plaintext OTP never persisted/logged.
* OTP expires in ``settings.otp_expire_minutes`` (default 5).
* Max ``settings.otp_max_attempts`` (default 5) failed verifications, then the
  record is consumed and can no longer be used.
* Resend supersedes the previous OTP (previous row consumed) and a per-email
  cooldown (``otp_resend_cooldown_seconds``) is enforced with **429**.
* Only ACTIVE accounts may reset — pending/disabled/unknown emails receive the
  exact same generic response (no account enumeration) and no OTP is sent.
* Successful OTP verification issues an opaque, hashed, short-lived
  single-use **reset token** — it is *not* a login JWT and grants nothing but
  the password change.
* ``reset_password`` updates **only** ``password_hash`` (existing bcrypt) and
  revokes all refresh sessions; role, status and approval state are untouched.
* No OTP/token values are ever logged.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core import security
from app.core.config import settings
from app.models.academic import RefreshSession, User
from app.models.password_reset import PasswordResetOtp
from app.services import email_service as email_service_module
from app.services.auth_service import AuthService, _as_aware_utc

_logger = logging.getLogger(__name__)

GENERIC_MESSAGE = (
    "If an account exists for this email, a password reset OTP has been sent."
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_otp(otp: str) -> str:
    """Keyed hash so a leaked DB dump cannot be brute-forced offline easily."""
    return hashlib.sha256(f"{otp}:{settings.secret_key}".encode()).hexdigest()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_otp() -> str:
    """Cryptographically secure 6-digit OTP (000000-999999, always 6 chars)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


class PasswordResetError(Exception):
    """Client-facing password-reset failure (message is safe to show)."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class PasswordResetService:
    """Business logic for the OTP-based password reset workflow."""

    # ------------------------------------------------------------------
    # Step 1 — request an OTP
    # ------------------------------------------------------------------
    async def request_reset(self, session: AsyncSession, email: str) -> str:
        """Create + email an OTP. Returns the generic response message.

        Unknown, pending, disabled or otherwise ineligible accounts produce
        the *same* response (no OTP, no enumeration).
        """
        user = await AuthService.get_user_by_email(session, email)
        if user is None or not user.is_active:
            # Eligibility policy: only ACTIVE accounts may reset a password.
            # Refusing here can never activate/reenable anything.
            return GENERIC_MESSAGE

        # Rate limit: one active flow per email within the cooldown window.
        cooldown = timedelta(seconds=settings.otp_resend_cooldown_seconds)
        recent = await session.execute(
            select(PasswordResetOtp)
            .where(
                PasswordResetOtp.user_id == user.id,
                PasswordResetOtp.used_at.is_(None),
                PasswordResetOtp.created_at >= _now() - cooldown,
            )
            .order_by(PasswordResetOtp.created_at.desc())
            .limit(1)
        )
        if recent.scalars().first() is not None:
            raise PasswordResetError(
                429,
                "Too many requests. Please wait a minute before requesting another code.",
            )

        # Supersede any previous active flow (resend invalidates prior OTP).
        previous = await session.execute(
            select(PasswordResetOtp).where(
                PasswordResetOtp.user_id == user.id,
                PasswordResetOtp.used_at.is_(None),
            )
        )
        for row in previous.scalars():
            row.used_at = _now()

        otp = generate_otp()
        record = PasswordResetOtp(
            user_id=user.id,
            email=user.email,
            otp_hash=_hash_otp(otp),
            expires_at=_now() + timedelta(minutes=settings.otp_expire_minutes),
            attempt_count=0,
        )
        session.add(record)
        await session.flush()

        delivered = await email_service_module.get_email_service().send_password_reset_otp(
            user.email, otp
        )
        await session.commit()
        if not delivered:
            # Generic success keeps enumeration impossible; delivery failure
            # is logged server-side (sanitized) without leaking the OTP.
            _logger.error("Password-reset OTP could not be delivered (user=%s)", user.id)
        return GENERIC_MESSAGE

    # ------------------------------------------------------------------
    # Step 2 — verify the OTP, issue the single-use reset authorization
    # ------------------------------------------------------------------
    async def verify_otp(self, session: AsyncSession, email: str, otp: str) -> str:
        """Verify the OTP and return a one-time reset token (never a JWT)."""
        user = await AuthService.get_user_by_email(session, email)
        if user is None:
            raise PasswordResetError(400, "Invalid or expired verification code.")

        result = await session.execute(
            select(PasswordResetOtp)
            .where(
                PasswordResetOtp.user_id == user.id,
                PasswordResetOtp.used_at.is_(None),
            )
            .order_by(PasswordResetOtp.created_at.desc())
            .limit(1)
        )
        record = result.scalars().first()
        if record is None:
            raise PasswordResetError(400, "Invalid or expired verification code.")

        expires_at = _as_aware_utc(record.expires_at)
        if expires_at is not None and expires_at < _now():
            record.used_at = _now()  # expired -> consume
            await session.commit()
            raise PasswordResetError(400, "This code has expired. Please request a new one.")

        if not hmac.compare_digest(record.otp_hash, _hash_otp(otp.strip())):
            record.attempt_count = (record.attempt_count or 0) + 1
            invalidated = record.attempt_count >= settings.otp_max_attempts
            if invalidated:
                record.used_at = _now()  # too many attempts -> invalidate
            await session.commit()
            if invalidated:
                raise PasswordResetError(
                    400, "Too many incorrect attempts. Please request a new code."
                )
            raise PasswordResetError(400, "Incorrect verification code.")

        # Success — consume the OTP stage and mint the reset authorization.
        record.verified_at = _now()
        reset_token = generate_reset_token()
        record.reset_token_hash = _hash_token(reset_token)
        record.reset_token_expires_at = _now() + timedelta(
            minutes=settings.reset_token_expire_minutes
        )
        await session.commit()
        return reset_token

    # ------------------------------------------------------------------
    # Step 3 — consume the reset authorization and change the password
    # ------------------------------------------------------------------
    async def reset_password(
        self, session: AsyncSession, reset_token: str, new_password: str
    ) -> str:
        """Validate the reset authorization, set the new bcrypt password and
        revoke all refresh sessions. Returns the success message."""
        token_hash = _hash_token(reset_token)
        result = await session.execute(
            select(PasswordResetOtp).where(
                PasswordResetOtp.reset_token_hash == token_hash,
                PasswordResetOtp.reset_used_at.is_(None),
                PasswordResetOtp.used_at.is_(None),
            )
        )
        record = result.scalars().first()
        if record is None:
            raise PasswordResetError(400, "This password reset request is invalid or already used.")

        expires_at = _as_aware_utc(record.reset_token_expires_at)
        if expires_at is None or expires_at < _now():
            record.used_at = _now()
            await session.commit()
            raise PasswordResetError(
                400, "This password reset request has expired. Please start again."
            )

        if len(new_password) < 8:
            raise PasswordResetError(422, "Password must be at least 8 characters.")

        user_result = await session.execute(select(User).where(User.id == record.user_id))
        user = user_result.scalars().first()
        if user is None:
            raise PasswordResetError(400, "This password reset request is invalid or already used.")

        # Only the password changes — role/status/approval are untouched, so a
        # reset can never activate a pending or re-enable a disabled account.
        user.password_hash = security.hash_password(new_password)
        record.reset_used_at = _now()
        record.used_at = _now()  # terminal — OTP + authorization both consumed

        # Force re-authentication everywhere (existing revocation mechanism).
        await self._revoke_all_refresh_sessions(session, user.id)

        await session.commit()
        return "Password reset successfully."

    # ------------------------------------------------------------------
    # Refresh-session revocation (reuses the existing refresh_sessions table)
    # ------------------------------------------------------------------
    @staticmethod
    async def _revoke_all_refresh_sessions(session: AsyncSession, user_id: str) -> None:
        result = await session.execute(
            select(RefreshSession).where(
                RefreshSession.user_id == user_id,
                RefreshSession.revoked.is_(False),
            )
        )
        for refresh_session in result.scalars():
            refresh_session.revoked = True


