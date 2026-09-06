"""TEST-ONLY support endpoints (OTP outbox for browser E2E).

This router is mounted by ``app.api.router`` **only** when
``settings.app_env`` is ``TEST`` (case-insensitive) and additionally
fail-closes inside every handler: if the environment is anything other than
TEST — development, staging, production, or ambiguous — the endpoints respond
404 and never touch the outbox. No production configuration can reach them.

The outbox exposes exactly two fields per recorded message:

    {"email": "...", "otp": "..."}

It never returns passwords, password hashes, reset tokens, JWTs, refresh
tokens, or any secret. It is a test concern only — the production frontend
has no knowledge of it and the normal API client never calls it.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.config import settings
from app.services.email_service import NoopEmailService, get_email_service

router = APIRouter()


def test_outbox_enabled() -> bool:
    """Fail-closed gating: only the exact TEST environment qualifies."""
    return settings.app_env.upper() == "TEST"


class OutboxMessage(BaseModel):
    email: str
    otp: str


class OutboxResponse(BaseModel):
    messages: list[OutboxMessage]


@router.get(
    "/outbox",
    response_model=OutboxResponse,
    summary="[TEST ONLY] Retrieve OTPs recorded by the test email adapter",
    include_in_schema=test_outbox_enabled(),
)
async def get_test_outbox(
    email: str | None = Query(default=None, description="Filter by recipient email"),
) -> OutboxResponse:
    if not test_outbox_enabled():
        # Fail closed — the route must be unreachable outside APP_ENV=TEST.
        raise HTTPException(status_code=404, detail="Not found")

    service = get_email_service()
    if not isinstance(service, NoopEmailService):
        # Ambiguous configuration (e.g. TEST env but a real mail adapter was
        # injected): expose nothing rather than risk leaking real deliveries.
        raise HTTPException(status_code=404, detail="Not found")

    messages = [
        OutboxMessage(email=sent_email, otp=otp)
        for sent_email, otp in reversed(service.sent)
        if email is None or sent_email.lower() == email.strip().lower()
    ]
    return OutboxResponse(messages=messages[:10])
