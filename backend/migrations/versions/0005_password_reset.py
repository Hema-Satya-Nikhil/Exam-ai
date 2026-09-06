"""password reset OTPs

Revision ID: 0005_password_reset
Revises: 0004_paper_created_by
Create Date: 2026-09-04

Single table powering the secure forgot-password flow: hashed 6-digit OTP
(plaintext never persisted), attempt counter, expiry, and a hashed short-lived
single-use reset authorization issued only after successful OTP verification.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_password_reset"
down_revision = "0004_paper_created_by"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_otps",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("otp_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reset_token_hash", sa.String(length=128), nullable=True),
        sa.Column("reset_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reset_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_password_reset_otps_user_id", "password_reset_otps", ["user_id"])
    op.create_index("ix_password_reset_otps_email", "password_reset_otps", ["email"])
    op.create_index(
        "ix_password_reset_otps_reset_token_hash", "password_reset_otps", ["reset_token_hash"]
    )


def downgrade() -> None:
    op.drop_index("ix_password_reset_otps_reset_token_hash", table_name="password_reset_otps")
    op.drop_index("ix_password_reset_otps_email", table_name="password_reset_otps")
    op.drop_index("ix_password_reset_otps_user_id", table_name="password_reset_otps")
    op.drop_table("password_reset_otps")
