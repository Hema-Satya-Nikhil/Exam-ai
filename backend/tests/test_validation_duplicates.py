from app.schemas.academic import QuestionRequirement
from app.services.validation_service import ValidationService


def test_detect_duplicate_questions_flags_similar_topics() -> None:
    questions = [
        QuestionRequirement(
            question_number=1,
            section="Part A",
            marks=5,
            unit=1,
            topic="K-Means Clustering",
            bloom_level="L2",
            difficulty="medium",
            question_type="conceptual",
        ),
        QuestionRequirement(
            question_number=2,
            section="Part A",
            marks=5,
            unit=1,
            topic="K Means Clustering",
            bloom_level="L3",
            difficulty="medium",
            question_type="application",
        ),
    ]

    result = ValidationService().detect_duplicate_questions(questions)

    assert result.passed is False
    assert any(issue.code in {"exact_duplicate_topic", "near_duplicate_topic"} for issue in result.issues)
