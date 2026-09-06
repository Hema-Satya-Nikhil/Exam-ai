"""Regression tests for atomic topic parsing and question-text sanitization.

Covers Task 2 / Task 7 of the atomic-topics work:
  - comma-separated atomic topic extraction
  - colon topic headers (group heading is NOT a topic)
  - final-period handling
  - PDF/OCR line wrapping (trailing comma joins, standalone ':' line)
  - unit heading variants (UNIT II / UNIT - II / UNIT- III / lowercase)
  - unit title must not swallow the first colon-header group
  - metadata-prefix sanitization of model output
"""
from __future__ import annotations

import pytest

from app.services.question_text_sanitizer import sanitize_question_text
from app.services.syllabus_service import SyllabusService

OS_SYLLABUS = """UNIT II
Processes: Process Concept, Process scheduling, Operations on processes, Inter-process communication.
Threads and Concurrency: Multithreading models, Thread libraries, Threading issues.
CPU Scheduling: Basic concepts, Scheduling criteria, Scheduling algorithms, Multiple processor scheduling."""


def _topics(text: str, file_name: str = "syllabus.pdf") -> list[str]:
    result = SyllabusService().parse_text(text, file_name)
    return [t.topic_name for u in result.units for t in u.topics]


def test_atomic_comma_separated_extraction() -> None:
    topics = _topics(OS_SYLLABUS)
    for expected in (
        "Process Concept",
        "Process scheduling",
        "Operations on processes",
        "Inter-process communication",
        "Multithreading models",
        "Scheduling criteria",
    ):
        assert expected in topics


def test_colon_header_is_not_a_topic() -> None:
    topics = _topics(OS_SYLLABUS)
    # The group heading must never become a question topic (it would yield
    # vague questions like "Explain operating systems").
    assert "Processes" not in topics
    assert "Threads and Concurrency" not in topics
    assert "CPU Scheduling" not in topics


def test_final_period_stripped() -> None:
    topics = _topics("UNIT I\nIntro: Processes, Threads.")
    assert topics == ["Processes", "Threads"]


def test_line_wrapping_joins_trailing_comma() -> None:
    text = "UNIT II\nProcesses: Process Concept, Process scheduling,\nOperations on processes."
    assert _topics(text) == [
        "Process Concept",
        "Process scheduling",
        "Operations on processes",
    ]


def test_wrapped_standalone_colon_line() -> None:
    text = "UNIT II\nThreads and Concurrency\n: Multithreading models, Thread libraries."
    topics = _topics(text)
    assert "Multithreading models" in topics
    assert ": Multithreading models" not in topics  # no leading-colon residue


def test_unit_heading_variants() -> None:
    for marker in ("UNIT II", "UNIT - II", "UNIT-II", "unit 2", "Unit - two"):
        result = SyllabusService().parse_text(f"{marker}\nIntro: Paging, Segmentation.", "s.pdf")
        assert result.units and result.units[0].unit_number == 2, marker


def test_unit_title_does_not_swallow_first_topic_group() -> None:
    result = SyllabusService().parse_text(OS_SYLLABUS, "s.pdf")
    unit2 = next(u for u in result.units if u.unit_number == 2)
    names = [t.topic_name for t in unit2.topics]
    assert "Process Concept" in names  # first group must not be eaten as title


def test_real_unit_title_still_captured() -> None:
    result = SyllabusService().parse_text(
        "UNIT- III\nMemory Management\nPaging: Page table, TLB.", "s.pdf"
    )
    unit3 = result.units[0]
    assert unit3.title == "Memory Management"
    assert [t.topic_name for t in unit3.topics] == ["Page table", "TLB"]


def test_no_combined_pseudo_topic() -> None:
    topics = _topics(OS_SYLLABUS)
    joined = "Process scheduling, Operations on processes, Inter-process communication"
    assert joined not in topics  # the original bug: comma list as ONE topic


# ---------------------------------------------------------------------------
# Question-text sanitization (metadata prefix stripping)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "16. (5 marks) Section C - Unit 2 - Topic: Scheduling criteria (L5) Analyze scheduling algorithms.",
            "Analyze scheduling algorithms.",
        ),
        ("Question 16: Compare Round Robin and Priority Scheduling.", "Compare Round Robin and Priority Scheduling."),
        ("(10 marks) Explain demand paging.", "Explain demand paging."),
        ("Unit 2 - Differentiate paging and segmentation.", "Differentiate paging and segmentation."),
        # Meaningful content must never be stripped.
        ("Compare Round Robin and Priority Scheduling on fairness.", "Compare Round Robin and Priority Scheduling on fairness."),
        ("In Unit 2, students studied scheduling.", "In Unit 2, students studied scheduling."),
    ],
)
def test_sanitize_question_text(raw: str, expected: str) -> None:
    assert sanitize_question_text(raw) == expected
