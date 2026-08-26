import pytest

from app.core.config import settings
from app.schemas.academic import PaperBlueprint, PaperSectionSpec, QuestionRequirement
from app.schemas.generation import GenerationJobCreate
from app.services.generation_service import GenerationService


@pytest.mark.asyncio
async def test_batch_generation_rejects_unconfigured_provider_after_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Explicitly simulate an unconfigured NVIDIA provider (key missing/empty).
    monkeypatch.setattr(settings, "nvidia_api_key", "")
    blueprint = PaperBlueprint(
        exam_type="Mid 1",
        subject="Data Mining",
        selected_units=[1, 2],
        total_marks=10,
        duration_minutes=60,
        sections=[PaperSectionSpec(name="Part A", section_type="short_answer", question_count=1, marks_per_question=10)],
        questions=[
            QuestionRequirement(
                question_number=1,
                section="Part A",
                marks=10,
                unit=1,
                topic="Clustering",
                bloom_level="L2",
                difficulty="easy",
                question_type="conceptual",
            )
        ],
        source_mode="manual",
    )

    service = GenerationService()

    with pytest.raises(ValueError, match="NVIDIA_API_KEY is not configured"):
        await service.generate_paper_from_blueprint(GenerationJobCreate(blueprint=blueprint))
