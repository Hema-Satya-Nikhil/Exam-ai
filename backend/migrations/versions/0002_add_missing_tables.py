"""add missing tables: user_roles, refresh_sessions, export_audits

Revision ID: 0002_add_missing_tables
Revises: 0001_initial_schema
Create Date: 2026-08-16 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0002_add_missing_tables"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # user_roles - many-to-many association between users and roles
    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
    )

    # refresh_sessions - JWT refresh token session persistence
    op.create_table(
        "refresh_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("jti", sa.String(length=36), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti", name="uq_refresh_sessions_jti"),
    )
    op.create_index(op.f("ix_refresh_sessions_jti"), "refresh_sessions", ["jti"], unique=True)

    # export_audits - audit trail for PDF/DOCX exports
    op.create_table(
        "export_audits",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("paper_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("approved_version", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("exported_by", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("format", sa.Enum("pdf", "docx", name="exportformat"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["paper_id"], ["generated_papers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approved_version"], ["paper_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exported_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("export_audits")
    op.drop_index(op.f("ix_refresh_sessions_jti"), table_name="refresh_sessions")
    op.drop_table("refresh_sessions")
    op.drop_table("user_roles")
    op.execute("DROP TYPE IF EXISTS exportformat")