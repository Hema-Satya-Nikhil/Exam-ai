from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field
from app.schemas.paper_review import CompositeQuestionTarget
from pydantic import BaseModel

from app.schemas.academic import GeneratedQuestionRead


class PaperDraftCreate(BaseModel):
    title: str
    paper_json: dict


class PaperDraftRead(BaseModel):
    id: str
    title: str
    status: Literal["draft", "under_review", "approved", "exported"]
    locked_question_numbers: list[int] = Field(default_factory=list)
    locked_question_keys: list[str] = Field(default_factory=list)
    paper_json: dict
    validation_passed: bool = False


class PaperQuestionUpdate(CompositeQuestionTarget):
    question_text: Optional[str] = None
    unit: Optional[int] = None
    topic: Optional[str] = None
    bloom_level: Optional[str] = None
    difficulty: Optional[str] = None
    question_type: Optional[str] = None


class PaperLockRequest(CompositeQuestionTarget):
    pass


class PaperApprovalRequest(BaseModel):
    """Approval request. The approving user is derived from the authenticated
    session (``current_user.id``), never from the client payload."""

    comments: Optional[str] = None


class PaperApprovalRead(BaseModel):
    paper_id: str
    approved_by: str
    comments: Optional[str] = None
    status: Literal["approved"] = "approved"
