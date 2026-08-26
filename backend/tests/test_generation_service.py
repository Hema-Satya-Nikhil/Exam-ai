import pytest

from app.schemas.academic import PaperBlueprint
from app.services.generation_service import GenerationService


@pytest.mark.asyncio
async def test_generation_service_returns_validation_summary() -> None:
    blueprint = PaperBlueprint(
        exam_type="Mid 1",
        subject="Data Mining",
        selected_units=[1, 2],
        total_marks=0,
        duration_minutes=60,
        sections=[],
        questions=[],
        source_mode="manual",
    )

    result = await GenerationService().generate_question_set(blueprint)

    assert result.passed is False
