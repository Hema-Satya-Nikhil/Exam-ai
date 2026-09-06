import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user, get_db
from app.api.routes.papers import router
from app.schemas.academic import GeneratedQuestionRead
from app.schemas.auth import UserContext
from app.schemas.paper_review import PaperQuestionRegenerateRequest
from app.schemas.paper_workflow import PaperDraftCreate, PaperLockRequest, PaperQuestionUpdate
from app.services.composite_review import (
    refresh_flattened_views,
    resolve_composite_question,
)
from app.services.generation_service import GenerationService
from app.services.paper_workflow_service import PaperWorkflowService


def composite_paper_json() -> dict:
    part_a = [
        {
            "question_number": i,
            "section": "Part A",
            "marks": 2,
            "unit": 1 if i % 2 else 2,
            "topic": f"Short topic {i}",
            "bloom_level": "L2",
            "difficulty": "easy",
            "question_type": "short_answer",
            "exam_part": "short_answer",
            "group_number": None,
            "part_label": None,
            "choice_group_id": None,
            "choice_member_id": None,
            "locked": False,
            "question_text": f"Short answer {i}",
            "source_references": [{"ref": f"A{i}"}],
        }
        for i in range(1, 3)
    ]
    paper_json = {
        "title": "Composite draft",
        "status": "under_review",
        "parts": {
            "part_a": {
                "name": "PART A - SHORT ANSWER",
                "total_marks": 4,
                "duration_minutes": 20,
                "questions": part_a,
            },
            "part_b": {
                "name": "PART B - MAIN PAPER",
                "total_marks": 20,
                "duration_minutes": 90,
                "groups": [
                    {
                        "group_number": 5,
                        "choice_group": "cg-56",
                        "parts": [
                            {
                                "question_number": 51,
                                "marks": 10,
                                "unit": 3,
                                "topic": "Deadlock",
                                "bloom_level": "L4",
                                "difficulty": "hard",
                                "question_type": "analytical",
                                "exam_part": "main",
                                "group_number": 5,
                                "part_label": "a",
                                "choice_group_id": "cg-56",
                                "choice_member_id": "m5a",
                                "locked": False,
                                "question_text": "Explain deadlock avoidance.",
                                "source_references": [{"ref": "B5a"}],
                            },
                            {
                                "question_number": 52,
                                "marks": 10,
                                "unit": 3,
                                "topic": "Scheduling",
                                "bloom_level": "L4",
                                "difficulty": "hard",
                                "question_type": "analytical",
                                "exam_part": "main",
                                "group_number": 5,
                                "part_label": "b",
                                "choice_group_id": "cg-56",
                                "choice_member_id": "m5b",
                                "locked": False,
                                "question_text": "Explain priority scheduling.",
                                "source_references": [{"ref": "B5b"}],
                            },
                        ],
                    },
                    {
                        "group_number": 6,
                        "choice_group": "cg-56",
                        "parts": [
                            {
                                "question_number": 61,
                                "marks": 10,
                                "unit": 4,
                                "topic": "Paging",
                                "bloom_level": "L3",
                                "difficulty": "medium",
                                "question_type": "analytical",
                                "exam_part": "main",
                                "group_number": 6,
                                "part_label": "a",
                                "choice_group_id": "cg-56",
                                "choice_member_id": "m6a",
                                "locked": False,
                                "question_text": "Explain paging hardware.",
                                "source_references": [{"ref": "B6a"}],
                            },
                            {
                                "question_number": 62,
                                "marks": 10,
                                "unit": 4,
                                "topic": "Virtual memory",
                                "bloom_level": "L3",
                                "difficulty": "medium",
                                "question_type": "analytical",
                                "exam_part": "main",
                                "group_number": 6,
                                "part_label": "b",
                                "choice_group_id": "cg-56",
                                "choice_member_id": "m6b",
                                "locked": False,
                                "question_text": "Explain demand paging.",
                                "source_references": [{"ref": "B6b"}],
                            },
                        ],
                    },
                ],
            },
        },
        "locked_question_numbers": [],
        "locked_question_keys": [],
    }
    refresh_flattened_views(paper_json)
    return paper_json


def legacy_paper_json() -> dict:
    return {
        "questions": [
            {
                "question_number": 1,
                "section": "Part A",
                "marks": 2,
                "unit": 1,
                "topic": "Clustering",
                "bloom_level": "L2",
                "difficulty": "easy",
                "question_type": "conceptual",
                "question_text": "Define clustering.",
                "source_references": [{"ref": "legacy"}],
                "locked": False,
            }
        ]
    }


