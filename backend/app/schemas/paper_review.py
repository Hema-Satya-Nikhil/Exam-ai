from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, model_validator


class CompositeQuestionTarget(BaseModel):
    exam_part: Optional[Literal["short_answer", "main"]] = None
    question_number: Optional[int] = None
    group_number: Optional[int] = None
    part_label: Optional[str] = None

    @model_validator(mode="after")
    def validate_target(self) -> "CompositeQuestionTarget":
        if self.exam_part == "short_answer" and self.question_number is None:
            raise ValueError("short_answer review actions require question_number")
        if self.exam_part == "main" and (
            self.group_number is None or not (self.part_label or "").strip()
        ):
            raise ValueError("main review actions require group_number and part_label")
        if self.exam_part is None and self.question_number is None:
            raise ValueError("question_number is required for legacy review actions")
        return self


class PaperQuestionRegenerateRequest(CompositeQuestionTarget):
    instructions: Optional[str] = None
