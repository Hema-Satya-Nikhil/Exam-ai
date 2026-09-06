"""Syllabus ingestion pipeline tests.

Covers PDF / DOCX / JPG / JPEG / PNG extraction, Roman-numeral unit heading
detection, topic extraction, low-confidence (uncertain) extraction, faculty
confirmation persistence, manual correction, and file validation (invalid
image / unsupported type / oversized). OCR is faked via a stub provider so the
tests are deterministic and do not require a Tesseract binary.
"""
from __future__ import annotations

import io

import pytest
import pytest_asyncio
from docx import Document
from PIL import Image
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

from app.db.base import Base
from app.models.academic import Subject, Syllabus, SyllabusUnit
from app.services.document_ingestion_service import DocumentIngestionService
from app.services.ocr_service import OcrResult, OcrProvider
from app.services.syllabus_service import SyllabusService, persist_confirmed_syllabus

SQLITE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    SQLITE_URL,
    echo=False,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


class FakeOCR(OcrProvider):
    def __init__(self, text: str, available: bool = True):
        self._text = text
        self._available = available

    def is_available(self) -> bool:
        return self._available

    def image_to_text(self, image_bytes: bytes) -> OcrResult:
        if not self._text.strip():
            return OcrResult(text="", warnings=["OCR returned no readable text; the image may be unclear."])
        return OcrResult(text=self._text)


SYLLABUS_TEXT = """UNIT - I
Introduction to Database Systems
Topic: Overview of DBMS
Topic: Relational model

UNIT - II
SQL and Query Languages
Topic: SELECT, INSERT
Topic: JOIN operations
"""


def make_png(text: str) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(buf, format="PNG")
    return buf.getvalue()


def make_jpg(text: str) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(buf, format="JPEG")
    return buf.getvalue()


