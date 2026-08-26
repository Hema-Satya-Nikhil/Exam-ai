from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

BloomLevel = Literal["L2", "L3", "L4", "L5", "L6"]
ConfidenceLevel = Literal["confirmed", "inferred", "unknown"]


class TopicRead(BaseModel):
    topic_name: str
    page_reference: Optional[str] = None
    confidence: ConfidenceLevel = "confirmed"


class UnitRead(BaseModel):
    unit_number: int
    title: Optional[str] = None
    confidence: ConfidenceLevel = "confirmed"
    topics: list[TopicRead] = Field(default_factory=list)


class SyllabusVersionRead(BaseModel):
    version_number: int
    source_file_name: Optional[str] = None
    structured_data: dict
    units: list[UnitRead] = Field(default_factory=list)


class QuestionRequirement(BaseModel):
    question_number: int
    section: str
    marks: int
    unit: int
    topic: str
    bloom_level: BloomLevel
    difficulty: str
    question_type: str
    choice_group: Optional[str] = None
    generation_instruction: Optional[str] = None


class PaperSectionSpec(BaseModel):
    name: str
    section_type: str
    question_count: int
    marks_per_question: int
    instructions: Optional[str] = None


class PaperBlueprint(BaseModel):
    exam_type: str
    subject: str
    selected_units: list[int]
    total_marks: int
    duration_minutes: int
    sections: list[PaperSectionSpec]
    questions: list[QuestionRequirement]
    source_mode: Literal["model_paper", "manual"]
    unit_materials_present: bool = False
    model_paper_confidence: ConfidenceLevel = "unknown"


class GeneratedQuestionRead(BaseModel):
    question_number: int
    section: str
    marks: int
    unit: int
    topic: str
    bloom_level: BloomLevel
    difficulty: str
    question_type: str
    choice_group: Optional[str] = None
    generation_instruction: Optional[str] = None
    question_text: str
    source_references: list[dict] = Field(default_factory=list)
    locked: bool = False
