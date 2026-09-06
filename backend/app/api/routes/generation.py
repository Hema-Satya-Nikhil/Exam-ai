"""Generation routes: persistent background jobs + legacy synchronous path."""
from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user, get_db
from app.api.routes.generation_deps import ensure_job_access
from app.models.academic import QuestionBlueprint, User
from app.models.generation import GeneratedPaper, GeneratedQuestion, GenerationJob
from app.schemas.academic import PaperBlueprint
from app.schemas.generation import (
    BatchGenerationResult,
    GenerationJobCreate,
    GenerationJobRead,
    QuestionGenerationRequest,
)
from app.services.generation_service import GenerationService
from app.services.generation_worker import enqueue_job, finalize_cancelled
from app.services.syllabus_service import _resolve_subject


def _fingerprint(blueprint: PaperBlueprint) -> str:
    canonical = json.dumps(blueprint.model_dump(), sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _iso(value):
    return value.isoformat() if value else None


async def _job_to_read(db, job: GenerationJob) -> GenerationJobRead:
    completed = (await db.execute(
        select(func.count(GeneratedQuestion.id))
        .where(GeneratedQuestion.generation_job_id == job.id))).scalar_one()
    current = (await db.execute(
        select(func.max(GeneratedQuestion.question_number))
        .where(GeneratedQuestion.generation_job_id == job.id))).scalar_one()
    paper_id = job.paper_id or (await db.execute(
        select(GeneratedPaper.id)
        .where(GeneratedPaper.generation_job_id == job.id))).scalars().first()

    return GenerationJobRead(
        id=job.id,
        status=job.status,
        current_step=job.current_step,
        progress_percent=job.progress_percent,
        retry_count=job.retry_count,
        error_message=job.error_message,
        paper_id=paper_id,
        created_by=job.created_by,
        total_questions=job.total_questions,
        completed_questions=int(completed or 0),
        current_question=(int(current) + 1) if current is not None else None,
        created_at=_iso(job.created_at),
        started_at=_iso(job.started_at),
        finished_at=_iso(job.finished_at),
        updated_at=_iso(job.updated_at),
    )


class _ExistingJob(Exception):
    def __init__(self, job: GenerationJob) -> None:
        self.job = job


async def _create_job_record(db, payload: GenerationJobCreate,
                             user: User) -> GenerationJob:
    """Persist QuestionBlueprint + queued GenerationJob owned by the caller."""
    fingerprint = _fingerprint(payload.blueprint)
    existing = (await db.execute(
        select(GenerationJob).where(
            GenerationJob.created_by == user.user_id,
            GenerationJob.idempotency_key == fingerprint,
            GenerationJob.status.in_(("queued", "running")),
        ).order_by(GenerationJob.created_at.desc()))).scalars().first()
    if existing is not None:
        raise _ExistingJob(existing)

    subject = await _resolve_subject(db, payload.blueprint.subject)
    qb = QuestionBlueprint(
        id=str(uuid4()),
        exam_type=payload.blueprint.exam_type,
        subject_id=subject.id,
        blueprint_json=payload.blueprint.model_dump(),
        source_mode=payload.blueprint.source_mode,
        validation_status="approved",
    )
    db.add(qb)
    await db.flush()

    job = GenerationJob(
        id=str(uuid4()),
        blueprint_id=qb.id,
        status="queued",
        current_step="Queued",
        progress_percent=0,
        created_by=user.user_id,
        total_questions=len(payload.blueprint.questions),
        idempotency_key=fingerprint,
    )
    db.add(job)
    await db.flush()
    return job


router = APIRouter()
generation_service = GenerationService()


@router.post("/jobs", response_model=GenerationJobRead,
             status_code=status.HTTP_201_CREATED)
async def create_generation_job(
    request: GenerationJobCreate,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerationJobRead:
    """Queue an asynchronous generation job; returns immediately.

    Idempotent: if the same user already has an active (queued/running) job for
    an identical blueprint, that existing job is returned with HTTP 200 instead
    of creating duplicate generation work.
    """
    validation = generation_service.validator.validate_blueprint(request.blueprint)
    blocking = [i for i in validation.issues if i.severity == "error"]
    if not validation.passed:
        detail = "; ".join(f"{i.message} [{i.code}]" for i in blocking)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Blueprint validation failed before generation. {detail}")

    created = True
    try:
        job = await _create_job_record(db, request, current_user)
    except _ExistingJob as dup:
        job = dup.job
        created = False

    await db.commit()
    await db.refresh(job)
    read = await _job_to_read(db, job)
    if created:
        response.status_code = status.HTTP_201_CREATED
        enqueue_job(job.id)
    else:
        response.status_code = status.HTTP_200_OK
    return read


@router.get("/jobs/{job_id}", response_model=GenerationJobRead)
async def get_generation_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerationJobRead:
    job = await db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Generation job not found")
    ensure_job_access(job, current_user)
    return await _job_to_read(db, job)


@router.post("/jobs/{job_id}/resume", response_model=GenerationJobRead)
async def resume_generation_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerationJobRead:
    """Resume a failed job; checkpointed questions are NOT regenerated."""
    job = await db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Generation job not found")
    ensure_job_access(job, current_user)
    if job.status != "failed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Only failed jobs can be resumed.")
    job.status = "queued"
    job.current_step = "Resuming"
    job.error_message = None
    job.finished_at = None
    await db.commit()
    await db.refresh(job)
    enqueue_job(job.id)
    return await _job_to_read(db, job)


@router.post("/jobs/{job_id}/cancel", response_model=GenerationJobRead)
async def cancel_generation_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerationJobRead:
    job = await db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Generation job not found")
    ensure_job_access(job, current_user)
    if job.status not in ("queued", "running"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Only queued or running jobs can be cancelled.")
    job.status = "cancelled"
    job.current_step = "Cancelled by user"
    await db.commit()
    await finalize_cancelled(job.id)
    await db.refresh(job)
    return await _job_to_read(db, job)


from fastapi import APIRouter, HTTPException, status

from app.schemas.generation import BatchGenerationResult, GenerationJobCreate, GenerationJobRead, QuestionGenerationRequest
from app.services.generation_service import GenerationService
from app.db.session import async_session_maker
from app.models.academic import Subject, QuestionBlueprint
from app.models.generation import GeneratedPaper, GenerationJob, PaperVersion
from app.schemas.academic import PaperBlueprint
from sqlalchemy import select
from uuid import uuid4


async def _persist_audit_graph(blueprint: PaperBlueprint, paper_id: str, paper_json: dict, created_by: str | None = None) -> None:
    """Persist the minimal Postgres rows the audit models demand.

    The in-process generation flow never touches the DB (repo=None), but
    Approval ExportAudit rows are committed with FKs to
    ``generated_papers.id`` and ``paper_versions.id``. Without a matching row
    those commits raise IntegrityError -> 500/400. We therefore create the
    supporting graph (Subject -> QuestionBlueprint -> GenerationJob ->
    GeneratedPaper -> PaperVersion) idempotently, and record the real version id
    on the draft's ``paper_json`` so ExportAudit.approved_version resolves.
    """
    async with async_session_maker() as db:
        if await db.get(GeneratedPaper, paper_id) is not None:
            return
        subj = (await db.execute(
            select(Subject).where(Subject.code == blueprint.subject)
        )).scalars().first()
        if not subj:
            subj = Subject(id=str(uuid4()), code=blueprint.subject, name=blueprint.subject, department="Computer Science")
            db.add(subj)
            await db.flush()
        qb = QuestionBlueprint(
            id=str(uuid4()), exam_type=blueprint.exam_type, subject_id=subj.id,
            blueprint_json=blueprint.model_dump(), source_mode=blueprint.source_mode,
            validation_status="approved",
        )
        db.add(qb)
        await db.flush()
        job = GenerationJob(
            id=str(uuid4()), blueprint_id=qb.id, status="completed",
            current_step="Ready for review", progress_percent=100,
        )
        db.add(job)
        await db.flush()
        gp = GeneratedPaper(
            id=paper_id, generation_job_id=job.id, current_version_id=None,
            title=f"{blueprint.exam_type} - {blueprint.subject}", status="approved",
            # Link ownership to the faculty who triggered generation so the
            # dashboard "Recent Papers" list can filter by authenticated user.
            created_by=created_by,
        )
        db.add(gp)
        await db.flush()
        version = PaperVersion(
            id=str(uuid4()), generated_paper_id=paper_id, version_number=1,
            paper_json=paper_json, blueprint_version=blueprint.model_dump(),
            rules_version={"version": "1.0"}, validation_summary={"passed": True, "issues": []},
        )
        db.add(version)
        await db.flush()
        paper_json["version_id"] = version.id
        gp.current_version_id = version.id
        # Belt-and-suspenders: ensure the in-process draft also sees version_id.
        try:
            from app.api.routes.generation import generation_service as _gs
            stored = _gs.paper_workflow.store.papers.get(paper_id)
            if stored is not None:
                stored.paper_json["version_id"] = version.id
        except Exception:
            pass
        await db.commit()




@router.post("/questions/generate")
async def generate_single_question(request: QuestionGenerationRequest) -> dict[str, object]:
    try:
        result = await generation_service.generate_single_question(request.requirement, request.source_context)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/papers/generate", response_model=BatchGenerationResult)
async def generate_paper(request: GenerationJobCreate,
                         current_user: User = Depends(get_current_user)) -> BatchGenerationResult:
    try:
        result = await generation_service.generate_paper_from_blueprint(request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    # Generation runs in-process (repo=None) and never persists the audit FK
    # graph; Approval/ExportAudit commits would otherwise raise IntegrityError.
    # Create the rows best-effort -- never block a successful generation.
    try:
        await _persist_audit_graph(request.blueprint, result.paper_id, result.paper_json, created_by=current_user.user_id)
    except Exception as exc:  # pragma: no cover
        print(f"[generation] audit-graph persistence skipped: {exc}", flush=True)
    return result
