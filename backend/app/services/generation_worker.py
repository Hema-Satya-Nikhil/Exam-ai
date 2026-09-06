"""Background worker for the persistent GenerationJob workflow.

Reuses the existing infrastructure end-to-end:
* ``GenerationRepository``  - job/question/paper/version persistence
* ``GenerationService``     - NVIDIA call + validation-feedback retry loop
* ``PaperWorkflowService``  - the SAME singleton the review endpoints use, so
  a completed job opens the standard Review -> Approve -> Export flow
* ``GenerationJob``/``GeneratedQuestion`` - checkpoint rows in PostgreSQL

Checkpointing: after EVERY successfully generated question the row is flushed
and job progress is committed. On resume, requirement numbers that already
have persisted rows are skipped (the DB unique constraint on
``(generation_job_id, question_number)`` guarantees no duplicates), so
interrupted jobs continue exactly where they stopped without regenerating.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.session import async_session_maker
from app.models.academic import QuestionBlueprint
from app.models.generation import GeneratedPaper, GenerationJob, PaperVersion
from app.repositories.generation_repository import GenerationRepository
from app.schemas.academic import PaperBlueprint
from app.services.generation_service import GenerationService

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("queued", "running")
_tasks: set[asyncio.Task] = set()


def _spawn(job_id: str) -> None:
    task = asyncio.create_task(run_job(job_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def enqueue_job(job_id: str) -> None:
    """Start (or continue) the background worker for one job."""
    _spawn(job_id)


async def resume_interrupted_jobs() -> int:
    """Startup hook: re-enqueue queued/running jobs left by a previous run.

    Valid interrupted jobs are resumed (completed questions are never
    regenerated - the worker skips requirement numbers that already have
    persisted ``GeneratedQuestion`` rows). A **stale/incompatible legacy job** -
    whose stored ``blueprint_json`` can no longer be parsed as a ``PaperBlueprint``
    (e.g. it actually holds a composite ``ExamConfig`` shape ``part_a``/``part_b``)
    and would crash on resume - is instead safely marked ``failed`` with a clear
    sanitized reason, and is never re-queued, so it is not repeatedly resumed on
    every restart. Valid active jobs are unaffected.
    """
    resumed = 0
    async with async_session_maker() as session:
        jobs = (
            await session.execute(
                select(GenerationJob).where(GenerationJob.status.in_(ACTIVE_STATUSES))
            )
        ).scalars().all()
        for job in jobs:
            blueprint = await session.get(QuestionBlueprint, job.blueprint_id)
            if blueprint is None or _is_stale_incompatible(blueprint.blueprint_json):
                job.status = "failed"
                job.current_step = "Not resumed (incompatible legacy blueprint)"
                job.error_message = (
                    "Job blueprint is incompatible with the current schema and "
                    "was not resumed; record it as failed rather than retrying."
                )
                job.finished_at = datetime.now(timezone.utc)
                logger.warning(
                    "stale/incompatible legacy job %s marked failed (not resumed); "
                    "blueprint schema mismatch", job.id)
                continue
            logger.warning("resuming interrupted generation job %s", job.id)
            enqueue_job(job.id)
            resumed += 1
        await session.commit()
    if resumed == 0:
        logger.info("no interrupted generation jobs to resume")
    return resumed


def _is_stale_incompatible(blueprint_json: object) -> bool:
    """Return True when a generation job's stored blueprint_json can no longer be
    parsed as a ``PaperBlueprint`` (e.g. a legacy row that holds a composite
    ``ExamConfig`` shape ``part_a``/``part_b`` instead of a flat blueprint).

    Such rows would crash ``run_job`` the instant it validates the blueprint, so
    marking them terminal at startup is strictly safer than repeatedly resuming.
    """
    if not isinstance(blueprint_json, dict):
        return True
    try:
        PaperBlueprint.model_validate(blueprint_json)
        return False
    except Exception:  # noqa: BLE001 - shape mismatch is the signal we want
        return True


async def _generate_and_save(
    *,
    session_factory,
    service: GenerationService,
    blueprint: PaperBlueprint,
    requirement,
    job_id: str,
):
    """Generate one question and checkpoint it in its OWN AsyncSession.

    The heavy ``generate_single_question`` call (NVIDIA + validation-retry
    loop) is network-bound and shared-session-free, so it can safely run
    concurrently. Persistence uses a private session per question and commits
    independently, so a failure/IntegrityError on one question never breaks another.
    """
    context = service._context_for_requirement(blueprint, requirement)
    question = await service.generate_single_question(requirement, context)
    async with session_factory() as persist:
        repo = GenerationRepository(persist)
        try:
            await repo.create_generated_question(job_id, question.model_dump())
            await persist.commit()
        except IntegrityError:
            # Already checkpointed (resume edge / duplicate question-claim).
            await persist.rollback()
            logger.info("job %s question %d already persisted - skipping",
                        job_id, requirement.question_number)
    return question


async def run_job(job_id: str, session_factory=None, concurrency: int | None = None) -> None:
    """Execute one generation job with per-question checkpoints.

    ``session_factory`` defaults to the production session maker; tests may
    inject their own (e.g. in-memory SQLite) factory. ``concurrency`` controls
    how many questions are generated in parallel; defaults to
    ``settings.generation_concurrency``. Each parallel question uses its OWN
    session; the unique ``(job_id, question_number)`` constraint guarantees no
    duplicates; persistence commits are independent per question.
    """
    session_factory = session_factory or async_session_maker
    concurrency = concurrency if concurrency is not None else max(1, settings.generation_concurrency)
    service = GenerationService()

    async with session_factory() as session:
        repo = GenerationRepository(session)

        # Claim atomically so only one worker can move a job out of queued/running.
        pre = await session.get(GenerationJob, job_id)
        logger.info("job %s pre-claim status=%r", job_id, getattr(pre, "status", None))
        claim = await session.execute(
            update(GenerationJob)
            .where(GenerationJob.id == job_id, GenerationJob.status.in_(ACTIVE_STATUSES))
            .values(status="running",
                    started_at=func.coalesce(GenerationJob.started_at, func.now()))
        )
        await session.commit()
        if claim.rowcount == 0:
            logger.info("job %s not claimable (not active) - skipping", job_id)
            return

        job = await repo.get_job(job_id)
        blueprint_row = await session.get(QuestionBlueprint, job.blueprint_id)
        if blueprint_row is None:
            await repo.update_job_status(job_id, "failed",
                                         error_message="Blueprint record missing.")
            await session.commit()
            return

        blueprint = PaperBlueprint.model_validate(blueprint_row.blueprint_json)
        requirements = sorted(blueprint.questions, key=lambda q: q.question_number)
        total = len(requirements)

        done_rows = await repo.list_questions(job_id)
        completed_numbers = {q.question_number for q in done_rows}
        # Resumed rows are ORM objects; normalize to the read model so paper
        # assembly works identically for fresh and resumed questions.
        from app.schemas.academic import GeneratedQuestionRead

        generated = [
            GeneratedQuestionRead(
                question_number=q.question_number,
                section=q.section,
                marks=q.marks,
                unit=q.unit,
                topic=q.topic,
                bloom_level=q.bloom_level,
                difficulty=q.difficulty,
                question_type=q.question_type,
                choice_group=q.choice_group,
                generation_instruction=q.generation_instruction,
                question_text=q.question_text,
                source_references=q.source_references or [],
                locked=q.locked,
            )
            for q in done_rows
        ]
        logger.info("job %s: %d/%d questions already checkpointed",
                    job_id, len(completed_numbers), total)

        try:
            pending = [
                requirement for requirement in requirements
                if requirement.question_number not in completed_numbers
            ]
            logger.info("job %s: %d pending questions, concurrency=%d",
                        job_id, len(pending), concurrency)

            for start in range(0, len(pending), concurrency):
                batch = pending[start:start + concurrency]
                # Honour user cancellation between batches.
                await session.refresh(job)
                if job.status == "cancelled":
                    logger.info("job %s cancelled at %d/%d",
                                job_id, len(completed_numbers), total)
                    return

                batch_nums = [r.question_number for r in batch]
                progress = 10 + int(80 * len(completed_numbers) / total) if total else 90
                await repo.update_job_status(
                    job_id, "running",
                    current_step=f"Generating questions {batch_nums} of {total}",
                    progress_percent=progress,
                )
                await session.commit()

                # Each question runs in its OWN session (concurrency-safe).
                batch_results = await asyncio.gather(*(
                    _generate_and_save(
                        session_factory=session_factory,
                        service=service,
                        blueprint=blueprint,
                        requirement=requirement,
                        job_id=job_id,
                    )
                    for requirement in batch
                ))

                for question in batch_results:
                    completed_numbers.add(question.question_number)
                    generated.append(question)

                # ---- CHECKPOINT: rows + progress, but never clobber a cancel ----
                # A user may have cancelled while the batch was generating. If so,
                # the already-persisted questions (in their own sessions) stay, but
                # we must NOT write back a "running" status over the "cancelled".
                await session.refresh(job)
                if job.status not in ACTIVE_STATUSES:
                    logger.info("job %s no longer active (%s) after batch %s - "
                                "leaving %d checkpointed",
                                job_id, job.status, batch_nums, len(completed_numbers))
                    return
                progress = 10 + int(80 * len(completed_numbers) / total) if total else 90
                await repo.update_job_status(
                    job_id, "running",
                    current_step=f"Saved question {len(completed_numbers)} of {total}",
                    progress_percent=progress,
                )
                await session.commit()
                logger.info("job %s checkpoint %d/%d (batch %s)",
                            job_id, len(completed_numbers), total, batch_nums)

            # ---- assemble the paper through the existing review workflow ------
            paper_json = service._assemble_paper_json(blueprint, generated)
            summary = service.validator.validate_blueprint(blueprint)

            from app.schemas.paper_workflow import PaperDraftCreate

            # Create the draft on the generation route's service SINGLETON -
            # the export path's fallback resolves papers from exactly this
            # instance's store (see paper_workflow_service._generation_store_draft).
            from app.api.routes.generation import generation_service as _gs

            draft = await _gs.paper_workflow.create_draft_async(
                PaperDraftCreate(
                    title=f"{blueprint.exam_type} - {blueprint.subject}",
                    paper_json=paper_json,
                )
            )
            paper_json["paper_id"] = draft.id

            # Same id as the workflow draft, mirroring the synchronous flow so
            # Review/Approve/Export resolve a single identifier.
            paper = await repo.create_paper(
                job_id,
                f"{blueprint.exam_type} - {blueprint.subject}",
                paper_id=draft.id,
                # Link ownership to the faculty who triggered generation so the
                # dashboard "Recent Papers" list can filter by authenticated user.
                created_by=job.created_by,
            )
            version = await repo.create_paper_version(
                paper_id=paper.id,
                version_number=1,
                paper_json=paper_json,
                blueprint_version=blueprint.model_dump(),
                rules_version={"version": "1.0"},
                llm_model=settings.nvidia_model or None,
                validation_summary=summary.model_dump(),
            )
            paper_json["version_id"] = version.id
            # The workflow store holds a COPY of paper_json (create_draft does
            # not share the caller's dict), so push the enriched copy - now
            # carrying paper_id/version_id - back into the store. The export
            # path renders from this exact structure.
            version.paper_json = paper_json
            _gs.paper_workflow.store.papers[draft.id].paper_json = paper_json

            # Export requires an APPROVED GeneratedPaper (mirrors sync flow's
            # audit-graph which inserts status='approved'). Keep the workflow
            # store copy in sync so export's fallback path agrees.
            paper.status = "approved"
            stored_draft = _gs.paper_workflow.store.papers.get(draft.id)
            if stored_draft is not None:
                stored_draft.status = "approved"
            job.paper_id = paper.id
            job.finished_at = datetime.now(timezone.utc)
            await repo.update_job_status(
                job_id, "completed",
                current_step="Ready for review",
                progress_percent=100,
            )
            await session.commit()
            logger.info("job %s completed -> paper %s", job_id, paper.id)

        except Exception as exc:
            # Keep every already-checkpointed question; sanitized error only.
            await repo.update_job_status(
                job_id, "failed",
                current_step="Generation failed",
                error_message=str(exc)[:500],
            )
            await session.commit()
            logger.exception("job %s failed", job_id)


async def finalize_cancelled(job_id: str) -> None:
    """Stamp finish time for a job cancelled while queued/running."""
    async with async_session_maker() as session:
        await session.execute(
            update(GenerationJob)
            .where(GenerationJob.id == job_id, GenerationJob.status == "cancelled")
            .values(finished_at=datetime.now(timezone.utc))
        )
        await session.commit()


