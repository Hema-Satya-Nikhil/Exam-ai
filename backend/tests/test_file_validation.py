from app.validators.file_validation import validate_upload_file


def test_validate_upload_file_accepts_pdf() -> None:
    result = validate_upload_file("syllabus.pdf", "application/pdf", 1024, 2048)
    assert result.allowed is True


def test_validate_upload_file_rejects_empty_file() -> None:
    result = validate_upload_file("syllabus.pdf", "application/pdf", 0, 2048)
    assert result.allowed is False
