from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.academic import BloomLevel


class ModelPaperAnalyzeRequest(BaseModel):
    file_name: str
    extracted_text: str


class ModelPaperFinding(BaseModel):
    field: str
    value: str
    confidence: Literal["confirmed", "inferred", "unknown"] = "unknown"


class ModelPaperSectionFinding(BaseModel):
    name: str
    question_count: Optional[int] = None
    marks_per_question: Optional[int] = None
    numbering_style: Optional[str] = None
    confidence: Literal["confirmed", "inferred", "unknown"] = "unknown"


class ModelPaperAnalysisResult(BaseModel):
    exam_title: Optional[str] = None
    subject: Optional[str] = None
    total_marks: Optional[int] = None
    duration_minutes: Optional[int] = None
    sections: list[ModelPaperSectionFinding] = Field(default_factory=list)
    findings: list[ModelPaperFinding] = Field(default_factory=list)
    confidence: Literal["confirmed", "inferred", "unknown"] = "unknown"
    bloom_hints: list[BloomLevel] = Field(default_factory=list)
