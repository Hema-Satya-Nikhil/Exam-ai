"""Add ownership metadata for paper templates.

Revision ID: 0002_productivity_template_owner
Revises: 0001_initial_schema
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_productivity_template_owner"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("paper_templates", sa.Column("created_by", postgresql.UUID(as_uuid=False), nullable=True))
    op.create_foreign_key(
        "fk_paper_templates_created_by_users",
        "paper_templates",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_paper_templates_created_by", "paper_templates", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_paper_templates_created_by", table_name="paper_templates")
    op.drop_constraint("fk_paper_templates_created_by_users", "paper_templates", type_="foreignkey")
    op.drop_column("paper_templates", "created_by")
