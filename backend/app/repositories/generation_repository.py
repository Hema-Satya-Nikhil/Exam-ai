from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generation import GeneratedPaper, GeneratedQuestion, GenerationJob, PaperVersion, ValidationResult


@dataclass
class GenerationRepository:
    session: AsyncSession

    async def create_job(self, blueprint_id: str, status: str = "queued", current_step: str = "Blueprint accepted") -> GenerationJob:
        job = GenerationJob(
            blueprint_id=blueprint_id,
            status=status,
            current_step=current_step,
            progress_percent=5,
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_job(self, job_id: str) -> GenerationJob | None:
        return await self.session.get(GenerationJob, job_id)

    async def update_job_status(self, job_id: str, status: str, current_step: str | None = None, progress_percent: int | None = None, error_message: str | None = None) -> GenerationJob | None:
        job = await self.get_job(job_id)
        if job is None:
            return None
        job.status = status
        if current_step is not None:
            job.current_step = current_step
        if progress_percent is not None:
            job.progress_percent = progress_percent
        if error_message is not None:
            job.error_message = error_message
        if status in ("completed", "failed"):
            job.finished_at = datetime.now(timezone.utc)
        await self.session.flush()
        return job

    async def create_generated_question(self, job_id: str, question_data: dict) -> GeneratedQuestion:
        question = GeneratedQuestion(
            generation_job_id=job_id,
            question_number=question_data["question_number"],
            section=question_data["section"],
            marks=question_data["marks"],
            unit=question_data["unit"],
            topic=question_data["topic"],
            bloom_level=question_data["bloom_level"],
            difficulty=question_data.get("difficulty", "medium"),
            question_type=question_data.get("question_type", "conceptual"),
            choice_group=question_data.get("choice_group"),
            generation_instruction=question_data.get("generation_instruction"),
            question_text=question_data["question_text"],
            source_references=question_data.get("source_references", []),
            locked=question_data.get("locked", False),
        )
        self.session.add(question)
        await self.session.flush()
        return question

    async def list_questions(self, job_id: str) -> Sequence[GeneratedQuestion]:
        result = await self.session.execute(
            select(GeneratedQuestion)
            .where(GeneratedQuestion.generation_job_id == job_id)
            .order_by(GeneratedQuestion.question_number)
        )
        return result.scalars().all()

    async def create_paper(self, job_id: str, title: str) -> GeneratedPaper:
        paper = GeneratedPaper(generation_job_id=job_id, title=title, status="draft")
        self.session.add(paper)
        await self.session.flush()
        return paper

    async def get_paper(self, paper_id: str) -> GeneratedPaper | None:
        return await self.session.get(GeneratedPaper, paper_id)

    async def create_paper_version(
        self,
        paper_id: str,
        version_number: int,
        paper_json: dict,
        blueprint_version: dict,
        rules_version: dict,
        llm_model: str | None = None,
        prompt_version: str | None = None,
        validation_summary: dict | None = None,
    ) -> PaperVersion:
        version = PaperVersion(
            generated_paper_id=paper_id,
            version_number=version_number,
            paper_json=paper_json,
            blueprint_version=blueprint_version,
            rules_version=rules_version,
            llm_model=llm_model,
            prompt_version=prompt_version,
            validation_summary=validation_summary or {},
        )
        self.session.add(version)
        await self.session.flush()

        paper = await self.get_paper(paper_id)
        if paper:
            paper.current_version_id = version.id
            await self.session.flush()

        return version

    async def record_validation_result(self, scope: str, status: str, details: dict, job_id: str | None = None, question_id: str | None = None) -> ValidationResult:
        result = ValidationResult(
            generation_job_id=job_id,
            generated_question_id=question_id,
            scope=scope,
            status=status,
            details=details,
        )
        self.session.add(result)
        await self.session.flush()
        return result
