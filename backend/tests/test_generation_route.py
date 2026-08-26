import pytest

from app.core.config import settings
from app.schemas.academic import QuestionRequirement
from app.schemas.generation import QuestionGenerationRequest
from app.services.generation_service import GenerationService


@pytest.mark.asyncio
async def test_generation_service_rejects_unconfigured_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Explicitly simulate an unconfigured NVIDIA provider (key = None / missing).
    monkeypatch.setattr(settings, "nvidia_api_key", "")
    service = GenerationService()
    request = QuestionGenerationRequest(
        requirement=QuestionRequirement(
            question_number=1,
            section="Part A",
            marks=2,
            unit=1,
            topic="Clustering",
            bloom_level="L2",
            difficulty="easy",
            question_type="conceptual",
        ),
        source_context="Unit 1 notes",
    )

    with pytest.raises(ValueError, match="NVIDIA_API_KEY is not configured"):
        await service.generate_single_question(request.requirement, request.source_context)
