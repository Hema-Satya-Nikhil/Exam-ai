"""PHASE 3/4 regression tests: OCR-backed ingestion + scoped duplicate rules.

Proves the fixes:
* a pip-only OCR engine (RapidOCR) serves when Tesseract is absent;
* an IMAGE upload flows through OCR into real unit/topic extraction;
* duplicate-topic detection is section-scoped and avoidability-aware;
* only ERROR-severity blueprint issues block generation.
"""
from __future__ import annotations

import asyncio
from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from app.schemas.academic import QuestionRequirement
from app.services.validation_service import ValidationService


def _png_syllabus_bytes() -> bytes:
    """Render a readable 'UNIT - I..II' page to PNG (no external fixture file)."""
    lines = [
        "UNIT - I",
        "Introduction to Operating Systems",
        "- Definition of operating system",
        "- Functions of operating system",
        "UNIT - II",
        "Process Management",
        "- Process concept",
        "- Process scheduling",
    ]
    image = Image.new("RGB", (900, 420), "white")
    draw = ImageDraw.Draw(image)
    y = 20
    for line in lines:
        draw.text((40, y), line, fill="black")
        y += 42
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# OCR-backed ingestion (PHASE 3)
# ---------------------------------------------------------------------------


def test_ocr_provider_is_available_in_this_environment() -> None:
    from app.services.ocr_service import default_ocr_provider

    assert default_ocr_provider().is_available() is True


def test_image_extraction_produces_units_via_ocr() -> None:
    """JPG/JPEG/PNG must flow through OCR into the syllabus parser."""
    from app.services.document_ingestion_service import DocumentIngestionService
    from app.services.syllabus_service import SyllabusService

    data = _png_syllabus_bytes()
    extracted = DocumentIngestionService().extract("syllabus.png", "image/png", data, 50_000_000)
    assert extracted.ocr_used is True
    assert "UNIT" in extracted.text.upper()

    parsed = SyllabusService().parse_text(extracted.text, "syllabus.png")
    assert len(parsed.units) >= 2
    assert 1 in [unit.unit_number for unit in parsed.units]
    assert all(unit.topics or unit.title for unit in parsed.units)
    assert parsed.confidence != "unknown"


def test_bullet_hyphen_is_stripped_from_topics() -> None:
    from app.services.syllabus_service import SyllabusService

    text = "UNIT - I\nProcess Management\n- Process concept\n- Process scheduling"
    parsed = SyllabusService().parse_text(text, "s.txt")
    assert len(parsed.units) == 1
    assert [topic.topic_name for topic in parsed.units[0].topics] == [
        "Process concept",
        "Process scheduling",
    ]


def test_corrupt_image_is_rejected_not_ocr_garbled() -> None:
    from app.services.document_ingestion_service import DocumentIngestionService

    with pytest.raises(ValueError):
        DocumentIngestionService().extract("broken.png", "image/png", b"not-an-image", 50_000_000)


# ---------------------------------------------------------------------------
# Section-scoped duplicate rules (PHASE 4)
# ---------------------------------------------------------------------------


def _question(number: int, section: str, topic: str, unit: int = 1) -> QuestionRequirement:
    return QuestionRequirement(
        question_number=number,
        section=section,
        marks=2,
        unit=unit,
        topic=topic,
        bloom_level="L2",
        difficulty="easy",
        question_type="conceptual",
    )


def test_same_topic_across_sections_is_allowed() -> None:
    """A 2-mark recall and a 10-mark analysis may share a topic."""
    questions = [
        _question(1, "Section A", "Deadlock characterization"),
        _question(2, "Section B", "Deadlock characterization"),
    ]
    result = ValidationService().detect_duplicate_questions(questions)
    assert result.passed is True


def test_avoidable_repeat_inside_section_is_an_error() -> None:
    questions = [
        _question(1, "Section A", "Process concept"),
        _question(2, "Section A", "Process scheduling"),
        _question(3, "Section A", "Process concept"),  # distinct topic available
    ]
    result = ValidationService().detect_duplicate_questions(questions)
    assert result.passed is False
    assert any(issue.severity == "error" for issue in result.issues)


def test_exhausted_topic_pool_warns_instead_of_blocking() -> None:
    """Thin syllabus (1 topic/unit): reuse is unavoidable -> warning only."""
    questions = [
        _question(1, "Section A", "Operating system basics"),
        _question(2, "Section A", "Operating system basics"),
        _question(3, "Section B", "Operating system basics"),
    ]
    result = ValidationService().detect_duplicate_questions(questions)
    assert "topic_pool_exhausted" in {issue.code for issue in result.issues}
    assert all(issue.severity == "warning" for issue in result.issues)


def test_blueprint_passes_when_only_warnings_remain() -> None:
    """Warnings inform; they must not make a legitimate paper ungeneratable."""
    from app.schemas.academic import PaperBlueprint

    blueprint = PaperBlueprint(
        exam_type="MID 1",
        subject="OPERATING SYSTEM",
        selected_units=[1],
        total_marks=4,
        duration_minutes=60,
        sections=[],
        questions=[
            _question(1, "Section A", "Operating system basics"),
            _question(2, "Section A", "Operating system basics"),
        ],
        source_mode="manual",
    )
    summary = ValidationService().validate_blueprint(blueprint)
    assert summary.passed is True
    assert any(issue.code == "topic_pool_exhausted" for issue in summary.issues)


# ---------------------------------------------------------------------------
# Generation surfaces the real blocking rules (PHASE 4)
# ---------------------------------------------------------------------------


def test_invalid_blueprint_error_names_the_failing_rules() -> None:
    """The 400 detail must name the failing rules, not just 'validation failed'."""
    from app.schemas.academic import PaperBlueprint
    from app.schemas.generation import GenerationJobCreate
    from app.services.generation_service import GenerationService

    blueprint = PaperBlueprint(
        exam_type="MID 1",
        subject="OPERATING SYSTEM",
        selected_units=[1],
        total_marks=50,  # wrong on purpose: questions sum to 6
        duration_minutes=120,
        sections=[
            {
                "name": "Section A",
                "section_type": "short_answer",
                "question_count": 3,
                "marks_per_question": 2,
                "instructions": "Answer all.",
            }
        ],
        questions=[
            QuestionRequirement(
                question_number=n,
                section="Section A",
                marks=2,
                unit=1,
                topic=f"Unit 1 topic {n}" if n > 1 else "Unit 1",
                bloom_level="L2",
                difficulty="easy",
                question_type="conceptual",
            )
            for n in (1, 2, 3)
        ],
        source_mode="manual",
    )

    with pytest.raises(ValueError) as excinfo:
        asyncio.run(
            GenerationService().generate_paper_from_blueprint(
                GenerationJobCreate(blueprint=blueprint)
            )
        )

    message = str(excinfo.value)
    assert "Blueprint validation failed before generation." in message
    # The exact rule(s) are named — no more opaque rejections.
    assert "total_marks_mismatch" in message
