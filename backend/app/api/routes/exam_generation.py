"""Composite examination generation routes (Phase 2).

Additive API for the two-part institutional examination:
    POST   /api/exam-generation/jobs            create + enqueue
    GET    /api/exam-generation/jobs/{id}       status / progress
    POST   /api/exam-generation/jobs/{id}/resume
    POST   /api/exam-generation/jobs/{id}/cancel

Reuses the existing authentication, ownership guard and GenerationJob
infrastructure. The legacy flat ``/api/generation/jobs`` remains untouched.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user, get_db
from app.db.session import async_session_maker
from app.models.academic import User
from app.models.generation import ExamGenerationJob, GeneratedQuestion
from app.schemas.exam_structure import ExamConfig
from app.services.exam_generation_service import run_exam_job

import logging

_logger = logging.getLogger(__name__)

router = APIRouter()

_tasks: set[asyncio.Task] = set()

ACTIVE = ("queued", "running")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ExamGenerationCreate(BaseModel):
    exam_config: dict  # ExamConfig payload


class ExamPartProgress(BaseModel):
    total_questions: int
    completed_questions: int
    status: str = "pending"


class ExamGenerationRead(BaseModel):
    job_id: str
    status: str
    current_step: str | None = None
    progress_percent: int = 0
    total_questions: int | None = None
    completed_questions: int = 0
    part_a: ExamPartProgress | None = None
    part_b: ExamPartProgress | None = None
    paper_id: str | None = None
    error_message: str | None = None
    created_at: str | None = None
    finished_at: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fingerprint(config: ExamConfig) -> str:
    canonical = json.dumps(config.model_dump(), sort_keys=True, default=str)
    return "exam-" + hashlib.sha256(canonical.encode()).hexdigest()[:40]


async def _ensure_exam_access(job, current_user: User) -> None:
    if current_user.has_role("admin"):
        return
    if job.created_by is not None and job.created_by != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You do not have access to this generation job.")


def _iso(value):
    return value.isoformat() if value else None


async def _load_part_a_topic_pool(db: AsyncSession, config: ExamConfig) -> list[tuple[int, str]] | None:
    """Resolve the confirmed ATOMIC syllabus topics for Part A generation.

    Reads the latest faculty-confirmed ``SyllabusVersion`` for the configured
    subject and returns ``(unit_number, topic_name)`` pairs restricted to the
    selected units. Each entry is one atomic topic exactly as confirmed —
    combined/comma-joined pseudo-topics are never produced here because the
    syllabus parser already stores atomic ``SyllabusTopic`` rows.

    Returns ``None`` when no confirmed syllabus exists so the caller keeps its
    legacy fallback behaviour (never fabricates topics itself).
    """
    from app.models.academic import (
        Subject,
        Syllabus,
        SyllabusTopic,
        SyllabusUnit,
        SyllabusVersion,
    )

    subject = (await db.execute(
        select(Subject).where(func.lower(Subject.name) == config.subject.strip().lower())
    )).scalars().first()
    if subject is None:
        subject = (await db.execute(
            select(Subject).where(func.lower(Subject.code) == config.subject.strip().lower())
        )).scalars().first()
    if subject is None:
        return None

    version = (await db.execute(
        select(SyllabusVersion)
        .join(Syllabus, Syllabus.id == SyllabusVersion.syllabus_id)
        .where(Syllabus.subject_id == subject.id)
        .order_by(SyllabusVersion.version_number.desc())
        .limit(1)
    )).scalars().first()
    if version is None:
        return None

    selected = {int(u) for u in (config.selected_units or [])} or None
    rows = (await db.execute(
        select(SyllabusUnit.unit_number, SyllabusTopic.topic_name)
        .join(SyllabusTopic, SyllabusTopic.unit_id == SyllabusUnit.id)
        .where(SyllabusUnit.syllabus_version_id == version.id)
        .order_by(SyllabusUnit.unit_number, SyllabusTopic.topic_name)
    )).all()

    pool = [
        (int(unit_number), topic_name.strip())
        for unit_number, topic_name in rows
        if topic_name and topic_name.strip()
        and (selected is None or int(unit_number) in selected)
    ]
    return pool or None


async def _to_read(db: AsyncSession, job: ExamGenerationJob) -> ExamGenerationRead:
    counts = {"short_answer": 0, "main": 0}
    rows = (await db.execute(
        select(GeneratedQuestion.exam_part, func.count(GeneratedQuestion.id))
        .where(GeneratedQuestion.exam_generation_job_id == job.id)
        .group_by(GeneratedQuestion.exam_part))).all()
    for part, count in rows:
        if part in counts:
            counts[part] = int(count)
    config = ExamConfig.model_validate(job.exam_config_json)
    b_total = sum(len(g.parts) for g in config.part_b.groups)
    total = job.total_questions or (config.part_a.question_count + b_total)
    return ExamGenerationRead(
        job_id=job.id,
        status=job.status,
        current_step=job.current_step,
        progress_percent=job.progress_percent,
        total_questions=total,
        completed_questions=job.completed_questions,
        part_a=ExamPartProgress(
            total_questions=config.part_a.question_count,
            completed_questions=min(counts["short_answer"], config.part_a.question_count),
            status=("completed" if counts["short_answer"] >= config.part_a.question_count
                    else ("generating" if job.status == "running" else job.status)),
        ),
        part_b=ExamPartProgress(
            total_questions=b_total,
            completed_questions=min(counts["main"], b_total),
            status=("completed" if counts["main"] >= b_total and b_total else
                    ("pending" if counts["short_answer"] < config.part_a.question_count
                     else "generating")),
        ),
        paper_id=job.paper_id,
        error_message=(job.error_message or "")[:300] or None,
        created_at=_iso(job.created_at),
        finished_at=_iso(job.finished_at),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/jobs", response_model=ExamGenerationRead,
             status_code=status.HTTP_201_CREATED)
async def create_exam_generation_job(
    request: ExamGenerationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExamGenerationRead:
    """Queue a composite two-part examination generation job.

    Reuses an identical ACTIVE job for the same faculty member (idempotency
    semantics matching the legacy flat endpoint).
    """
    try:
        config = ExamConfig.model_validate(request.exam_config)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Invalid exam config: {exc}") from exc

    active = (await db.execute(
        select(ExamGenerationJob).where(
            ExamGenerationJob.created_by == current_user.user_id,
            ExamGenerationJob.status.in_(ACTIVE),
        ).order_by(ExamGenerationJob.created_at.desc()))).scalars().first()
    if active is not None and active.exam_config_json == config.model_dump():
        return await _to_read(db, active)

    job = ExamGenerationJob(
        id=str(uuid4()),
        exam_config_json=config.model_dump(),
        created_by=current_user.user_id,
        status="queued",
        current_step="Queued",
        total_questions=config.part_a.question_count
                        + sum(len(g.parts) for g in config.part_b.groups),
    )
    db.add(job)
    await db.commit()

    # Resolve the confirmed ATOMIC syllabus topics for the selected units so
    # Part A questions are generated from real syllabus material (never
    # fabricated pseudo-topics). Falls back to the legacy pool behaviour when
    # no confirmed syllabus exists for the subject.
    topic_pool = await _load_part_a_topic_pool(db, config)
    _spawn(job.id, topic_pool)
    return await _to_read(db, job)


@router.get("/jobs/{job_id}", response_model=ExamGenerationRead)
async def get_exam_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExamGenerationRead:
    job = await db.get(ExamGenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Exam generation job not found")
    await _ensure_exam_access(job, current_user)
    return await _to_read(db, job)


@router.post("/jobs/{job_id}/resume", response_model=ExamGenerationRead)
async def resume_exam_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExamGenerationRead:
    job = await db.get(ExamGenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Exam generation job not found")
    await _ensure_exam_access(job, current_user)
    if job.status != "failed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Only failed exam jobs can be resumed.")
    job.status = "queued"
    job.current_step = "Resuming"
    job.error_message = None
    await db.commit()
    _spawn(job.id, None)
    return await _to_read(db, job)


@router.post("/jobs/{job_id}/cancel", response_model=ExamGenerationRead)
async def cancel_exam_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ExamGenerationRead:
    job = await db.get(ExamGenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Exam generation job not found")
    await _ensure_exam_access(job, current_user)
    if job.status not in ACTIVE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Only queued or running exams can be cancelled.")
    job.status = "cancelled"
    job.current_step = "Cancelled by user"
    job.finished_at = _now()
    await db.commit()
    return await _to_read(db, job)


def _spawn(exam_job_id: str, topic_pool) -> None:
    async def _run() -> None:
        try:
            await run_exam_job(exam_job_id, part_a_topic_pool=topic_pool)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - harden background task
            # Sanitize: never echo secrets. Keep only a bounded, type-qualified
            # message. This still lets a job never stay stuck in "queued".
            _logger.exception("exam-generation background task failed")
            _sanitized = f"{type(exc).__name__}: {str(exc)[:200]}"
            try:
                async with async_session_maker() as s:
                    job = await s.get(ExamGenerationJob, exam_job_id)
                    if job is not None and job.status in ACTIVE:
                        job.status = "failed"
                        job.current_step = "Generation failed"
                        job.error_message = _sanitized
                        job.finished_at = datetime.now(timezone.utc)
                        await s.commit()
            except Exception as rec_exc:  # noqa: BLE001 - never mask the task
                _logger.exception("failed to persist exam job failure: %s", rec_exc)

    task = asyncio.get_running_loop().create_task(_run())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def _now():
    return datetime.now(timezone.utc)
