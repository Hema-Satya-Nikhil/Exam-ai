"""Apply the persistent-GenerationJob columns to the existing PostgreSQL schema.

The project provisions its schema manually (no Alembic versions directory), so
this script follows that convention. It is IDEMPOTENT — safe to re-run:

    python scripts/apply_generation_job_columns.py

Adds to ``generation_jobs``:
    created_by       UUID NULL      -> users.id (faculty ownership)
    created_at       timestamptz DEFAULT now()
    updated_at       timestamptz DEFAULT now()
    total_questions  INTEGER NULL
    paper_id         UUID NULL      -> generated_papers.id
    idempotency_key  VARCHAR(64) NULL + index (duplicate-job prevention)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db.session import engine  # noqa: E402

STATEMENTS = [
    "ALTER TABLE generation_jobs ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id) ON DELETE SET NULL",
    "ALTER TABLE generation_jobs ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
    "ALTER TABLE generation_jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()",
    "ALTER TABLE generation_jobs ADD COLUMN IF NOT EXISTS total_questions INTEGER",
    "ALTER TABLE generation_jobs ADD COLUMN IF NOT EXISTS paper_id UUID REFERENCES generated_papers(id) ON DELETE SET NULL",
    "ALTER TABLE generation_jobs ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(64)",
    "CREATE INDEX IF NOT EXISTS ix_generation_jobs_idempotency_key ON generation_jobs (idempotency_key)",
]


async def main() -> None:
    async with engine.begin() as conn:
        for statement in STATEMENTS:
            await conn.execute(text(statement))
            print("OK :", statement[:72])
        columns = (
            await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'generation_jobs' ORDER BY ordinal_position"
                )
            )
        ).scalars().all()
        print("\ncurrent generation_jobs columns:")
        for name in columns:
            print("  -", name)


if __name__ == "__main__":
    asyncio.run(main())
