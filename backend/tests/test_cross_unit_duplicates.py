from app.schemas.academic import PaperBlueprint, PaperSectionSpec, QuestionRequirement
from app.services.validation_service import ValidationService


def _q(number: int, unit: int, topic: str, section: str = "Part A") -> QuestionRequirement:
    return QuestionRequirement(
        question_number=number,
        section=section,
        marks=5,
        unit=unit,
        topic=topic,
        bloom_level="L2",
        difficulty="medium",
        question_type="conceptual",
    )


def _blueprint(questions: list[QuestionRequirement], units: list[int] | None = None) -> PaperBlueprint:
    return PaperBlueprint(
        exam_type="Mid 1",
        subject="OS",
        selected_units=units or [1, 2, 3],
        total_marks=sum(q.marks for q in questions),
        duration_minutes=60,
        sections=[PaperSectionSpec(name="Part A", section_type="short_answer", question_count=len(questions), marks_per_question=5)],
        questions=questions,
        source_mode="manual",
    )


def _codes(result) -> set[str]:
    return {issue.code for issue in result.issues}


def test_same_topic_in_different_units_is_valid() -> None:
    # "Process Scheduling" may legitimately appear in both Unit 1 and Unit 2.
    blueprint = _blueprint([
        _q(1, unit=1, topic="Process Scheduling"),
        _q(2, unit=2, topic="Process Scheduling"),
    ])
    result = ValidationService().validate_blueprint(blueprint)
    assert result.passed is True
    assert "exact_duplicate_topic" not in _codes(result)
    assert "near_duplicate_topic" not in _codes(result)


def test_same_topic_twice_in_same_unit_with_alternatives_is_error() -> None:
    # Unit 2 says: Process Scheduling, Threads. Repeating Process Scheduling on
    # unit 2 while Threads goes unused must be flagged.
    blueprint = _blueprint([
        _q(1, unit=2, topic="Process Scheduling"),
        _q(2, unit=2, topic="Threads"),
        _q(3, unit=2, topic="Process Scheduling"),
    ])
    result = ValidationService().validate_blueprint(blueprint)
    assert result.passed is False
    assert "exact_duplicate_topic" in _codes(result)


def test_topic_reuse_in_same_unit_after_pool_exhaustion_is_warning() -> None:
    # Unit 2 lists only a single topic. Reuse it -> warning only, not blocking.
    blueprint = _blueprint([
        _q(1, unit=2, topic="Scheduling"),
        _q(2, unit=2, topic="Scheduling"),
    ])
    result = ValidationService().validate_blueprint(blueprint)
    assert any(issue.code == "topic_pool_exhausted" for issue in result.issues)
    assert all(issue.severity == "warning" for issue in result.issues)
    assert result.passed is True
def test_case_and_whitespace_normalization_within_unit() -> None:
    # Same unit, same topic differing only by case / whitespace -> error when
    # another distinct topic remains available.
    blueprint = _blueprint([
        _q(1, unit=1, topic="Process Scheduling"),
        _q(2, unit=1, topic="Deadlocks"),
        _q(3, unit=1, topic="  process   scheduling "),  # normalized dup of q1
    ])
    result = ValidationService().validate_blueprint(blueprint)
    assert result.passed is False
    assert "exact_duplicate_topic" in _codes(result)


def test_multi_unit_topic_allocation_is_scoped_per_unit() -> None:
    # Unit 1 topics: A, B ; Unit 2 topics: A, C
    # Valid allocation: Unit 1 -> A, B ; Unit 2 -> A, C  must PASS.
    blueprint = _blueprint([
        _q(1, unit=1, topic="A"),
        _q(2, unit=1, topic="B"),
        _q(3, unit=2, topic="A"),
        _q(4, unit=2, topic="C"),
    ])
    result = ValidationService().validate_blueprint(blueprint)
    assert result.passed is True
    assert "exact_duplicate_topic" not in _codes(result)


def test_exact_duplicate_topic_still_catches_same_unit_malformed_dup() -> None:
    blueprint = _blueprint([
        _q(1, unit=1, topic="Deadlocks"),
        _q(2, unit=1, topic="Processes"),
        _q(3, unit=1, topic="Deadlocks"),
    ])
    result = ValidationService().validate_blueprint(blueprint)
    assert result.passed is False
    assert "exact_duplicate_topic" in _codes(result)


def test_operating_systems_syllabus_regression() -> None:
    blueprint = _blueprint([
        _q(1, unit=1, topic="Process Concept"),
        _q(2, unit=1, topic="Process Scheduling"),
        _q(3, unit=2, topic="Process Scheduling"),  # legit cross-unit
        _q(4, unit=2, topic="Threads"),
    ])
    result = ValidationService().validate_blueprint(blueprint)
    assert result.passed is True
    assert "exact_duplicate_topic" not in _codes(result)


def test_composite_exam_config_regression() -> None:
    qs = [
        _q(1, unit=1, topic="Process", section="Section A"),
        _q(2, unit=1, topic="Threads", section="Section A"),
        _q(3, unit=2, topic="Process", section="Section B"),
        _q(4, unit=2, topic="Scheduling", section="Section B"),
    ]
    blueprint = PaperBlueprint(
        exam_type="Mid 1",
        subject="OS",
        selected_units=[1, 2],
        total_marks=sum(q.marks for q in qs),
        duration_minutes=110,
        sections=[
            PaperSectionSpec(name="Section A", section_type="short_answer", question_count=2, marks_per_question=5),
            PaperSectionSpec(name="Section B", section_type="descriptive", question_count=2, marks_per_question=5),
        ],
        questions=qs,
        source_mode="manual",
    )
    result = ValidationService().validate_blueprint(blueprint)
    assert result.passed is True
    assert "exact_duplicate_topic" not in _codes(result)


def test_legacy_flat_blueprint_regression() -> None:
    varied = _blueprint([
        _q(1, unit=1, topic="A"), _q(2, unit=1, topic="B"), _q(3, unit=1, topic="C"),
    ], units=[1])
    assert ValidationService().validate_blueprint(varied).passed is True

    repeated = _blueprint([
        _q(1, unit=1, topic="A"), _q(2, unit=1, topic="B"), _q(3, unit=1, topic="A"),
    ], units=[1])
    assert "exact_duplicate_topic" in _codes(ValidationService().validate_blueprint(repeated))