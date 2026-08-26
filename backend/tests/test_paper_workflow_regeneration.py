import pytest

from app.schemas.academic import GeneratedQuestionRead
from app.schemas.paper_review import PaperQuestionRegenerateRequest
from app.schemas.paper_workflow import PaperDraftCreate, PaperLockRequest
from app.services.generation_service import GenerationService
from app.services.paper_workflow_service import PaperWorkflowService


@pytest.mark.asyncio
async def test_regenerate_question_updates_the_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    workflow = PaperWorkflowService()
    draft = workflow.create_draft(
        PaperDraftCreate(
            title="Mid 1",
            paper_json={
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
                    }
                ]
            },
        )
    )

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
            question_text="Regenerated clustering question.",
            source_references=[],
            locked=False,
        )

    monkeypatch.setattr(GenerationService, "generate_single_question", fake_generate_single_question)

    updated = await workflow.regenerate_question(draft.id, PaperQuestionRegenerateRequest(question_number=1, instructions="Make it more analytical."))

    assert updated is not None
    assert updated.paper_json["questions"][0]["question_text"] == "Regenerated clustering question."
    assert updated.status == "under_review"


@pytest.mark.asyncio
async def test_regenerate_question_rejects_locked_question(monkeypatch: pytest.MonkeyPatch) -> None:
    workflow = PaperWorkflowService()
    draft = workflow.create_draft(
        PaperDraftCreate(
            title="Mid 1",
            paper_json={
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
                    }
                ]
            },
        )
    )
    workflow.lock_question(draft.id, PaperLockRequest(question_number=1))

    with pytest.raises(ValueError, match="Locked questions cannot be regenerated"):
        await workflow.regenerate_question(draft.id, PaperQuestionRegenerateRequest(question_number=1))
