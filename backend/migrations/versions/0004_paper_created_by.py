"""add created_by to generated_papers

Revision ID: 0004_paper_created_by
Revises: 0003_composite_exam
Create Date: 2026-08-29

Ownership column used by the dashboard "Recent Papers" list and legacy
paper creation; some live environments predate it.
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_paper_created_by"
down_revision = "0003_composite_exam"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generated_papers",
        sa.Column("created_by", sa.UUID(), nullable=True),
    )
    op.create_index(
        "ix_generated_papers_created_by", "generated_papers", ["created_by"]
    )


def downgrade() -> None:
    op.drop_index("ix_generated_papers_created_by", table_name="generated_papers")
    op.drop_column("generated_papers", "created_by")
