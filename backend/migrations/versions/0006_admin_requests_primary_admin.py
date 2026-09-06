"""admin access requests + protected Main Admin

Revision ID: 0006_admin_requests
Revises: 0005_password_reset
Create Date: 2026-09-05

* ``users.is_primary_admin`` — the protected Main Admin flag. Exactly one user
  may hold it (partial unique index). Backfilled from the configured
  ``ADMIN_EMAIL`` bootstrap account; runtime authorization reads this column,
  never the email.
* ``admin_access_requests`` — the admin-access request workflow (a workflow
  state, never a role). At most one PENDING request per user (partial unique
  index).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.core.config import settings

revision = "0006_admin_requests"
down_revision = "0005_password_reset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. Protected Main Admin flag --------------------------------------
    op.add_column(
        "users",
        sa.Column(
            "is_primary_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index(
        "uq_users_one_primary_admin",
        "users",
        ["is_primary_admin"],
        unique=True,
        postgresql_where=sa.text("is_primary_admin"),
        sqlite_where=sa.text("is_primary_admin"),
    )
    # Backfill the configured bootstrap admin (if the account exists — it may
    # be created later by seed_admin, which also sets the flag).
    op.execute(
        sa.text(
            "UPDATE users SET is_primary_admin = TRUE "
            "WHERE lower(email) = lower(:admin_email)"
        ).bindparams(admin_email=settings.admin_email or "")
    )

    # --- 2. Admin access request workflow ----------------------------------
    op.create_table(
        "admin_access_requests",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requested_role", sa.String(length=30), nullable=False, server_default="admin"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_admin_requests_user_id", "admin_access_requests", ["user_id"])
    op.create_index("ix_admin_requests_status", "admin_access_requests", ["status"])
    op.create_index("ix_admin_requests_requested_at", "admin_access_requests", ["requested_at"])
    op.create_index(
        "uq_admin_requests_one_pending",
        "admin_access_requests",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_admin_requests_one_pending", table_name="admin_access_requests")
    op.drop_index("ix_admin_requests_requested_at", table_name="admin_access_requests")
    op.drop_index("ix_admin_requests_status", table_name="admin_access_requests")
    op.drop_index("ix_admin_requests_user_id", table_name="admin_access_requests")
    op.drop_table("admin_access_requests")
    op.drop_index("uq_users_one_primary_admin", table_name="users")
    op.drop_column("users", "is_primary_admin")
