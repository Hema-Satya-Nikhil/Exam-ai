from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.generation_repository import GenerationRepository
from app.schemas.academic import GeneratedQuestionRead, PaperBlueprint, QuestionRequirement
from app.schemas.generation import BatchGenerationResult, GenerationJobCreate, GenerationJobRead, ValidationIssue, ValidationSummary
from app.services.blueprint_service import BlueprintService
from app.services.llm.nvidia import NVIDIAProvider
from app.services.paper_workflow_service import PaperWorkflowService
from app.services.question_text_sanitizer import sanitize_question_text
from app.services.validation_service import ValidationService


@dataclass
class GenerationJobStore:
    jobs: dict[str, GenerationJobRead] = field(default_factory=dict)


class GenerationService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self.provider = NVIDIAProvider()
        self.validator = ValidationService()
        self.blueprint_service = BlueprintService()
        self.job_store = GenerationJobStore()
        self.paper_workflow = PaperWorkflowService(session)
        self.repo = GenerationRepository(session) if session else None

    async def generate_question_set(self, blueprint: PaperBlueprint) -> ValidationSummary:
        issues: list[ValidationIssue] = []
        for message in self.blueprint_service.validate_feasibility(blueprint):
            issues.append(ValidationIssue(code="blueprint_feasibility_error", message=message))

        validation = self.validator.validate_blueprint(blueprint)
        issues.extend(validation.issues)
        return ValidationSummary(passed=not issues, issues=issues)

    async def generate_paper_from_blueprint(self, payload: GenerationJobCreate) -> BatchGenerationResult:
        validation = self.validator.validate_blueprint(payload.blueprint)
        if not validation.passed:
            # Surface the actual blocking rules so the faculty can fix the
            # blueprint instead of staring at an opaque rejection.
            blocking = [issue for issue in validation.issues if issue.severity == "error"]
            detail = "; ".join(f"{issue.message} [{issue.code}]" for issue in blocking)
            raise ValueError(
                "Blueprint validation failed before generation. " + detail
            )

        job = await self.create_job_async(payload) if self.repo else self.create_job(payload)
        running_job = await self.mark_job_running_async(job.id, "Generating question set", 15) if self.repo else self.mark_job_running(job.id, "Generating question set", 15)
        if running_job is None:
            raise ValueError("Generation job could not be initialized.")

        generated_questions: list[GeneratedQuestionRead] = []
        for index, requirement in enumerate(payload.blueprint.questions):
            step = f"Generating question {requirement.question_number}"
            if self.repo:
                await self.mark_job_running_async(job.id, step, min(20 + index * 10, 95))
            else:
                self.mark_job_running(job.id, step, min(20 + index * 10, 95))
            question = await self.generate_single_question(requirement, self._context_for_requirement(payload.blueprint, requirement))
            generated_questions.append(question)
            if self.repo:
                await self.repo.create_generated_question(job.id, question.model_dump())

        paper_json = self._assemble_paper_json(payload.blueprint, generated_questions)
        draft = await self.paper_workflow.create_draft_async(
            __import__("app.schemas.paper_workflow", fromlist=["PaperDraftCreate"]).PaperDraftCreate(
                title=f"{payload.blueprint.exam_type} - {payload.blueprint.subject}",
                paper_json=paper_json,
            )
        )
        paper_json["paper_id"] = draft.id
        paper_json["validation"] = validation.model_dump()

        completed = await self.mark_job_completed_async(job.id) if self.repo else self.mark_job_completed(job.id)
        if completed is None:
            raise ValueError("Generation job could not be completed.")

        if self.repo:
            db_paper = await self.repo.create_paper(job.id, f"{payload.blueprint.exam_type} - {payload.blueprint.subject}")
            await self.repo.create_paper_version(
                paper_id=db_paper.id,
                version_number=1,
                paper_json=paper_json,
                blueprint_version=payload.blueprint.model_dump(),
                rules_version={"version": "1.0"},
                validation_summary=validation.model_dump(),
            )

        return BatchGenerationResult(job=completed, paper_id=draft.id, paper_json=paper_json, validation=validation)

    async def generate_single_question(self, requirement: QuestionRequirement, source_context: str) -> GeneratedQuestionRead:
        # Generate -> validate -> feed the exact rule violations back to the
        # model and retry. Every academic rule stays enforced; the loop only
        # gives the provider the chance to comply before we fail.
        feedback: str | None = None
        last_issues: list[str] = []
        max_attempts = max(1, settings.llm_max_retries + 1)

        for attempt in range(1, max_attempts + 1):
            payload = await self.provider.generate_question(requirement, source_context, feedback)
            question_text = sanitize_question_text(
                str(payload.get("question_text", "")).strip()
            )
            validation = self.validator.validate_question(requirement, question_text)
            if validation.passed:
                return GeneratedQuestionRead(
                    question_number=requirement.question_number,
                    section=requirement.section,
                    marks=requirement.marks,
                    unit=requirement.unit,
                    topic=requirement.topic,
                    bloom_level=requirement.bloom_level,
                    difficulty=requirement.difficulty,
                    question_type=requirement.question_type,
                    choice_group=requirement.choice_group,
                    generation_instruction=requirement.generation_instruction,
                    question_text=question_text,
                    source_references=list(payload.get("source_references", [])),
                    locked=False,
                )
            last_issues = [
                f"{issue.message} [{issue.code}]" for issue in validation.issues
            ]
            feedback = "\n".join(last_issues) if attempt < max_attempts else None

        raise ValueError(
            "Generated question failed validation after "
            f"{max_attempts} attempts: " + "; ".join(last_issues)
        )

    def _context_for_requirement(self, blueprint: PaperBlueprint, requirement: QuestionRequirement) -> str:
        unit_material_state = "available" if blueprint.unit_materials_present else "unavailable"
        return (
            f"Subject: {blueprint.subject}. Exam: {blueprint.exam_type}. Units: {', '.join(map(str, blueprint.selected_units))}. "
            f"Unit materials: {unit_material_state}. Section: {requirement.section}. Topic: {requirement.topic}."
        )

    def _assemble_paper_json(self, blueprint: PaperBlueprint, questions: list[GeneratedQuestionRead]) -> dict:
        sections: list[dict] = []
        for section in blueprint.sections:
            section_questions = [
                question.model_dump()
                for question in questions
                if question.section == section.name
            ]
            sections.append(
                {
                    "name": section.name,
                    "section_type": section.section_type,
                    "question_count": section.question_count,
                    "marks_per_question": section.marks_per_question,
                    "instructions": section.instructions,
                    "questions": section_questions,
                }
            )

        return {
            "title": f"{blueprint.exam_type} - {blueprint.subject}",
            "exam_name": blueprint.exam_type,
            "subject_name": blueprint.subject,
            "subject_code": blueprint.subject,
            "duration_minutes": blueprint.duration_minutes,
            "total_marks": blueprint.total_marks,
            "sections": sections,
            "questions": [question.model_dump() for question in questions],
            "instructions": ["Answer all questions as instructed by the section rules."],
            "source_mode": blueprint.source_mode,
            "selected_units": blueprint.selected_units,
        }

    def create_job(self, payload: GenerationJobCreate) -> GenerationJobRead:
        job = GenerationJobRead(
            id=str(uuid4()),
            status="queued",
            current_step="Blueprint accepted",
            progress_percent=5,
            retry_count=0,
            error_message=None,
        )
        self.job_store.jobs[job.id] = job
        return job

    async def create_job_async(self, payload: GenerationJobCreate) -> GenerationJobRead:
        job = self.create_job(payload)
        if self.repo:
            db_job = await self.repo.create_job("blueprint-placeholder", status="queued")
            job = job.model_copy(update={"id": db_job.id})
            self.job_store.jobs[job.id] = job
        return job

    def get_job(self, job_id: str) -> GenerationJobRead | None:
        return self.job_store.jobs.get(job_id)

    async def get_job_async(self, job_id: str) -> GenerationJobRead | None:
        if job_id in self.job_store.jobs:
            return self.job_store.jobs[job_id]
        if self.repo:
            db_job = await self.repo.get_job(job_id)
            if db_job:
                job = GenerationJobRead(
                    id=db_job.id,
                    status=db_job.status,
                    current_step=db_job.current_step,
                    progress_percent=db_job.progress_percent,
                    retry_count=db_job.retry_count,
                    error_message=db_job.error_message,
                )
                self.job_store.jobs[job.id] = job
                return job
        return None

    def mark_job_running(self, job_id: str, step: str, progress_percent: int) -> GenerationJobRead | None:
        job = self.job_store.jobs.get(job_id)
        if job is None:
            return None
        updated = job.model_copy(update={"status": "running", "current_step": step, "progress_percent": progress_percent})
        self.job_store.jobs[job_id] = updated
        return updated

    async def mark_job_running_async(self, job_id: str, step: str, progress_percent: int) -> GenerationJobRead | None:
        updated = self.mark_job_running(job_id, step, progress_percent)
        if self.repo:
            await self.repo.update_job_status(job_id, "running", current_step=step, progress_percent=progress_percent)
        return updated

    def mark_job_completed(self, job_id: str, step: str = "Ready for review") -> GenerationJobRead | None:
        job = self.job_store.jobs.get(job_id)
        if job is None:
            return None
        updated = job.model_copy(update={"status": "completed", "current_step": step, "progress_percent": 100})
        self.job_store.jobs[job_id] = updated
        return updated

    async def mark_job_completed_async(self, job_id: str, step: str = "Ready for review") -> GenerationJobRead | None:
        updated = self.mark_job_completed(job_id, step)
        if self.repo:
            await self.repo.update_job_status(job_id, "completed", current_step=step, progress_percent=100)
        return updated

    def mark_job_failed(self, job_id: str, error_message: str) -> GenerationJobRead | None:
        job = self.job_store.jobs.get(job_id)
        if job is None:
            return None
        updated = job.model_copy(update={"status": "failed", "error_message": error_message})
        self.job_store.jobs[job_id] = updated
        return updated

    async def mark_job_failed_async(self, job_id: str, error_message: str) -> GenerationJobRead | None:
        updated = self.mark_job_failed(job_id, error_message)
        if self.repo:
            await self.repo.update_job_status(job_id, "failed", error_message=error_message)
        return updated
