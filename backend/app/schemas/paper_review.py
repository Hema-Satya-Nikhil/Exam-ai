from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class PaperQuestionRegenerateRequest(BaseModel):
    question_number: int
    instructions: Optional[str] = None