def make_workflow_with_composite_draft() -> tuple[PaperWorkflowService, str]:
    workflow = PaperWorkflowService()
    draft = workflow.create_draft(
        PaperDraftCreate(title="Composite Draft", paper_json=composite_paper_json())
    )
    return workflow, draft.id


def make_regenerated_text(requirement, source_context: str) -> str:
    return (
        f"Regenerated {requirement.topic} [{requirement.question_number}] "
        f":: {requirement.generation_instruction or 'no extra instruction'} "
        f":: {source_context}"
    )


@pytest.fixture
def fake_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_generate_single_question(self, requirement, source_context):
        return GeneratedQuestionRead(
            question_number=requirement.question_number,
            section=requirement.section,
            marks=requirement.marks,
            unit=requirement.unit,
            topic=requirement.topic,
            bloom_level=requirement.bloom_level,
            difficulty=requirement.difficulty,
            question_type=requirement.question_type,
            choice_group=requirement.choice_group,
            generation_instruction=requirement.generation_instruction,
            question_text=make_regenerated_text(requirement, source_context),
            source_references=[{"ref": "new"}],
            locked=False,
        )

    monkeypatch.setattr(GenerationService, "generate_single_question", fake_generate_single_question)


def test_resolve_part_a_question() -> None:
    resolved = resolve_composite_question(
        composite_paper_json(), "short_answer", question_number=1
    )
    assert resolved is not None
    assert resolved.key == "short_answer:q1"
    assert resolved.question["question_text"] == "Short answer 1"


def test_resolve_part_b_question() -> None:
    resolved = resolve_composite_question(
        composite_paper_json(), "main", group_number=5, part_label="b"
    )
    assert resolved is not None
    assert resolved.key == "main:g5:b"
    assert resolved.question["question_text"] == "Explain priority scheduling."


def test_resolve_or_alternative() -> None:
    resolved = resolve_composite_question(
        composite_paper_json(), "main", group_number=6, part_label="a"
    )
    assert resolved is not None
    assert resolved.question["choice_group_id"] == "cg-56"
    assert resolved.question["choice_member_id"] == "m6a"


@pytest.mark.asyncio
async def test_regenerate_part_a(fake_generation) -> None:
    workflow, draft_id = make_workflow_with_composite_draft()
    updated = await workflow.regenerate_question(
        draft_id,
        PaperQuestionRegenerateRequest(
            exam_part="short_answer",
            question_number=2,
            instructions="Make it more analytical.",
        ),
    )
    assert updated is not None
    question = updated.paper_json["parts"]["part_a"]["questions"][1]
    assert "Make it more analytical." in question["question_text"]
    assert question["source_references"] == [{"ref": "A2"}]


@pytest.mark.asyncio
async def test_regenerate_part_b(fake_generation) -> None:
    workflow, draft_id = make_workflow_with_composite_draft()
    updated = await workflow.regenerate_question(
        draft_id,
        PaperQuestionRegenerateRequest(
            exam_part="main",
            group_number=5,
            part_label="b",
            instructions="Emphasize trade-offs.",
        ),
    )
    assert updated is not None
    question = resolve_composite_question(updated, "main", group_number=5, part_label="b")
    assert question is not None
    assert "Emphasize trade-offs." in question.question["question_text"]
    assert question.question["choice_group_id"] == "cg-56"
    assert question.question["choice_member_id"] == "m5b"


@pytest.mark.asyncio
async def test_regenerate_or_alternative_only_changes_target(fake_generation) -> None:
    workflow, draft_id = make_workflow_with_composite_draft()
    before = composite_paper_json()
    updated = await workflow.regenerate_question(
        draft_id,
        PaperQuestionRegenerateRequest(
            exam_part="main",
            group_number=5,
            part_label="a",
            instructions="Use a numerical example.",
        ),
    )
    assert updated is not None
    after_target = resolve_composite_question(updated, "main", group_number=5, part_label="a")
    after_sibling = resolve_composite_question(updated, "main", group_number=5, part_label="b")
    untouched_other_group = resolve_composite_question(updated, "main", group_number=6, part_label="a")
    assert after_target is not None and after_sibling is not None and untouched_other_group is not None
    assert "Use a numerical example." in after_target.question["question_text"]
    assert after_sibling.question["question_text"] == before["parts"]["part_b"]["groups"][0]["parts"][1]["question_text"]
    assert untouched_other_group.question["question_text"] == before["parts"]["part_b"]["groups"][1]["parts"][0]["question_text"]
    assert after_target.question["choice_group_id"] == "cg-56"
    assert after_target.question["choice_member_id"] == "m5a"


