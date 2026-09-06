"""Regression tests for the additive institutional exam-structure layer.

Covers the two-part examination model (Part A short-answer + Part B main paper
with explicit ChoiceGroup/OR relationships) and the printed-vs-attempted marks
model, plus the Mid 1 / Mid 2 selected_units variants. Purely additive - it
does not depend on or modify the existing flat PaperBlueprint pipeline.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.exam_structure import (
    ChoiceGroup,
    ChoiceMember,
    ExamConfig,
    MainPaperConfig,
    QuestionGroup,
    QuestionPart,
    ShortAnswerPaperConfig,
)
from app.services.exam_structure_service import compute_exam_marks, part_b_marks


def part(n: int, unit: int = 2, bloom: str = "L3", marks: int = 5) -> QuestionPart:
    return QuestionPart(
        question_number=n, part_label=None, marks=marks, unit=unit,
        topic=f"topic{n}", bloom_level=bloom,
    )


def default_part_a(units=None) -> ShortAnswerPaperConfig:
    return ShortAnswerPaperConfig(
        question_count=10, marks_per_question=2, total_marks=20,
        duration_minutes=20, selected_units=units or [1, 2],
    )


def part_b(groups, choices=None, units=None) -> MainPaperConfig:
    return MainPaperConfig(
        total_marks=30, duration_minutes=90, selected_units=units or [2],
        source_mode="model", groups=groups, choice_groups=choices or [],
    )


def _exhib_exam() -> ExamConfig:
    groups = [
        QuestionGroup(group_number=1, parts=[
            QuestionPart(question_number=1, part_label="a", marks=5, unit=2,
                         topic="t1a", bloom_level="L3"),
            QuestionPart(question_number=1, part_label="b", marks=5, unit=2,
                         topic="t1b", bloom_level="L3"),
        ]),
        QuestionGroup(group_number=2, parts=[part(2, 2)]),
        QuestionGroup(group_number=3, parts=[part(3, 2)]),
        QuestionGroup(group_number=4, parts=[part(4, 2)], choice_group="cg1"),
        QuestionGroup(group_number=5, parts=[part(5, 2)], choice_group="cg1"),
        QuestionGroup(group_number=6, parts=[part(6, 2)], choice_group="cg2"),
        QuestionGroup(group_number=7, parts=[part(7, 2)], choice_group="cg2"),
    ]
    choices = [
        ChoiceGroup(id="cg1", choice_type="group", select_count=1, members=[
            ChoiceMember(key="4", marks=5, unit=2, topic="t4", bloom_level="L3"),
            ChoiceMember(key="5", marks=5, unit=2, topic="t5", bloom_level="L3"),
        ]),
        ChoiceGroup(id="cg2", choice_type="group", select_count=1, members=[
            ChoiceMember(key="6", marks=5, unit=2, topic="t6", bloom_level="L3"),
            ChoiceMember(key="7", marks=5, unit=2, topic="t7", bloom_level="L3"),
        ]),
    ]
    return ExamConfig(exam_type="MID 1", subject="OS", selected_units=[1, 2],
                      part_a=default_part_a(), part_b=part_b(groups, choices, [1, 2]))


# ---------------------------------------------------------------------------
# Part A invariants
# ---------------------------------------------------------------------------


def test_part_a_separate_2mark_paper():
    cfg = default_part_a()
    assert cfg.question_count == 10
    assert cfg.marks_per_question == 2
    assert cfg.total_marks == 20
    assert cfg.duration_minutes == 20


def test_part_a_rejects_marks_imbalance():
    with pytest.raises(ValidationError):
        ShortAnswerPaperConfig(question_count=10, marks_per_question=2, total_marks=22)


def test_part_a_is_independent_of_part_b():
    cfg = default_part_a()
    assert cfg.total_marks == 20  # never bleeds into Part B
# ---------------------------------------------------------------------------
# Whole-exam invariants
# ---------------------------------------------------------------------------


def test_total_exam_50_marks_110_minutes():
    ex = _exhib_exam()
    assert ex.total_marks == 50
    assert ex.total_duration == 110


def test_group_level_or():
    m = compute_exam_marks(_exhib_exam())
    # printed = 10(Q1a+b)+5(Q2)+5(Q3)+10(cg1)+10(cg2)=40; attempted=30.
    assert m.part_b.printed_available_marks == 40
    assert m.part_b.attempted_required_marks == 30


def test_part_level_or():
    groups = [
        QuestionGroup(group_number=2, parts=[
            QuestionPart(question_number=2, part_label="a", marks=5, unit=2,
                         topic="t2a", bloom_level="L3", choice_member="2a"),
            QuestionPart(question_number=2, part_label="b", marks=5, unit=2,
                         topic="t2b", bloom_level="L3", choice_member="2b"),
        ]),
    ]
    choices = [ChoiceGroup(id="cg_a_b", choice_type="part", select_count=1, members=[
        ChoiceMember(key="2a", marks=5, unit=2, topic="t2a", bloom_level="L3"),
        ChoiceMember(key="2b", marks=5, unit=2, topic="t2b", bloom_level="L3"),
    ])]
    pb = part_b(groups, choices, [2])
    m = part_b_marks(pb)
    assert m.printed_available_marks == 10
    assert m.attempted_required_marks == 5


def test_multiple_alternatives_select_two():
    groups = [
        QuestionGroup(group_number=5, parts=[part(5, 2)], choice_group="m"),
        QuestionGroup(group_number=6, parts=[part(6, 2)], choice_group="m"),
        QuestionGroup(group_number=8, parts=[part(8, 2)], choice_group="m"),
    ]
    choices = [ChoiceGroup(id="m", choice_type="multi", select_count=2, members=[
        ChoiceMember(key="5", marks=5, unit=2, topic="t5", bloom_level="L3"),
        ChoiceMember(key="6", marks=5, unit=2, topic="t6", bloom_level="L3"),
        ChoiceMember(key="8", marks=5, unit=2, topic="t8", bloom_level="L3"),
    ])]
    pb = part_b(groups, choices, [2])
    m = part_b_marks(pb)
    assert m.printed_available_marks == 15
    assert m.attempted_required_marks == 10


def test_mid1_units_1_2():
    ex = _exhib_exam()
    assert ex.selected_units == [1, 2]
    assert ex.part_b.selected_units == [1, 2]


def test_mid2_units_3_4_5():
    cfg = ShortAnswerPaperConfig(question_count=10, marks_per_question=2,
                                 total_marks=20, duration_minutes=20,
                                 selected_units=[3, 4, 5])
    ex = ExamConfig(exam_type="MID 2", subject="OS", selected_units=[3, 4, 5],
                    part_a=cfg, part_b=part_b([], [], [3, 4, 5]))
    assert ex.selected_units == [3, 4, 5]
    assert ex.part_a.selected_units == [3, 4, 5]
    assert ex.part_b.selected_units == [3, 4, 5]


def test_institutional_invariant_smoke():
    ex = _exhib_exam()
    assert ex.total_marks == 50
    assert ex.total_duration == 110
    assert compute_exam_marks(ex).attempted_required_total == 50