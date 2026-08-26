from app.schemas.academic import PaperBlueprint, PaperSectionSpec, QuestionRequirement
from app.services.validation_service import ValidationService


def test_validation_service_returns_payload_shape() -> None:
    blueprint = PaperBlueprint(
        exam_type="Mid 1",
        subject="Data Mining",
        selected_units=[1, 2],
        total_marks=10,
        duration_minutes=60,
        sections=[PaperSectionSpec(name="Part A", section_type="short_answer", question_count=2, marks_per_question=5)],
        questions=[
            QuestionRequirement(
                question_number=1,
                section="Part A",
                marks=5,
                unit=1,
                topic="Clustering",
                bloom_level="L2",
                difficulty="medium",
                question_type="conceptual",
            ),
            QuestionRequirement(
                question_number=2,
                section="Part A",
                marks=5,
                unit=2,
                topic="Classification",
                bloom_level="L3",
                difficulty="medium",
                question_type="application",
            ),
        ],
        source_mode="manual",
    )

    result = ValidationService().validate_blueprint(blueprint)

    payload = result.model_dump()
    assert set(payload) == {"passed", "issues"}
