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
from app.services.composite_review import (
    rebuild_locked_question_keys,
    refresh_flattened_views,
    resolve_composite_question,
    resolve_legacy_question,
    sync_locked_question_state,
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
        self.actor_id: str | None = None

    def create_draft(self, payload: PaperDraftCreate) -> PaperDraftRead:
        paper_id = str(uuid4())
        paper = PaperDraftRead(
            id=paper_id,
            title=payload.title,
            status="draft",
            locked_question_numbers=[],
            locked_question_keys=[],
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
            if self.session:
                await self.session.commit()
        return paper

    def get_draft(self, paper_id: str) -> PaperDraftRead | None:
        draft = self.store.papers.get(paper_id)
        if draft is not None:
            return draft

        fallback = self._generation_store_draft(paper_id)
        if fallback is not None:
            self.store.papers[paper_id] = fallback
            return fallback

        # Restart survival: background-completed jobs persist Paper +
        # PaperVersion rows in PostgreSQL. Rebuild the draft from those rows
        # when no in-memory copy exists (e.g. after a backend restart) so the
        # Review workflow keeps working. Safe here because this sync path runs
        # in a worker thread; the async variant uses get_draft_async.
        import asyncio as _asyncio

        try:
            _asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            return None

        async def _rebuild() -> None:
            from app.db.session import async_session_maker as _maker

            repo = PaperWorkflowRepository(_maker())
            db_paper = await repo.get_paper(paper_id)
            if db_paper is None:
                return
            latest = await repo.get_latest_version(paper_id)
            paper_json = latest.paper_json if latest else {}
            rebuilt = PaperDraftRead(
                id=db_paper.id,
                title=db_paper.title,
                status=db_paper.status,
                locked_question_numbers=paper_json.get("locked_question_numbers", []),
                locked_question_keys=paper_json.get("locked_question_keys", []),
                paper_json=paper_json,
                validation_passed=paper_json.get("validation", {}).get("passed", False),
            )
            self.store.papers[rebuilt.id] = rebuilt

        _asyncio.run(_rebuild())
        return self.store.papers.get(paper_id)

    def _generation_store_draft(self, paper_id: str) -> PaperDraftRead | None:
        """Fall back to the in-process GenerationService draft store.

        The generation flow stores drafts in its own PaperWorkflowService
        instance (see ``app.api.routes.generation``), while the paper review/export
        routes use a separate instance. Without this fallback a freshly generated
        draft (stored in the generation service) is invisible to GET /drafts/{id},
        PATCH question, lock, regenerate, approve and export -> 404 / "not approved".
        """
        try:
            from app.api.routes.generation import generation_service
            return generation_service.paper_workflow.store.papers.get(paper_id)
        except Exception:
            return None

    async def get_draft_async(self, paper_id: str) -> PaperDraftRead | None:
        if paper_id in self.store.papers:
            return self.store.papers[paper_id]

        fallback = self._generation_store_draft(paper_id)
        if fallback is not None:
            self.store.papers[paper_id] = fallback
            return fallback

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
                    locked_question_keys=paper_json.get("locked_question_keys", []),
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

        target_question = self._resolve_question(paper, payload)
        if target_question is None:
            return None

        if payload.question_text is not None:
            target_question["question_text"] = payload.question_text
        if payload.unit is not None:
            target_question["unit"] = payload.unit
        if payload.topic is not None:
            target_question["topic"] = payload.topic
        if payload.bloom_level is not None:
            target_question["bloom_level"] = payload.bloom_level
        if payload.difficulty is not None:
            target_question["difficulty"] = payload.difficulty
        if payload.question_type is not None:
            target_question["question_type"] = payload.question_type

        refresh_flattened_views(paper.paper_json)
        return paper

    async def update_question_async(self, paper_id: str, payload: PaperQuestionUpdate, actor_id: str | None = None) -> PaperDraftRead | None:
        paper = await self.get_draft_async(paper_id)
        if paper is None:
            return None
        updated = self.update_question(paper_id, payload)
        if updated and self.repo:
            await self.repo.update_paper_version_json(paper_id, updated.paper_json)
            await self.repo.log_action("update_question", "paper", paper_id, {"question_number": payload.question_number}, actor_id=actor_id or self.actor_id)
            if self.session:
                await self.session.commit()
        return updated

    def lock_question(self, paper_id: str, payload: PaperLockRequest) -> PaperDraftRead | None:
        paper = self.get_draft(paper_id)
        if paper is None:
            return None
        resolved = self._resolve_question_ref(paper, payload)
        if resolved is None:
            return None
        resolved.question["locked"] = True
        sync_locked_question_state(paper.paper_json, resolved, locked=True)
        refresh_flattened_views(paper.paper_json)
        paper.locked_question_numbers = list(paper.paper_json.get("locked_question_numbers", []))
        paper.locked_question_keys = list(paper.paper_json.get("locked_question_keys", []))
        return paper

    async def lock_question_async(self, paper_id: str, payload: PaperLockRequest, actor_id: str | None = None) -> PaperDraftRead | None:
        paper = await self.get_draft_async(paper_id)
        if paper is None:
            return None
        locked = self.lock_question(paper_id, payload)
        if locked and self.repo:
            await self.repo.update_paper_version_json(paper_id, locked.paper_json)
            await self.repo.log_action(
                "lock_question",
                "paper",
                paper_id,
                {
                    "question_number": payload.question_number,
                    "exam_part": payload.exam_part,
                    "group_number": payload.group_number,
                    "part_label": payload.part_label,
                }, actor_id=actor_id or self.actor_id,
            )
            if self.session:
                await self.session.commit()
        return locked

    def unlock_question(self, paper_id: str, payload: PaperLockRequest) -> PaperDraftRead | None:
        paper = self.get_draft(paper_id)
        if paper is None:
            return None
        resolved = self._resolve_question_ref(paper, payload)
        if resolved is None:
            return None
        resolved.question["locked"] = False
        sync_locked_question_state(paper.paper_json, resolved, locked=False)
        refresh_flattened_views(paper.paper_json)
        paper.locked_question_numbers = list(paper.paper_json.get("locked_question_numbers", []))
        paper.locked_question_keys = list(paper.paper_json.get("locked_question_keys", []))
        return paper

    async def unlock_question_async(self, paper_id: str, payload: PaperLockRequest, actor_id: str | None = None) -> PaperDraftRead | None:
        paper = await self.get_draft_async(paper_id)
        if paper is None:
            return None
        unlocked = self.unlock_question(paper_id, payload)
        if unlocked and self.repo:
            await self.repo.update_paper_version_json(paper_id, unlocked.paper_json)
            await self.repo.log_action(
                "unlock_question",
                "paper",
                paper_id,
                {
                    "question_number": payload.question_number,
                    "exam_part": payload.exam_part,
                    "group_number": payload.group_number,
                    "part_label": payload.part_label,
                }, actor_id=actor_id or self.actor_id,
            )
            if self.session:
                await self.session.commit()
        return unlocked

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
            if self.session:
                await self.session.commit()
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
            if self.session:
                await self.session.commit()
        return exported

    async def regenerate_question(self, paper_id: str, payload: PaperQuestionRegenerateRequest, actor_id: str | None = None) -> PaperDraftRead | None:
        paper = await self.get_draft_async(paper_id) if self.repo else self.get_draft(paper_id)
        if paper is None:
            return None
        resolved = self._resolve_question_ref(paper, payload)
        if resolved is None:
            return None
        target_question = resolved.question
        if bool(target_question.get("locked")):
            raise ValueError("Locked questions cannot be regenerated.")

        requirement = QuestionRequirement(
            question_number=int(target_question.get("question_number", payload.question_number or 0)),
            section=str(target_question.get("section", "")),
            marks=int(target_question.get("marks", 0)),
            unit=int(target_question.get("unit", 0)),
            topic=str(target_question.get("topic", "")),
            bloom_level=str(target_question.get("bloom_level", "L2")),
            difficulty=str(target_question.get("difficulty", "medium")),
            question_type=str(target_question.get("question_type", "conceptual")),
            choice_group=target_question.get("choice_group") or target_question.get("choice_group_id"),
            generation_instruction=payload.instructions,
        )

        from app.services.generation_service import GenerationService

        generated = await GenerationService().generate_single_question(
            requirement,
            f"Regenerate question {resolved.key}. Instructions: {payload.instructions or 'None'}. "
            f"Keep marks ({requirement.marks}), unit ({requirement.unit}), topic ('{requirement.topic}'), "
            f"Bloom level ({requirement.bloom_level}), difficulty ({requirement.difficulty}) and "
            f"question type ({requirement.question_type}) unchanged.",
        )
        # Composite-exam metadata must survive regeneration untouched.
        preserved = {
            key: target_question[key]
            for key in ("exam_part", "group_number", "part_label",
                        "choice_group_id", "choice_member_id", "locked", "source_references")
            if key in target_question
        }
        target_question.update(generated.model_dump())
        target_question.update(preserved)
        refresh_flattened_views(paper.paper_json)
        paper.locked_question_numbers = list(paper.paper_json.get("locked_question_numbers", []))
        paper.locked_question_keys = rebuild_locked_question_keys(paper.paper_json)
        paper.status = "under_review"
        paper.paper_json["status"] = "under_review"

        if self.repo:
            await self.repo.update_paper_version_json(paper_id, paper.paper_json)
            await self.repo.log_action(
                "regenerate_question",
                "paper",
                paper_id,
                {
                    "question_number": target_question.get("question_number"),
                    "exam_part": target_question.get("exam_part"),
                    "group_number": target_question.get("group_number"),
                    "part_label": target_question.get("part_label"),
                }, actor_id=actor_id or self.actor_id,
            )
            if self.session:
                await self.session.commit()

        return paper

    def _resolve_question(self, paper: PaperDraftRead, payload: PaperQuestionUpdate | PaperLockRequest | PaperQuestionRegenerateRequest) -> dict | None:
        resolved = self._resolve_question_ref(paper, payload)
        return resolved.question if resolved else None

    def _resolve_question_ref(self, paper: PaperDraftRead, payload: PaperQuestionUpdate | PaperLockRequest | PaperQuestionRegenerateRequest):
        if paper.paper_json.get("parts"):
            resolved = resolve_composite_question(
                paper,
                payload.exam_part,
                payload.question_number,
                payload.group_number,
                payload.part_label,
            )
            if resolved is not None:
                return resolved
            if payload.exam_part is not None:
                return None
        return resolve_legacy_question(paper, payload.question_number)
