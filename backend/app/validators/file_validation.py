from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class FileValidationResult:
    allowed: bool
    message: str = ""


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}


def validate_upload_file(file_name: str, mime_type: str, size_bytes: int, max_size: int) -> FileValidationResult:
    suffix = Path(file_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return FileValidationResult(False, "Unsupported file extension.")
    if mime_type not in ALLOWED_MIME_TYPES:
        return FileValidationResult(False, "Unsupported file type.")
    if size_bytes <= 0:
        return FileValidationResult(False, "Uploaded file is empty.")
    if size_bytes > max_size:
        return FileValidationResult(False, "Uploaded file exceeds the allowed size.")
    return FileValidationResult(True, "")
