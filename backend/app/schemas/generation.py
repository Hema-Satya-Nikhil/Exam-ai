from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.academic import PaperBlueprint, QuestionRequirement


class GenerationJobCreate(BaseModel):
    blueprint: PaperBlueprint
    llm_model: Optional[str] = None
    prompt_version: str = "v1"


class GenerationJobRead(BaseModel):
    id: str
    status: Literal["queued", "running", "failed", "completed"]
    current_step: Optional[str] = None
    progress_percent: int = 0
    retry_count: int = 0
    error_message: Optional[str] = None


class ValidationIssue(BaseModel):
    code: str
    message: str
    path: Optional[str] = None
    severity: Literal["info", "warning", "error"] = "error"


class ValidationSummary(BaseModel):
    passed: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


class PaperExportRequest(BaseModel):
    paper_id: str
    format: Literal["pdf", "docx"]


class QuestionGenerationRequest(BaseModel):
    requirement: QuestionRequirement
    source_context: str


class BatchGenerationResult(BaseModel):
    job: GenerationJobRead
    paper_id: str
    paper_json: dict
    validation: ValidationSummary
