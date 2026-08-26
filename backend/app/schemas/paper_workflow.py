from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.academic import GeneratedQuestionRead


class PaperDraftCreate(BaseModel):
    title: str
    paper_json: dict


class PaperDraftRead(BaseModel):
    id: str
    title: str
    status: Literal["draft", "under_review", "approved", "exported"]
    locked_question_numbers: list[int] = Field(default_factory=list)
    paper_json: dict
    validation_passed: bool = False


class PaperQuestionUpdate(BaseModel):
    question_number: int
    question_text: Optional[str] = None
    unit: Optional[int] = None
    topic: Optional[str] = None
    bloom_level: Optional[str] = None
    difficulty: Optional[str] = None
    question_type: Optional[str] = None


class PaperLockRequest(BaseModel):
    question_number: int


class PaperApprovalRequest(BaseModel):
    """Approval request. The approving user is derived from the authenticated
    session (``current_user.id``), never from the client payload."""

    comments: Optional[str] = None


class PaperApprovalRead(BaseModel):
    paper_id: str
    approved_by: str
    comments: Optional[str] = None
    status: Literal["approved"] = "approved"
