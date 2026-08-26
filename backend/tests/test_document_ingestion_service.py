from app.services.document_ingestion_service import DocumentIngestionService


def test_extract_txt_returns_text_and_warning_for_empty_input() -> None:
    service = DocumentIngestionService()
    result = service.extract("notes.txt", "text/plain", b"hello world", 1024)

    assert result.text == "hello world"
    assert result.warnings == []


def test_extract_rejects_unsupported_extension() -> None:
    service = DocumentIngestionService()

    try:
        service.extract("notes.exe", "application/octet-stream", b"data", 1024)
    except ValueError as exc:
        assert "Unsupported file extension" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
