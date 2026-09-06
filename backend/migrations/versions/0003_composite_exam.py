"""exam structure: exam_generation_jobs + composite metadata on generated_questions

Revision ID: 0003_composite_exam
Revises: 0002_add_missing_tables
Create Date: 2026-08-26 00:00:00.000000

Adds the parent ``exam_generation_jobs`` table for the two-part institutional
examination (Part A short-answer + Part B main paper) and six nullable
composite-metadata columns on ``generated_questions`` so every generated
question can carry its exam part / group / part-label / choice membership.
All new ``generated_questions`` columns are optional so existing flat-paper
rows are unaffected.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0003_composite_exam"
down_revision = "0002_add_missing_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exam_generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("exam_config_json", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False,
                  server_default=sa.text("'queued'")),
        sa.Column("current_step", sa.String(length=160), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("total_questions", sa.Integer(), nullable=True),
        sa.Column("completed_questions", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("short_answer_job_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("main_paper_job_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("paper_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["short_answer_job_id"], ["generation_jobs.id"],
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["main_paper_job_id"], ["generation_jobs.id"],
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["paper_id"], ["generated_papers.id"],
                                ondelete="SET NULL"),
    )
    op.create_index("ix_exam_generation_jobs_created_by",
                    "exam_generation_jobs", ["created_by"])

    # Composite metadata on generated_questions (all nullable -> flat rows NULL).
    op.add_column(
        "generated_questions",
        sa.Column("exam_generation_job_id", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.create_foreign_key(
        "fk_gq_exam_generation_job_id",
        "generated_questions", "exam_generation_jobs",
        ["exam_generation_job_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_generated_questions_exam_generation_job_id",
                    "generated_questions", ["exam_generation_job_id"])
    op.add_column("generated_questions",
                  sa.Column("exam_part", sa.String(length=30), nullable=True))
    op.add_column("generated_questions",
                  sa.Column("group_number", sa.Integer(), nullable=True))
    op.add_column("generated_questions",
                  sa.Column("part_label", sa.String(length=10), nullable=True))
    op.add_column("generated_questions",
                  sa.Column("choice_group_id", sa.String(length=80), nullable=True))
    op.add_column("generated_questions",
                  sa.Column("choice_member_id", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("generated_questions", "choice_member_id")
    op.drop_column("generated_questions", "choice_group_id")
    op.drop_column("generated_questions", "part_label")
    op.drop_column("generated_questions", "group_number")
    op.drop_column("generated_questions", "exam_part")
    op.drop_index("ix_generated_questions_exam_generation_job_id",
                  table_name="generated_questions")
    op.drop_constraint("fk_gq_exam_generation_job_id", "generated_questions",
                       type_="foreignkey")
    op.drop_column("generated_questions", "exam_generation_job_id")
    op.drop_index("ix_exam_generation_jobs_created_by", table_name="exam_generation_jobs")
    op.drop_table("exam_generation_jobs")