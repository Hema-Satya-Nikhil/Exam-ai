"""Phase 2 - composite examination generation orchestration.

Additive: reuses the existing GenerationJob infrastructure, GenerationService
(NVIDIA + validation + retry), safe per-question session design, checkpointing
and resume semantics. The existing flat pipeline is untouched.

Parent flow:
    queued -> Part A stage -> Part B stage -> assemble -> validate -> completed

Resume never regenerates already-persisted questions; a failed Part A stops
Part B from starting while preserving every Part A checkpoint.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.session import async_session_maker
from app.models.academic import QuestionBlueprint  # noqa: F401  (schema parity)
from app.models.generation import (
    ExamGenerationJob,
    GeneratedPaper,
    GeneratedQuestion,
    GenerationJob,
    PaperVersion,
)
from app.schemas.academic import GeneratedQuestionRead, PaperBlueprint
from app.schemas.exam_structure import (
    ExamConfig,
    MainPaperConfig,
    ShortAnswerPaperConfig,
)
from app.schemas.generation import ValidationIssue, ValidationSummary
from app.services.exam_structure_service import compute_exam_marks, validate_exam
from app.services.generation_service import GenerationService
from app.services.composite_review import refresh_flattened_views

logger = logging.getLogger(__name__)

PART_A = "short_answer"
PART_B = "main"


# ---------------------------------------------------------------------------
# Requirement expansion - ExamConfig -> flat per-question requirement list
# ---------------------------------------------------------------------------


def build_part_a_requirements(
    config: ShortAnswerPaperConfig,
    topic_pool: list[tuple[int, str]],
) -> list[dict]:
    """Expand Part A into ``question_count`` independent 2-mark requirements."""
    pool = list(topic_pool or [])
    reqs: list[dict] = []
    for i in range(config.question_count):
        if pool:
            unit, topic = pool[i % len(pool)]
        else:
            unit = (config.selected_units or [1])[0]
            topic = f"Unit {unit} concept {i + 1}"
        bloom = "L2"
        by_level = config.bloom_distribution.by_level or {}
        # Distribute Bloom levels across question_count by their requested counts
        # (e.g. {"L2": 5, "L3": 5} -> first 5 L2, next 5 L3). Falls back to L2
        # for any question beyond the declared distribution.
        assigned_total = 0
        for level, count in by_level.items():
            if i < assigned_total + count:
                bloom = level
                break
            assigned_total += count
        reqs.append({
            "question_number": i + 1,
            "section": "Part A",
            "marks": config.marks_per_question,
            "unit": unit,
            "topic": topic,
            "bloom_level": bloom,
            "difficulty": "easy" if config.marks_per_question <= 2 else "medium",
            "question_type": (config.allowed_question_types or ["short_answer"])[0],
            "exam_part": PART_A,
            "group_number": None,
            "part_label": None,
            "choice_group_id": None,
            "choice_member_id": None,
        })
    return reqs


def build_part_b_requirements(config: MainPaperConfig) -> list[dict]:
    """Expand Part B groups/parts into requirements preserving choice metadata."""
    reqs: list[dict] = []
    for group in sorted(config.groups, key=lambda g: g.group_number):
        for part in group.parts:
            member_id = part.choice_member or (
                f"{group.group_number}{part.part_label or ''}" if group.choice_group else None
            )
            reqs.append({
                "question_number": _flat_question_number(group, part),
                "section": f"Part B - Q{group.group_number}",
                "marks": part.marks,
                "unit": part.unit,
                "topic": part.topic,
                "bloom_level": part.bloom_level,
                "difficulty": part.difficulty,
                "question_type": part.question_type,
                "generation_instruction": part.generation_instruction
                                          or part.source_restriction,
                "exam_part": PART_B,
                "group_number": group.group_number,
                "part_label": part.part_label,
                "choice_group_id": group.choice_group,
                "choice_member_id": member_id,
            })
    return reqs


def _flat_question_number(group, part) -> int:
    """Stable unique integer per part so the existing unique constraint holds."""
    base = group.group_number * 10
    if not part.part_label:
        return base
    offset = ord(part.part_label.lower()) - ord("a") + 1
    return base + max(1, offset)
# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def _generate_one(*, session_factory, service: GenerationService,
                        req: dict, exam_job_id: str) -> GeneratedQuestionRead:
    """Generate one composite question; persist it with exam metadata in its
    OWN session so a failure never loses other checkpoints."""
    from app.schemas.academic import QuestionRequirement

    requirement = QuestionRequirement(
        question_number=req["question_number"], section=req["section"],
        marks=req["marks"], unit=req["unit"], topic=req["topic"],
        bloom_level=req["bloom_level"], difficulty=req["difficulty"],
        question_type=req["question_type"],
        choice_group=req.get("choice_group_id"),
        generation_instruction=req.get("generation_instruction"),
    )
    context = (f"Section: {req['section']}. Unit: {req['unit']}. "
               f"Topic: {req['topic']}. Marks: {req['marks']}.")
    question = await service.generate_single_question(requirement, context)

    async with session_factory() as persist:
        row = GeneratedQuestion(
            generation_job_id=req.get("child_job_id") or str(uuid.uuid4()),
            question_number=req["question_number"],
            section=req["section"], marks=req["marks"], unit=req["unit"],
            topic=req["topic"], bloom_level=req["bloom_level"],
            difficulty=req["difficulty"], question_type=req["question_type"],
            choice_group=req.get("choice_group_id"),
            generation_instruction=req.get("generation_instruction"),
            question_text=question.question_text,
            source_references={"refs": question.source_references},
            locked=False,
            # composite metadata
            exam_generation_job_id=exam_job_id,
            exam_part=req["exam_part"],
            group_number=req.get("group_number"),
            part_label=req.get("part_label"),
            choice_group_id=req.get("choice_group_id"),
            choice_member_id=req.get("choice_member_id"),
        )
        persist.add(row)
        try:
            await persist.commit()
        except IntegrityError:
            await persist.rollback()  # already checkpointed (resume edge)
    return question


async def _run_stage(*, stage_label: str, requirements: list[dict],
                     exam_job_id: str, child_job_id: str | None,
                     session_factory, service: GenerationService,
                     concurrency: int, done_keys: set[str],
                     report) -> list[GeneratedQuestionRead]:
    """Run one child stage in batches of ``concurrency``; returns results in order."""
    results: list[GeneratedQuestionRead] = []
    pending = [r for r in requirements
               if f"{r['exam_part']}:{r['question_number']}" not in done_keys]
    logger.info("exam job %s %s stage: %d pending", exam_job_id, stage_label, len(pending))
    for start in range(0, len(pending), concurrency):
        batch = pending[start:start + concurrency]
        reqs_with_job = [{**r, "child_job_id": child_job_id} for r in batch]
        await report(stage_label, batch[0])
        batch_results = await asyncio.gather(*(
            _generate_one(session_factory=session_factory, service=service,
                          req=r, exam_job_id=exam_job_id)
            for r in reqs_with_job))
        results.extend(batch_results)
        for i, q in enumerate(batch_results):
            done_keys.add(f"{batch[i]['exam_part']}:{batch[i]['question_number']}")
        await report(stage_label + " saved", batch[-1])
    return results
# ---------------------------------------------------------------------------
# Parent entry point
# ---------------------------------------------------------------------------


async def _create_child_generation_jobs(
    session, exam_job: ExamGenerationJob, total_a: int, total_b: int
) -> tuple[str, str]:
    """Create real child GenerationJob rows so existing checkpoint/resume and
    restart-scan infrastructure keeps working for each part.

    Both children reference a real ``QuestionBlueprint`` (created on demand for
    the composite exam config) so the NOT NULL ``blueprint_id`` FK holds on
    PostgreSQL/Supabase (in-memory SQLite tests do not enforce it).
    """
    from app.services.syllabus_service import _resolve_subject

    config = ExamConfig.model_validate(exam_job.exam_config_json)
    subject = await _resolve_subject(session, config.subject)

    qb = QuestionBlueprint(
        id=str(uuid.uuid4()),
        exam_type=config.exam_type,
        subject_id=subject.id,
        blueprint_json=exam_job.exam_config_json,
        source_mode=getattr(config.part_b, "source_mode", "model"),
        validation_status="approved",
    )
    session.add(qb)
    await session.flush()

    child_opts = dict(status="queued", created_by=exam_job.created_by)
    sa = GenerationJob(id=str(uuid.uuid4()), blueprint_id=qb.id,
                       current_step="Part A queued",
                       total_questions=total_a, **child_opts)
    mp = GenerationJob(id=str(uuid.uuid4()), blueprint_id=qb.id,
                       current_step="Part B queued",
                       total_questions=total_b, **child_opts)
    session.add_all([sa, mp])
    await session.flush()
    exam_job.short_answer_job_id = sa.id
    exam_job.main_paper_job_id = mp.id
    return sa.id, mp.id


def make_reporter(session_factory, exam_job_id: str, done_keys: set,
                  total: int):
    async def report(step: str, current_req: dict | None = None) -> None:
        async with session_factory() as s:
            j = await s.get(ExamGenerationJob, exam_job_id)
            if j is None:
                return
            j.completed_questions = len(done_keys)
            label = step + (f" - {current_req['section']}" if current_req else "")
            j.current_step = label[:160]
            j.progress_percent = (10 + int(80 * len(done_keys) / total)) if total else 90
            await s.commit()
    return report


async def run_exam_job(exam_job_id: str, session_factory=None,
                       concurrency: int | None = None,
                       part_a_topic_pool: list[tuple[int, str]] | None = None) -> None:
    """Execute the composite examination generation end-to-end.

    Stages run sequentially (Part A then Part B). If a stage fails, the parent
    is marked failed with all checkpoints preserved and later stages never start.
    Resume skips every already-persisted question.
    """
    session_factory = session_factory or async_session_maker
    concurrency = concurrency if concurrency is not None else max(1, settings.generation_concurrency)
    service = GenerationService()

    async with session_factory() as session:
        exam_job = await session.get(ExamGenerationJob, exam_job_id)
        if exam_job is None or exam_job.status not in ("queued", "running"):
            return
        config = ExamConfig.model_validate(exam_job.exam_config_json)
        exam_job.status = "running"
        exam_job.current_step = "Starting composite generation"
        exam_job.started_at = exam_job.started_at or datetime.now(timezone.utc)
        total_a = config.part_a.question_count
        total_b = sum(len(g.parts) for g in config.part_b.groups)
        exam_job.total_questions = total_a + total_b
        child_a, child_b = await _create_child_generation_jobs(
            session, exam_job, total_a, total_b)
        await session.commit()

    async with session_factory() as s:
        rows = (await s.execute(select(GeneratedQuestion).where(
            GeneratedQuestion.exam_generation_job_id == exam_job_id))).scalars().all()
    done_keys = {f"{r.exam_part}:{r.question_number}" for r in rows}
    logger.info("exam job %s: %d/%d already checkpointed",
                exam_job_id, len(done_keys), exam_job.total_questions)

    report = make_reporter(session_factory, exam_job_id, done_keys,
                           exam_job.total_questions)

    try:
        # ---- Stage 1: Part A ---------------------------------------------
        part_a_reqs = build_part_a_requirements(config.part_a, part_a_topic_pool or [])
        await report("PART A - generating")
        await _run_stage(stage_label="part_a", requirements=part_a_reqs,
                         exam_job_id=exam_job_id, child_job_id=child_a,
                         session_factory=session_factory, service=service,
                         concurrency=concurrency, done_keys=done_keys,
                         report=report)
        await report("PART A complete")

        # ---- Stage 2: Part B (never starts if Part A failed) --------------
        await report("PART B - generating")
        part_b_reqs = build_part_b_requirements(config.part_b)
        part_b_rows = await _run_stage(
            stage_label="part_b", requirements=part_b_reqs,
            exam_job_id=exam_job_id, child_job_id=child_b,
            session_factory=session_factory, service=service,
            concurrency=concurrency, done_keys=done_keys, report=report)

        # ---- Stage 3: assemble + validate + persist -----------------------
        await report("Assembling composite paper")
        await _assemble_and_finalize(
            exam_job_id=exam_job_id, config=config,
            session_factory=session_factory, service=service,
            done_keys=done_keys, child_job_ids=(child_a, child_b))
    except Exception as exc:
        async with session_factory() as s:
            j = await s.get(ExamGenerationJob, exam_job_id)
            if j is not None and j.status in ("queued", "running"):
                j.status = "failed"
                j.error_message = str(exc)[:500]
                j.finished_at = datetime.now(timezone.utc)
                await s.commit()
# ---------------------------------------------------------------------------
# Assembly - only after BOTH parts are complete and full-exam validation passes
# ---------------------------------------------------------------------------


def _group_view(config_b: MainPaperConfig, rows: list) -> list[dict]:
    out: list[dict] = []
    for g in sorted(config_b.groups, key=lambda x: x.group_number):
        parts = []
        for p in g.parts:
            match = next((r for r in rows
                          if r.group_number == g.group_number
                          and (r.part_label or "") == (p.part_label or "")), None)
            meta = _question_meta(match) if match else {
                "difficulty": p.difficulty, "question_type": p.question_type,
                "locked": False, "source_references": {"refs": []}}
            parts.append({
                "part_label": p.part_label,
                "question_number": p.question_number,
                "marks": p.marks,
                "unit": p.unit,
                "topic": p.topic,
                "bloom_level": p.bloom_level,
                "difficulty": meta.get("difficulty", p.difficulty),
                "question_type": meta.get("question_type", p.question_type),
                "locked": meta.get("locked", False),
                # Composite identity metadata so the Review UI can build the
                # same exam_part/group_number/part_label payload the
                # regeneration endpoint requires (mirrors Part A's _question_meta).
                "exam_part": meta.get("exam_part", PART_B),
                "group_number": meta.get("group_number", g.group_number),
                "choice_group_id": g.choice_group,
                "choice_member_id": p.choice_member,
                "source_references": meta.get("source_references", {"refs": []}),
                "question_text": match.question_text if match else "",
            })
        out.append({"group_number": g.group_number,
                    "choice_group": g.choice_group, "parts": parts})
    return out


def _question_meta(row) -> dict:
    """Full per-question metadata so Review/regeneration preserves constraints."""
    return {
        "unit": row.unit,
        "topic": row.topic,
        "bloom_level": row.bloom_level,
        "difficulty": row.difficulty,
        "question_type": row.question_type,
        "exam_part": row.exam_part,
        "group_number": row.group_number,
        "part_label": row.part_label,
        "choice_group_id": row.choice_group_id,
        "choice_member_id": row.choice_member_id,
        "locked": row.locked,
        "source_references": {"refs": row.source_references.get("refs", [])
                              if isinstance(row.source_references, dict) else []},
    }


def _flat_sections(config: ExamConfig, part_a_rows, part_b_rows) -> list[dict]:
    """Legacy-compatible flat view so the existing renderer keeps working.

    Each entry carries the full composite metadata so the existing
    regeneration endpoint can preserve group/part/choice constraints.
    """
    part_a = {
        "name": "PART A - SHORT ANSWER",
        "section_type": "short_answer",
        "marks_per_question": config.part_a.marks_per_question,
        "questions": [dict({"question_number": q.question_number, "marks": q.marks,
                            "section": "Part A",
                            "question_text": q.question_text},
                           **_question_meta(q)) for q in part_a_rows],
    }
    by_group: dict[int, list] = {}
    for r in part_b_rows:
        by_group.setdefault(r.group_number, []).append(r)
    pb_questions = []
    for gn in sorted(by_group):
        for r in sorted(by_group[gn], key=lambda x: x.question_number):
            label = f"{gn}{r.part_label or ''}"
            entry = {
                "question_number": r.question_number,
                "section": f"Q{label}", "marks": r.marks,
                "choice_group": r.choice_group_id,
                "question_text": r.question_text,
            }
            entry.update(_question_meta(r))
            pb_questions.append(entry)
    part_b = {"name": "PART B - MAIN PAPER", "section_type": "main",
              "marks_per_question": 5, "questions": pb_questions}
    return [part_a, part_b]


def _build_validation_record(validation: ValidationSummary) -> dict:
    """Build the persisted composite validation object stored in ``paper_json``.

    Shape is ``{"passed", "errors", "warnings"}`` (the DB source of truth the
    export gate reads directly) plus a legacy-aligned ``issues`` list so any
    existing consumer of the combined list stays compatible. Errors are
    error-severity issues only; warnings never block export/generation.
    """
    issues = [i.model_dump() for i in validation.issues]
    return {
        "passed": validation.passed,
        "errors": [i for i in issues if i.get("severity") == "error"],
        "warnings": [i for i in issues if i.get("severity") == "warning"],
        "issues": issues,
    }


async def _assemble_and_finalize(*, exam_job_id: str, config: ExamConfig,
                                 session_factory, service, done_keys: set,
                                 child_job_ids: tuple[str, str]) -> None:
    """Assemble the composite PaperVersion only when both parts completed AND
    full-exam validation passes. A persisted ``validation`` object is embedded
    in ``paper_json`` so the export gate reads the DB-recorded result directly.
    """
    validation = validate_exam(config)
    if not validation.passed:
        raise ValueError("Full-exam validation failed: "
                         + "; ".join(i.message for i in validation.issues))

    async with session_factory() as s:
        rows = (await s.execute(select(GeneratedQuestion).where(
            GeneratedQuestion.exam_generation_job_id == exam_job_id))).scalars().all()
        exam_job = await s.get(ExamGenerationJob, exam_job_id)
        if exam_job is None:
            raise ValueError("exam generation job row disappeared")

        part_a_rows = sorted([r for r in rows if r.exam_part == PART_A],
                             key=lambda r: r.question_number)
        part_b_rows = sorted([r for r in rows if r.exam_part == PART_B],
                             key=lambda r: r.question_number)

        marks = compute_exam_marks(config)

        # Hard institutional gate before any version is persisted.
        pa_marks = sum(q.marks for q in part_a_rows)
        if len(part_a_rows) != config.part_a.question_count or pa_marks != config.part_a.total_marks:
            raise ValueError("Part A does not contain exactly {0} x {1}-mark questions.".format(config.part_a.question_count, config.part_a.marks_per_question))
        expected_parts_b = sum(len(g.parts) for g in config.part_b.groups)
        if len(part_b_rows) != expected_parts_b:
            raise ValueError("Part B incomplete: {0} of {1} alternatives generated.".format(len(part_b_rows), expected_parts_b))
        if marks.part_b.attempted_required_marks != config.part_b.total_marks:
            raise ValueError("Part B attempted marks ({0}) != configured total ({1}).".format(marks.part_b.attempted_required_marks, config.part_b.total_marks))

        paper_json = {
            "title": f"{config.exam_type} - {config.subject}",
            "exam_name": config.exam_type,
            "subject_name": config.subject,
            "duration_minutes": config.total_duration,
            "total_marks": config.total_marks,
            "printed_available_marks": marks.printed_available_total,
            "attempted_required_marks": marks.attempted_required_total,
            "instructions": [
                "PART A: answer ALL questions.",
                "PART B: answer according to the internal-choice (OR) rules.",
            ],
            "parts": {
                "part_a": {"name": "PART A - SHORT ANSWER",
                           "total_marks": config.part_a.total_marks,
                           "duration_minutes": config.part_a.duration_minutes,
                           "questions": [dict({"question_number": q.question_number,
                                               "marks": q.marks,
                                               "section": "Part A",
                                               "question_text": q.question_text},
                                              **_question_meta(q))
                                          for q in part_a_rows]},
                "part_b": {"name": "PART B - MAIN PAPER",
                           "total_marks": config.part_b.total_marks,
                           "duration_minutes": config.part_b.duration_minutes,
                           "groups": _group_view(config.part_b, part_b_rows)},
            },
            "locked_question_numbers": [],
            "locked_question_keys": [],
            # legacy-compatible flat view so the existing renderer works
            "sections": _flat_sections(config, part_a_rows, part_b_rows),
            "questions": [{"question_number": r.question_number,
                           "section": r.section, "marks": r.marks,
                           "question_text": r.question_text,
                           **_question_meta(r)} for r in rows],
        }
        refresh_flattened_views(paper_json)
        # Persist the full-exam validation record inside the paper JSON so the
        # export gate (papers.py `_blocking_validation_issues`) can read the
        # explicit DB-recorded result directly instead of cosmetic fallbacks.
        paper_json["validation"] = _build_validation_record(validation)

        paper = GeneratedPaper(
            id=str(uuid.uuid4()),
            generation_job_id=child_job_ids[0],
            title=paper_json["title"], status="approved",
            # Link ownership to the faculty who triggered generation so the
            # dashboard "Recent Papers" list can filter by authenticated user.
            created_by=exam_job.created_by,
        )
        s.add(paper)
        await s.flush()

        version = PaperVersion(
            generated_paper_id=paper.id, version_number=1,
            paper_json=paper_json,
            blueprint_version=config.model_dump(),
            rules_version={"version": "2.0"},
            llm_model=settings.nvidia_model or None,
            validation_summary=validation.model_dump(),
        )
        s.add(version)
        await s.flush()

        paper.current_version_id = version.id
        exam_job.paper_id = paper.id
        exam_job.status = "completed"
        exam_job.current_step = "Ready for review"
        exam_job.progress_percent = 100
        exam_job.completed_questions = len(rows)
        exam_job.finished_at = datetime.now(timezone.utc)
        await s.commit()
        logger.info("exam job %s completed -> paper %s (v%d)",
                    exam_job_id, paper.id, version.version_number)
