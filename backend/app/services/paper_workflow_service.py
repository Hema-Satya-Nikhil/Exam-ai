from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.paper_workflow_repository import PaperWorkflowRepository
from app.schemas.academic import QuestionRequirement
from app.schemas.paper_review import PaperQuestionRegenerateRequest
from app.schemas.paper_workflow import (
    PaperApprovalRead,
    PaperDraftCreate,
    PaperDraftRead,
    PaperLockRequest,
    PaperQuestionUpdate,
)


@dataclass
class PaperWorkflowStore:
    papers: dict[str, PaperDraftRead] = field(default_factory=dict)
    approvals: dict[str, PaperApprovalRead] = field(default_factory=dict)


class PaperWorkflowService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self.store = PaperWorkflowStore()
        self.repo = PaperWorkflowRepository(session) if session else None

    def create_draft(self, payload: PaperDraftCreate) -> PaperDraftRead:
        paper_id = str(uuid4())
        paper = PaperDraftRead(
            id=paper_id,
            title=payload.title,
            status="draft",
            locked_question_numbers=[],
            paper_json=payload.paper_json,
            validation_passed=False,
        )
        self.store.papers[paper.id] = paper
        return paper

    async def create_draft_async(self, payload: PaperDraftCreate) -> PaperDraftRead:
        paper = self.create_draft(payload)
        if self.repo:
            await self.repo.update_paper_version_json(paper.id, paper.paper_json)
            await self.repo.log_action("create_draft", "paper", paper.id, {"title": paper.title})
        return paper

    def get_draft(self, paper_id: str) -> PaperDraftRead | None:
        return self.store.papers.get(paper_id)

    async def get_draft_async(self, paper_id: str) -> PaperDraftRead | None:
        if paper_id in self.store.papers:
            return self.store.papers[paper_id]

        if self.repo:
            db_paper = await self.repo.get_paper(paper_id)
            if db_paper:
                latest_version = await self.repo.get_latest_version(paper_id)
                paper_json = latest_version.paper_json if latest_version else {}
                draft = PaperDraftRead(
                    id=db_paper.id,
                    title=db_paper.title,
                    status=db_paper.status,
                    locked_question_numbers=paper_json.get("locked_question_numbers", []),
                    paper_json=paper_json,
                    validation_passed=paper_json.get("validation", {}).get("passed", False),
                )
                self.store.papers[draft.id] = draft
                return draft

        return None

    def update_question(self, paper_id: str, payload: PaperQuestionUpdate) -> PaperDraftRead | None:
        paper = self.get_draft(paper_id)
        if paper is None:
            return None

        questions = paper.paper_json.setdefault("questions", [])
        for question in questions:
            if int(question.get("question_number", -1)) != payload.question_number:
                continue
            if payload.question_text is not None:
                question["question_text"] = payload.question_text
            if payload.unit is not None:
                question["unit"] = payload.unit
            if payload.topic is not None:
                question["topic"] = payload.topic
            if payload.bloom_level is not None:
                question["bloom_level"] = payload.bloom_level
            if payload.difficulty is not None:
                question["difficulty"] = payload.difficulty
            if payload.question_type is not None:
                question["question_type"] = payload.question_type
            break
        return paper

    async def update_question_async(self, paper_id: str, payload: PaperQuestionUpdate) -> PaperDraftRead | None:
        paper = await self.get_draft_async(paper_id)
        if paper is None:
            return None
        updated = self.update_question(paper_id, payload)
        if updated and self.repo:
            await self.repo.update_paper_version_json(paper_id, updated.paper_json)
            await self.repo.log_action("update_question", "paper", paper_id, {"question_number": payload.question_number})
        return updated

    def lock_question(self, paper_id: str, payload: PaperLockRequest) -> PaperDraftRead | None:
        paper = self.get_draft(paper_id)
        if paper is None:
            return None
        if payload.question_number not in paper.locked_question_numbers:
            paper.locked_question_numbers.append(payload.question_number)
        paper.paper_json["locked_question_numbers"] = paper.locked_question_numbers
        for question in paper.paper_json.get("questions", []):
            if int(question.get("question_number", -1)) == payload.question_number:
                question["locked"] = True
        return paper

    async def lock_question_async(self, paper_id: str, payload: PaperLockRequest) -> PaperDraftRead | None:
        paper = await self.get_draft_async(paper_id)
        if paper is None:
            return None
        locked = self.lock_question(paper_id, payload)
        if locked and self.repo:
            await self.repo.update_paper_version_json(paper_id, locked.paper_json)
            await self.repo.log_action("lock_question", "paper", paper_id, {"question_number": payload.question_number})
        return locked

    def approve_paper(
        self, paper_id: str, approved_by: str, comments: str | None = None
    ) -> PaperApprovalRead | None:
        paper = self.get_draft(paper_id)
        if paper is None:
            return None
        paper.status = "approved"
        paper.paper_json["status"] = "approved"
        approval = PaperApprovalRead(
            paper_id=paper_id, approved_by=approved_by, comments=comments
        )
        self.store.approvals[paper_id] = approval
        return approval

    async def approve_paper_async(
        self, paper_id: str, approved_by: str, comments: str | None = None
    ) -> PaperApprovalRead | None:
        paper = await self.get_draft_async(paper_id)
        if paper is None:
            return None
        approval = self.approve_paper(paper_id, approved_by, comments)
        if approval and self.repo:
            await self.repo.update_paper_status(paper_id, "approved")
            await self.repo.log_action(
                "approve_paper",
                "paper",
                paper_id,
                {"approved_by": approved_by, "comments": comments},
            )
        return approval

    def mark_exported(self, paper_id: str) -> PaperDraftRead | None:
        paper = self.get_draft(paper_id)
        if paper is None:
            return None
        paper.status = "exported"
        paper.paper_json["status"] = "exported"
        return paper

    async def mark_exported_async(self, paper_id: str) -> PaperDraftRead | None:
        paper = await self.get_draft_async(paper_id)
        if paper is None:
            return None
        exported = self.mark_exported(paper_id)
        if exported and self.repo:
            await self.repo.update_paper_status(paper_id, "exported")
            await self.repo.log_action("mark_exported", "paper", paper_id)
        return exported

    async def regenerate_question(self, paper_id: str, payload: PaperQuestionRegenerateRequest) -> PaperDraftRead | None:
        paper = await self.get_draft_async(paper_id) if self.repo else self.get_draft(paper_id)
        if paper is None:
            return None
        if payload.question_number in paper.locked_question_numbers:
            raise ValueError("Locked questions cannot be regenerated.")

        questions = paper.paper_json.get("questions", [])
        target_question = next((q for q in questions if int(q.get("question_number", -1)) == payload.question_number), None)
        if target_question is None:
            return None

        requirement = QuestionRequirement(
            question_number=int(target_question.get("question_number", payload.question_number)),
            section=str(target_question.get("section", "")),
            marks=int(target_question.get("marks", 0)),
            unit=int(target_question.get("unit", 0)),
            topic=str(target_question.get("topic", "")),
            bloom_level=str(target_question.get("bloom_level", "L2")),
            difficulty=str(target_question.get("difficulty", "medium")),
            question_type=str(target_question.get("question_type", "conceptual")),
            choice_group=target_question.get("choice_group"),
            generation_instruction=payload.instructions,
        )

        from app.services.generation_service import GenerationService

        generated = await GenerationService().generate_single_question(
            requirement,
            f"Regenerate question {payload.question_number}. Instructions: {payload.instructions or 'None'}.",
        )
        target_question.update(generated.model_dump())
        paper.status = "under_review"
        paper.paper_json["status"] = "under_review"

        if self.repo:
            await self.repo.update_paper_version_json(paper_id, paper.paper_json)
            await self.repo.log_action("regenerate_question", "paper", paper_id, {"question_number": payload.question_number})

        return paper
