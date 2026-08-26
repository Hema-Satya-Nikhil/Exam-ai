from app.validators.file_validation import validate_upload_file


def test_validate_upload_file_rejects_wrong_extension() -> None:
    result = validate_upload_file("notes.exe", "application/octet-stream", 1024, 2048)
    assert result.allowed is False