@pytest.mark.asyncio
async def test_locked_composite_question_rejects_regeneration(fake_generation) -> None:
    workflow, draft_id = make_workflow_with_composite_draft()
    workflow.lock_question(
        draft_id, PaperLockRequest(exam_part="main", group_number=5, part_label="a")
    )
    with pytest.raises(ValueError, match="Locked questions cannot be regenerated"):
        await workflow.regenerate_question(
            draft_id,
            PaperQuestionRegenerateRequest(exam_part="main", group_number=5, part_label="a"),
        )


def test_lock_existing_composite_question() -> None:
    workflow, draft_id = make_workflow_with_composite_draft()
    locked = workflow.lock_question(
        draft_id, PaperLockRequest(exam_part="main", group_number=5, part_label="a")
    )
    assert locked is not None
    target = resolve_composite_question(locked, "main", group_number=5, part_label="a")
    assert target is not None and target.question["locked"] is True
    assert "main:g5:a" in locked.locked_question_keys
    assert 51 in locked.locked_question_numbers


def test_lock_missing_composite_question_returns_none() -> None:
    workflow, draft_id = make_workflow_with_composite_draft()
    assert (
        workflow.lock_question(
            draft_id, PaperLockRequest(exam_part="main", group_number=9, part_label="a")
        )
        is None
    )


def test_unlock_composite_question() -> None:
    workflow, draft_id = make_workflow_with_composite_draft()
    workflow.lock_question(
        draft_id, PaperLockRequest(exam_part="main", group_number=5, part_label="a")
    )
    unlocked = workflow.unlock_question(
        draft_id, PaperLockRequest(exam_part="main", group_number=5, part_label="a")
    )
    assert unlocked is not None
    target = resolve_composite_question(unlocked, "main", group_number=5, part_label="a")
    assert target is not None and target.question["locked"] is False
    assert "main:g5:a" not in unlocked.locked_question_keys


def test_synchronize_flattened_compatibility_view() -> None:
    workflow, draft_id = make_workflow_with_composite_draft()
    updated = workflow.update_question(
        draft_id,
        PaperQuestionUpdate.model_validate(
            {
                "exam_part": "main",
                "group_number": 6,
                "part_label": "b",
                "question_text": "Explain demand paging with a diagram.",
            }
        ),
    )
    assert updated is not None
    flat = next(q for q in updated.paper_json["questions"] if q["question_number"] == 62)
    section_flat = next(
        q
        for section in updated.paper_json["sections"]
        for q in section["questions"]
        if q["question_number"] == 62
    )
    assert flat["question_text"] == "Explain demand paging with a diagram."
    # Issue 3: compat view question_text is pure wording; the renderer owns
    # numbering/labels, so no "Q6b." prefix is injected into the text.
    assert section_flat["question_text"] == "Explain demand paging with a diagram."


@pytest.mark.asyncio
async def test_legacy_flat_paper_regeneration_still_works(fake_generation) -> None:
    workflow = PaperWorkflowService()
    draft = workflow.create_draft(
        PaperDraftCreate(title="Legacy Draft", paper_json=legacy_paper_json())
    )
    updated = await workflow.regenerate_question(
        draft.id,
        PaperQuestionRegenerateRequest(question_number=1, instructions="Make it tougher."),
    )
    assert updated is not None
    assert "Make it tougher." in updated.paper_json["questions"][0]["question_text"]


def test_unknown_composite_key_returns_404() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/papers")

    async def override_user():
        return UserContext(
            user_id="faculty-1",
            email="faculty@example.edu",
            full_name="Faculty",
            roles=["faculty"],
            is_active=True,
        )

    async def override_db():
        yield None

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    async def fake_regenerate(self, paper_id, payload):
        return None

    original = PaperWorkflowService.regenerate_question
    PaperWorkflowService.regenerate_question = fake_regenerate
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/papers/drafts/paper-1/regenerate",
                json={"exam_part": "main", "group_number": 9, "part_label": "a"},
            )
    finally:
        PaperWorkflowService.regenerate_question = original

    assert response.status_code == 404


def test_lock_missing_composite_question_returns_404() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/papers")

    async def override_user():
        return UserContext(
            user_id="faculty-1",
            email="faculty@example.edu",
            full_name="Faculty",
            roles=["faculty"],
            is_active=True,
        )

    async def override_db():
        yield None

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    def fake_lock(self, paper_id, payload):
        return None

    original = PaperWorkflowService.lock_question
    PaperWorkflowService.lock_question = fake_lock
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/papers/drafts/paper-1/lock",
                json={"exam_part": "main", "group_number": 9, "part_label": "a"},
            )
    finally:
        PaperWorkflowService.lock_question = original

    assert response.status_code == 404
