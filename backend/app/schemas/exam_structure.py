"""Additive data model for the actual institutional examination structure.

This is an OPT-IN, backward-compatible layer. The existing single `PaperBlueprint`
pipeline (flat sections + flat questions) is left untouched and fully supported;
this module introduces the two-part institutional format (Part A short-answer +
Part B main paper with explicit choice/OR groups) as a separate schema set.

Key concepts:
* ``ChoiceGroup``   - an explicit OR/choice relationship. ``members`` are
  question/part keys; ``select_count`` is how many the student must attempt.
  This is deliberately NOT the old ``internal_choice = true`` boolean.
* ``QuestionGroup`` - a visible question block (e.g. Q2) composed of parts
  (e.g. 2(a), 2(b)). Same-group parts are compulsory unless in a ``ChoiceGroup``.
* Marks model      - ``printed_available_marks`` != ``attempted_required_marks``
  because OR alternatives print more marks than must be answered.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.academic import BloomLevel

PartKey = str  # e.g. "2", "2a", "5c"


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------


class ChoiceMember(BaseModel):
    """One selectable alternative inside a ChoiceGroup (a question/part key)."""

    key: PartKey
    marks: int
    unit: int
    topic: str
    bloom_level: BloomLevel
    difficulty: str = "medium"
    question_type: str = "analytical"
    source_restriction: Optional[str] = None


class ChoiceGroup(BaseModel):
    """Explicit OR/choice relationship.

    ``choice_type``:
      * ``group``  - whole question groups are alternatives (Q2 <=> Q3).
      * ``part``   - parts within one group are alternatives (2(a) <=> 2(b)).
      * ``multi``  - pick ``select_count`` of N alternatives (Q5 <=> Q6 <=> Q7).
    """

    id: str
    choice_type: Literal["group", "part", "multi"] = "multi"
    select_count: int = Field(default=1, ge=1)
    members: list[ChoiceMember] = Field(min_length=2)

    @model_validator(mode="after")
    def _select_le_members(self) -> "ChoiceGroup":
        if self.select_count > len(self.members):
            raise ValueError(
                f"choice group '{self.id}': select_count ({self.select_count}) "
                f"cannot exceed member count ({len(self.members)})"
            )
        return self


class QuestionPart(BaseModel):
    """One answerable unit within a question group (a visible part)."""

    question_number: int
    part_label: Optional[str] = None  # None => the whole group is one question
    marks: int = Field(gt=0)
    unit: int
    topic: str
    bloom_level: BloomLevel
    difficulty: str = "medium"
    question_type: str = "analytical"
    source_restriction: Optional[str] = None
    generation_instruction: Optional[str] = None
    choice_member: Optional[PartKey] = None  # key if this part is an alternative


class QuestionGroup(BaseModel):
    """A visible question block (e.g. Q2) made of one or more parts."""

    group_number: int = Field(gt=0)
    parts: list[QuestionPart] = Field(min_length=1)
    choice_group: Optional[str] = None  # group-level OR membership (Q2 <=> Q3)
# ---------------------------------------------------------------------------
# Part A / Part B configuration
# ---------------------------------------------------------------------------


class BloomDistribution(BaseModel):
    """``bloom_level -> count`` distribution (defaults to flat)."""

    by_level: dict[BloomLevel, int] = Field(default_factory=dict)


class ShortAnswerPaperConfig(BaseModel):
    """Part A - independent 2-mark short-answer paper.

    Defaults to the institutional requirement (10 x 2 marks = 20 marks, 20 min)
    but every value is configurable.
    """

    question_count: int = Field(default=10, ge=1)
    marks_per_question: int = Field(default=2, ge=1)
    total_marks: int = Field(default=20, ge=1)
    duration_minutes: int = Field(default=20, ge=1)
    selected_units: list[int] = Field(default_factory=list)
    bloom_distribution: BloomDistribution = Field(default_factory=BloomDistribution)
    allowed_question_types: list[str] = Field(
        default_factory=lambda: ["short_answer", "recall"]
    )
    topic_distribution: Optional[dict[str, int]] = None

    @model_validator(mode="after")
    def _marks_consistent(self) -> "ShortAnswerPaperConfig":
        if self.question_count * self.marks_per_question != self.total_marks:
            raise ValueError(
                "Part A marks inconsistent: "
                f"{self.question_count} x {self.marks_per_question} "
                f"!= total {self.total_marks}"
            )
        return self


class MainPaperConfig(BaseModel):
    """Part B - 30-mark main question paper with group/choice structure."""

    total_marks: int = Field(default=30, ge=1)
    duration_minutes: int = Field(default=90, ge=1)
    selected_units: list[int] = Field(default_factory=list)
    source_mode: Literal["model", "manual"] = "model"
    groups: list[QuestionGroup] = Field(default_factory=list)
    choice_groups: list[ChoiceGroup] = Field(default_factory=list)


class ExamConfig(BaseModel):
    """The complete examination = Part A + Part B."""

    exam_type: str
    subject: str
    selected_units: list[int] = Field(default_factory=list)
    part_a: ShortAnswerPaperConfig
    part_b: MainPaperConfig

    @property
    def total_marks(self) -> int:
        return self.part_a.total_marks + self.part_b.total_marks

    @property
    def total_duration(self) -> int:
        return self.part_a.duration_minutes + self.part_b.duration_minutes


# ---------------------------------------------------------------------------
# Marks model - printed vs attempted
# ---------------------------------------------------------------------------


class PartMarks(BaseModel):
    printed_available_marks: int = 0
    attempted_required_marks: int = 0


class ExamMarks(BaseModel):
    part_a: PartMarks
    part_b: PartMarks

    @property
    def printed_available_total(self) -> int:
        return self.part_a.printed_available_marks + self.part_b.printed_available_marks

    @property
    def attempted_required_total(self) -> int:
        return self.part_a.attempted_required_marks + self.part_b.attempted_required_marks

# ---------------------------------------------------------------------------
# Model-paper extraction output (confidence-tracked) - Phase 1
# ---------------------------------------------------------------------------


class ExtractionSourceRef(BaseModel):
    """Where a group/part/choice was detected, and how confident we are."""

    evidence: str = ""
    confidence: Literal["confirmed", "inferred", "unknown"] = "unknown"


class GroupExtraction(BaseModel):
    group_number: int
    group_evidence: ExtractionSourceRef = Field(default_factory=ExtractionSourceRef)
    parts: list[QuestionPart] = Field(default_factory=list)
    part_labels: list[str] = Field(default_factory=list)
    marks_evidence: list[int] = Field(default_factory=list)
    btl: list[str] = Field(default_factory=list)     # e.g. ["L3"]
    co: list[str] = Field(default_factory=list)       # e.g. ["CO1"]
    section: Optional[str] = None
    unit: Optional[int] = None
    topic_hint: Optional[str] = None


class ChoiceDetection(BaseModel):
    """An OR/choice relationship detected between groups or parts."""

    choice_id: str
    member_keys: list[PartKey] = Field(min_length=2)
    select_count: int = 1
    confidence: Literal["confirmed", "inferred", "unknown"] = "inferred"


class ModelPaperExtractionResult(BaseModel):
    """The analyzer output that flows to faculty confirmation before generation."""

    exam_title: str = ""
    duration_minutes: Optional[int] = None
    total_printed_marks: Optional[int] = None
    total_attempted_marks: Optional[int] = None
    groups: list[GroupExtraction] = Field(default_factory=list)
    choices: list[ChoiceDetection] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: Literal["confirmed", "inferred", "unknown"] = "unknown"

    def requires_confirmation(self) -> bool:
        """True when any structural field was only inferred (never invented)."""
        for g in self.groups:
            if g.group_evidence.confidence == "inferred":
                return True
        for c in self.choices:
            if c.confidence == "inferred":
                return True
        return bool(self.warnings)

    def to_main_config(self, selected_units: list[int],
                       duration_minutes: int = 90) -> MainPaperConfig:
        """Build a MainPaperConfig after faculty confirms the extraction.

        Only confirmed/acceptable choices are materialised into explicit
        ChoiceGroups; nothing is fabricated.
        """
        groups = []
        choices = []
        for g in self.groups:
            parts = [p.model_copy(deep=True) for p in g.parts]
            groups.append(QuestionGroup(
                group_number=g.group_number, parts=parts))
        for c in self.choices:
            members = []
            for key in c.member_keys:
                found = _find_part_key(self.groups, key)
                if found is None:
                    continue
                member_obj, marks, unit, topic = found
                members.append(ChoiceMember(
                    key=key, marks=marks, unit=unit, topic=topic,
                    bloom_level=member_obj.bloom_level,
                ))
            if len(members) >= 2:
                choices.append(ChoiceGroup(
                    id=c.choice_id, choice_type=_infer_choice(c),
                    select_count=c.select_count, members=members))
        return MainPaperConfig(
            total_marks=self.total_attempted_marks or sum(
                p.marks for g in groups for p in g.parts),
            duration_minutes=duration_minutes,
            selected_units=selected_units, source_mode="model",
            groups=groups, choice_groups=choices,
        )


def _find_part_key(groups: list[GroupExtraction], key: str):
    """Locate a part (e.g. '2a') or whole group (e.g. '2') among extracted samples."""
    import re as _re
    m = _re.fullmatch(r"(\d+)([a-z])?", key)
    if not m:
        return None
    num = int(m.group(1)); sub = m.group(2) or ""
    for g in groups:
        if g.group_number != num:
            continue
        if not sub:
            # group-level key: use first part's marks/unit/topic
            p = g.parts[0]
            return (p, p.marks, p.unit, p.topic)
        for p in g.parts:
            if (p.part_label or "").lower() == sub.lower():
                return (p, p.marks, p.unit, p.topic)
    return None


def _infer_choice(c: ChoiceDetection) -> Literal["group", "part", "multi"]:
    if len(c.member_keys) == 2:
        if c.member_keys[0].isdigit() and c.member_keys[1].isdigit():
            return "group"
        return "part"
    return "multi"