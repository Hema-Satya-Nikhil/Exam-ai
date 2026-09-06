"""Admin access request workflow (multi-admin onboarding).

An admin access request is a *workflow state*, never a role: a PENDING request
grants nothing. Only an approved request — actioned by an authorized admin —
results in the ADMIN role being granted. Exactly one protected Main Admin
(``users.is_primary_admin``) exists in the database and can never be created
through this workflow.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AdminAccessRequest(Base):
    """A user's request for ADMIN access.

    Lifecycle: PENDING → APPROVED | REJECTED | CANCELLED. At most ONE PENDING
    request per user (partial unique index ``uq_admin_requests_one_pending``).
    """

    __tablename__ = "admin_access_requests"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    requested_role: Mapped[str] = mapped_column(String(30), nullable=False, default="admin")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    review_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        foreign_keys=[user_id], lazy="selectin"
    )
    reviewer: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        foreign_keys=[reviewed_by], lazy="selectin"
    )

    __table_args__ = (
        Index("ix_admin_requests_user_id", "user_id"),
        Index("ix_admin_requests_status", "status"),
        Index("ix_admin_requests_requested_at", "requested_at"),
        # Database-enforced: at most one PENDING request per user.
        Index(
            "uq_admin_requests_one_pending",
            "user_id",
            unique=True,
            sqlite_where=text("status = 'pending'"),
            postgresql_where=text("status = 'pending'"),
        ),
    )
