from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PaperDocumentExportRequest(BaseModel):
    paper_id: str
    format: Literal["pdf", "docx"]
    file_name: str = "question-paper"
    title: str = "Question Paper"
    institution_name: str = "AI-Based Question Paper Generation System"
    department_name: str = "Department of Computer Science"
    subject_name: str = "Subject"
    subject_code: str = ""
    exam_name: str = "Examination"
    duration_minutes: int = 0
    total_marks: int = 0
    instructions: list[str] = Field(default_factory=list)
