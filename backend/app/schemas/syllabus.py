from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.academic import ConfidenceLevel, TopicRead, UnitRead


class SyllabusUploadRequest(BaseModel):
    subject_id: str
    file_name: str
    extracted_text: str
    source_file_hash: Optional[str] = None


class SyllabusParseResult(BaseModel):
    source_file_name: str
    units: list[UnitRead] = Field(default_factory=list)
    confidence: ConfidenceLevel = "inferred"
    notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    ocr_used: bool = False


class SyllabusConfirmUnit(BaseModel):
    unit_number: int
    title: Optional[str] = None
    topics: list[str] = Field(default_factory=list)


class SyllabusConfirmRequest(BaseModel):
    subject_id: str
    source_file_name: str = ""
    units: list[SyllabusConfirmUnit] = Field(default_factory=list)


class SyllabusConfirmResult(BaseModel):
    syllabus_version_id: str
    subject_id: str
    source_file_name: str
    units: list[SyllabusConfirmUnit] = Field(default_factory=list)


class UnitMaterialUploadRequest(BaseModel):
    syllabus_version_id: str
    unit_number: int
    file_name: str
    mime_type: str
    extracted_text: str
    file_hash: str


class UnitMaterialRead(BaseModel):
    unit_number: int
    file_name: str
    version_number: int
    mime_type: str
    source_type: Literal["pdf", "docx", "txt"]
    page_references: list[str] = Field(default_factory=list)