def make_docx(text: str) -> bytes:
    doc = Document()
    for line in text.splitlines():
        if line.strip():
            doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_pdf(text: str) -> bytes:
    """Build a real text-PDF with the given lines using reportlab (installed)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    for line in (text or "").splitlines():
        if line.strip():
            story.append(Paragraph(line, styles["BodyText"]))
            story.append(Spacer(1, 4))
    doc.build(story)
    return buf.getvalue()

# ---------------------------------------------------------------------------
# PDF / DOCX extraction
# ---------------------------------------------------------------------------


def test_pdf_text_extraction_detects_units_and_topics():
    svc = DocumentIngestionService(ocr_provider=FakeOCR("unused", available=False))
    result = svc.extract("syllabus.pdf", "application/pdf", make_pdf(SYLLABUS_TEXT), 5_000_000)
    assert result.text.strip()
    parsed = SyllabusService().parse_text(result.text, "syllabus.pdf")
    assert [u.unit_number for u in parsed.units] == [1, 2]
    assert parsed.units[0].title == "Introduction to Database Systems"
    assert [t.topic_name for t in parsed.units[0].topics] == ["Overview of DBMS", "Relational model"]


def test_docx_extraction_detects_units_and_topics():
    svc = DocumentIngestionService(ocr_provider=FakeOCR("unused", available=False))
    result = svc.extract(
        "syllabus.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        make_docx(SYLLABUS_TEXT),
        5_000_000,
    )
    parsed = SyllabusService().parse_text(result.text, "syllabus.docx")
    assert [u.unit_number for u in parsed.units] == [1, 2]
    assert parsed.units[1].title == "SQL and Query Languages"


# ---------------------------------------------------------------------------
# Image extraction (OCR)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "file_name, mime_type, maker",
    [
        ("syllabus.png", "image/png", make_png),
        ("syllabus.jpg", "image/jpeg", make_jpg),
        ("syllabus.jpeg", "image/jpeg", make_jpg),
    ],
)
def test_image_extraction_uses_ocr(file_name, mime_type, maker):
    svc = DocumentIngestionService(ocr_provider=FakeOCR(SYLLABUS_TEXT))
    result = svc.extract(file_name, mime_type, maker("unused"), 5_000_000)
    assert result.ocr_used is True
    parsed = SyllabusService().parse_text(result.text, file_name)
    assert [u.unit_number for u in parsed.units] == [1, 2]
    assert "UNIT" in (parsed.units[0].title or "") or "Introduction" in (parsed.units[0].title or "")


def test_image_ocr_unavailable_returns_uncertain_warning():
    svc = DocumentIngestionService(ocr_provider=FakeOCR("", available=False))
    result = svc.extract("syllabus.png", "image/png", make_png("unused"), 5_000_000)
    assert result.text == ""
    assert result.ocr_used is False
    assert any("OCR" in w for w in result.warnings)


def test_low_confidence_when_no_unit_headings():
    parsed = SyllabusService().parse_text("Some free text with no units at all.", "notes.txt")
    assert parsed.units == []
    assert parsed.confidence == "unknown"
    assert any("couldn't confidently read" in w for w in parsed.warnings)


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------


def test_unsupported_file_type_rejected():
    svc = DocumentIngestionService(ocr_provider=FakeOCR(""))
    with pytest.raises(ValueError, match="Unsupported file extension"):
        svc.extract("malware.exe", "application/octet-stream", b"MZ....", 5_000_000)


def test_extension_mime_mismatch_rejected():
    svc = DocumentIngestionService(ocr_provider=FakeOCR(""))
    with pytest.raises(ValueError, match="does not match"):
        svc.extract("syllabus.png", "image/jpeg", make_png("x"), 5_000_000)


def test_oversized_file_rejected():
    svc = DocumentIngestionService(ocr_provider=FakeOCR(""))
    with pytest.raises(ValueError, match="exceeds the allowed size"):
        svc.extract("syllabus.pdf", "application/pdf", b"x" * 5000, 1000)


def test_invalid_image_rejected():
    svc = DocumentIngestionService(ocr_provider=FakeOCR(""))
    with pytest.raises(ValueError, match="not a valid"):
        svc.extract("syllabus.png", "image/png", b"this is not an image at all", 5_000_000)

# ---------------------------------------------------------------------------
# Faculty confirmation + manual correction (persistence)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def _make_confirm_units(units: list[dict]):
    from app.schemas.academic import TopicRead, UnitRead

    return [
        UnitRead(
            unit_number=u["unit_number"],
            title=u["title"],
            topics=[TopicRead(topic_name=t) for t in u["topics"]],
        )
        for u in units
    ]


async def test_confirm_persists_units_and_topics():
    async with TestSession() as session:
        subject = Subject(code="CS401", name="Database Systems", department="CS")
        session.add(subject)
        await session.flush()

        unit_models = _make_confirm_units(
            [
                {"unit_number": 1, "title": "Intro to DB", "topics": ["Overview of DBMS", "Relational model"]},
                {"unit_number": 2, "title": "SQL", "topics": ["SELECT", "JOIN"]},
            ]
        )
        version_id = await persist_confirmed_syllabus(session, subject.id, "confirmed.pdf", unit_models)

        syn = (await session.execute(select(Syllabus))).scalars().first()
        assert syn is not None
        units_db = (await session.execute(
            select(SyllabusUnit)
            .options(selectinload(SyllabusUnit.topics))
            .where(SyllabusUnit.syllabus_version_id == version_id)
            .order_by(SyllabusUnit.unit_number)
        )).scalars().all()
        assert [u.unit_number for u in units_db] == [1, 2]
        assert units_db[0].title == "Intro to DB"
        assert units_db[0].topics[0].topic_name == "Overview of DBMS"
        assert units_db[0].confidence == "confirmed"


async def test_manual_correction_adds_and_removes_units():
    """Faculty edits titles/topics before confirmation: those edits are what get
    persisted (manual correction is honored over the raw extraction)."""
    async with TestSession() as session:
        subject = Subject(code="CS402", name="Operating Systems", department="CS")
        session.add(subject)
        await session.flush()

        unit_models = _make_confirm_units(
            [
                {"unit_number": 1, "title": "Corrected Title", "topics": ["Corrected Topic A"]},
                {"unit_number": 3, "title": "Added Unit", "topics": ["Fresh Topic"]},
            ]
        )
        version_id = await persist_confirmed_syllabus(session, subject.id, "edited.pdf", unit_models)
        units_db = (await session.execute(
            select(SyllabusUnit)
            .options(selectinload(SyllabusUnit.topics))
            .where(SyllabusUnit.syllabus_version_id == version_id)
            .order_by(SyllabusUnit.unit_number)
        )).scalars().all()
        assert [u.unit_number for u in units_db] == [1, 3]
        assert units_db[0].topics[0].topic_name == "Corrected Topic A"


async def test_confirm_duplicate_unit_numbers_rejected():
    from app.api.routes.syllabi import _validate_no_duplicate_unit_numbers
    from app.schemas.syllabus import SyllabusConfirmUnit

    dupe = [
        SyllabusConfirmUnit(unit_number=1, title="A", topics=["x"]),
        SyllabusConfirmUnit(unit_number=2, title="B", topics=["y"]),
        SyllabusConfirmUnit(unit_number=2, title="C", topics=["z"]),
    ]
    with pytest.raises(HTTPException) as excinfo:
        _validate_no_duplicate_unit_numbers(dupe)
    assert excinfo.value.status_code == 400

    # No exception for unique numbers
    _validate_no_duplicate_unit_numbers(dupe[:2])
