"""Unit tests for the deterministic export filename helper (Issue 2)."""
import pytest

from app.services.documents.filenames import build_export_filename


@pytest.mark.parametrize(
    ("subject", "fmt", "expected"),
    [
        ("Operating Systems", "pdf", "OperatingSystems_Exam_ai.pdf"),
        ("Operating Systems", "docx", "OperatingSystems_Exam_ai.docx"),
        ("Data Warehousing and Data Mining", "pdf", "DataWarehousingandDataMining_Exam_ai.pdf"),
        ("Data Warehousing and Data Mining", "docx", "DataWarehousingandDataMining_Exam_ai.docx"),
        # punctuation removed, readable capitalization preserved
        ("Operating-Systems / Mid 1", "pdf", "OperatingSystemsMid1_Exam_ai.pdf"),
        ("DBMS (R23): Unit-3", "docx", "DBMSR23Unit3_Exam_ai.docx"),
        # very long subject stays deterministic and filesystem-safe
        (
            "A Very Long Subject Name That Keeps Going And Going For Many Words",
            "pdf",
            "AVeryLongSubjectNameThatKeepsGoingAndGoingForManyWords_Exam_ai.pdf",
        ),
    ],
)
def test_build_export_filename_expected_shapes(subject, fmt, expected):
    assert build_export_filename(subject, fmt) == expected


@pytest.mark.parametrize(
    "subject",
    ["Operating Systems", "Data Warehousing and Data Mining", "Machine Learning"],
)
@pytest.mark.parametrize("fmt", ["pdf", "docx"])
def test_build_export_filename_deterministic_and_safe(subject, fmt):
    first = build_export_filename(subject, fmt)
    second = build_export_filename(subject, fmt)
    assert first == second  # deterministic
    assert first.endswith(f"_Exam_ai.{fmt}")
    assert " " not in first
    assert all(ch.isalnum() or ch in "_.-" for ch in first)


@pytest.mark.parametrize("bad", [None, "", "   ", "!!!", "***"])
def test_build_export_filename_fallback(bad):
    name = build_export_filename(bad, "pdf")
    assert name == "Exam_Exam_ai.pdf"
