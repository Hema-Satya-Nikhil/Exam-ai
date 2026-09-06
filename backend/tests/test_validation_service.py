from app.schemas.academic import PaperBlueprint, PaperSectionSpec, QuestionRequirement
from app.services.validation_service import ValidationService


def test_validate_blueprint_marks_and_sections() -> None:
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

    assert result.passed is True
    assert result.issues == []


def test_validate_blueprint_rejects_unit_scope_not_crossunit_topic() -> None:
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
                unit=5,
                topic="Clustering",
                bloom_level="L3",
                difficulty="medium",
                question_type="application",
            ),
        ],
        source_mode="manual",
    )

    result = ValidationService().validate_blueprint(blueprint)

    assert result.passed is False
    codes = {issue.code for issue in result.issues}
    # Q2 uses unit 5 which is outside the selected scope -> error.
    assert "unit_out_of_scope" in codes
    # The same topic on *different* units is legitimate — it must NOT be
    # flagged as a duplicate (only the out-of-scope unit is).
    assert "exact_duplicate_topic" not in codes
    assert "near_duplicate_topic" not in codes


def test_validate_blueprint_rejects_non_contiguous_numbering() -> None:
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
                question_number=3,
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

    assert result.passed is False
    assert any(issue.code == "question_number_sequence_error" for issue in result.issues)
