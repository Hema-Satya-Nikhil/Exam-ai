"""Email delivery abstraction for the password-reset OTP flow.

The default provider is **Resend** (HTTP API via ``httpx`` — no new heavy
dependency). Credentials come exclusively from environment variables:

    RESEND_API_KEY      — API key (never logged, never committed)
    RESEND_FROM_EMAIL   — verified sender address
    RESEND_FROM_NAME    — display name (default: ExamCraft AI)
    EMAIL_PROVIDER      — ``resend`` (default) or ``brevo``
    BREVO_API_KEY       — backend-only Brevo API key
    BREVO_FROM_EMAIL    — sender permitted by Brevo
    BREVO_FROM_NAME     — display name (default: ExamCraft AI)

Tests never send real email: ``get_email_service()`` returns a
:class:`NoopEmailService` when ``APP_ENV=TEST`` (the test ``conftest`` sets
this), and tests may additionally inject a recorder via ``set_email_service``.
Nothing here ever logs the OTP or any credential.
"""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from app.core.config import settings

_logger = logging.getLogger(__name__)

OTP_SUBJECT = "ExamCraft AI - Password Reset OTP"


def _otp_body(otp: str, expire_minutes: int) -> str:
    """Plain-text email body. Contains only the OTP + guidance (no tokens)."""
    return (
        "Hello,\n\n"
        "We received a request to reset your ExamCraft AI password.\n\n"
        f"Your one-time verification code is: {otp}\n\n"
        f"This code expires in {expire_minutes} minutes and can be used only once.\n\n"
        "If you did not request a password reset, you can safely ignore this "
        "email — your password will not change.\n\n"
        "— ExamCraft AI"
    )


class EmailService(Protocol):
    """Minimal email contract — single purpose, no secrets in logs."""

    async def send_password_reset_otp(self, email: str, otp: str) -> bool:
        """Deliver the OTP email. Returns True when delivery was accepted."""
        ...  # pragma: no cover


class ResendEmailService:
    """Resend (https://resend.com) delivery over its plain HTTP API."""

    def __init__(self, api_key: str | None = None, from_email: str | None = None,
                 from_name: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else settings.resend_api_key
        self._from_email = from_email if from_email is not None else settings.resend_from_email
        self._from_name = from_name if from_name is not None else settings.resend_from_name
        _logger.info(
            "Resend provider selected (sender=%s, environment=%s)",
            self._from_email or "<unset>",
            settings.app_env,
        )

    async def send_password_reset_otp(self, email: str, otp: str) -> bool:
        if not self._api_key or not self._from_email:
            # Provider not configured — report failure without logging secrets.
            _logger.error("Password-reset email skipped: email provider is not configured")
            return False
        payload = {
            "from": f"{self._from_name} <{self._from_email}>",
            "to": [email],
            "subject": OTP_SUBJECT,
            "text": _otp_body(otp, settings.otp_expire_minutes),
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.resend.com/emails",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                )
            if resp.status_code in (200, 201):
                _logger.info("Resend provider accepted password-reset email (status=%s)", resp.status_code)
                return True
            provider_message = ""
            try:
                body = resp.json()
                provider_message = str(body.get("message") or body.get("error") or "")[:160]
            except ValueError:
                provider_message = ""
            _logger.error(
                "Password-reset email delivery failed: provider status %s%s",
                resp.status_code,
                f" ({provider_message})" if provider_message else "",
            )
            return False
        except httpx.HTTPError:
            # Sanitized: no URL query, no key, no body dumped.
            _logger.exception("Password-reset email delivery failed (network error)")
            return False


class BrevoEmailService:
    """Brevo transactional delivery over its plain HTTP API."""

    def __init__(self, api_key: str | None = None, from_email: str | None = None,
                 from_name: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else settings.brevo_api_key
        self._from_email = from_email if from_email is not None else settings.brevo_from_email
        self._from_name = from_name if from_name is not None else settings.brevo_from_name
        _logger.info(
            "Brevo provider selected (sender=%s, environment=%s)",
            self._from_email or "<unset>",
            settings.app_env,
        )

    async def send_password_reset_otp(self, email: str, otp: str) -> bool:
        if not self._api_key or not self._from_email:
            _logger.error("Password-reset email skipped: Brevo provider is not configured")
            return False
        payload = {
            "sender": {"name": self._from_name, "email": self._from_email},
            "to": [{"email": email}],
            "subject": OTP_SUBJECT,
            "textContent": _otp_body(otp, settings.otp_expire_minutes),
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.brevo.com/v3/smtp/email",
                    json=payload,
                    headers={
                        "api-key": self._api_key,
                        "accept": "application/json",
                        "content-type": "application/json",
                    },
                )
            if resp.status_code in (200, 201, 202):
                _logger.info("Brevo provider accepted password-reset email (status=%s)", resp.status_code)
                return True
            provider_message = ""
            try:
                body = resp.json()
                provider_message = str(body.get("message") or body.get("code") or "")[:160]
            except ValueError:
                provider_message = ""
            _logger.error(
                "Brevo password-reset delivery failed: provider status %s%s",
                resp.status_code,
                f" ({provider_message})" if provider_message else "",
            )
            return False
        except httpx.HTTPError:
            _logger.exception("Brevo password-reset delivery failed (network error)")
            return False


class NoopEmailService:
    """Test/no-op adapter — never sends anything, never persists the OTP."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send_password_reset_otp(self, email: str, otp: str) -> bool:
        self.sent.append((email, otp))
        return True

    def latest_otp(self, email: str) -> str | None:
        """Most recent OTP recorded for ``email`` (TEST outbox support)."""
        target = email.strip().lower()
        for sent_email, otp in reversed(self.sent):
            if sent_email.lower() == target:
                return otp
        return None

    def clear(self) -> None:
        """Deterministic test setup: drop previously recorded messages."""
        self.sent.clear()


_email_service: EmailService | None = None


def get_email_service() -> EmailService:
    global _email_service
    if _email_service is None:
        # Automated test environments must never perform real deliveries.
        if settings.app_env.upper() == "TEST":
            _email_service = NoopEmailService()
        elif settings.email_provider.strip().lower() == "brevo":
            _email_service = BrevoEmailService()
        else:
            _email_service = ResendEmailService()
    return _email_service


def set_email_service(service: EmailService | None) -> None:
    """Injection point for tests / alternative providers (None = reset)."""
    global _email_service
    _email_service = service
