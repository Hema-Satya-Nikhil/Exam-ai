from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    blueprint_id: Mapped[str] = mapped_column(ForeignKey("question_blueprints.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    current_step: Mapped[Optional[str]] = mapped_column(String(120))
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    questions: Mapped[list[GeneratedQuestion]] = relationship(back_populates="job", cascade="all, delete-orphan")


class GeneratedQuestion(Base):
    __tablename__ = "generated_questions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    generation_job_id: Mapped[str] = mapped_column(ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(100), nullable=False)
    marks: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[int] = mapped_column(Integer, nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    bloom_level: Mapped[str] = mapped_column(String(10), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(30), nullable=False)
    question_type: Mapped[str] = mapped_column(String(80), nullable=False)
    choice_group: Mapped[Optional[str]] = mapped_column(String(80))
    generation_instruction: Mapped[Optional[str]] = mapped_column(Text)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_references: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    locked: Mapped[bool] = mapped_column(default=False, nullable=False)

    job: Mapped[GenerationJob] = relationship(back_populates="questions")

    __table_args__ = (UniqueConstraint("generation_job_id", "question_number", name="uq_job_question_number"),)


class GeneratedPaper(Base):
    __tablename__ = "generated_papers"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    generation_job_id: Mapped[str] = mapped_column(ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    current_version_id: Mapped[Optional[str]] = mapped_column(ForeignKey("paper_versions.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)


class PaperVersion(Base):
    __tablename__ = "paper_versions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    generated_paper_id: Mapped[str] = mapped_column(ForeignKey("generated_papers.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    paper_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    blueprint_version: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    rules_version: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    llm_model: Mapped[Optional[str]] = mapped_column(String(120))
    prompt_version: Mapped[Optional[str]] = mapped_column(String(80))
    validation_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    exported_pdf_path: Mapped[Optional[str]] = mapped_column(String(500))
    exported_docx_path: Mapped[Optional[str]] = mapped_column(String(500))

    __table_args__ = (UniqueConstraint("generated_paper_id", "version_number", name="uq_paper_version"),)


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    generation_job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("generation_jobs.id", ondelete="CASCADE"))
    generated_question_id: Mapped[Optional[str]] = mapped_column(ForeignKey("generated_questions.id", ondelete="CASCADE"))
    scope: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
