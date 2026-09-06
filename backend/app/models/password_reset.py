from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PasswordResetOtp(Base):
    """Persistent password-reset OTP + single-use reset authorization.

    One row represents one password-reset flow for a user. The 6-digit OTP is
    stored **hashed** (never plaintext) and so is the derived short-lived
    reset token. Lifecycle:

        request  -> row created (otp_hash, expires_at, attempt_count=0)
        resend   -> previous active row is consumed (used_at set), new row
        verify   -> verified_at set; a hashed single-use reset token is stored
        reset    -> password changed; reset_used_at + used_at set (terminal)
        too many failed OTP attempts -> row consumed (invalidated)

    Only the password may be changed through this flow — role, status and
    admin-approval state are never touched here.
    """

    __tablename__ = "password_reset_otps"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # --- OTP stage -------------------------------------------------------
    otp_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # --- Reset-authorization stage (issued only after OTP verification) ---
    reset_token_hash: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    reset_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reset_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Terminal marker — set when the row is consumed/invalidated for any reason
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
