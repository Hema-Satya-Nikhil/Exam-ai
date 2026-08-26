from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class FileValidationResult:
    allowed: bool
    message: str = ""


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".jpg", ".jpeg", ".png"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "image/jpeg",
    "image/png",
}

# Maps each allowed extension to the set of MIME types that are consistent with
# it. Used to reject invalid extension/MIME combinations (e.g. a .png named .pdf).
_EXT_MIME_MAP = {
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".txt": {"text/plain"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
}


def validate_upload_file(file_name: str, mime_type: str, size_bytes: int, max_size: int) -> FileValidationResult:
    suffix = Path(file_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return FileValidationResult(False, "Unsupported file extension.")
    if mime_type not in ALLOWED_MIME_TYPES:
        return FileValidationResult(False, "Unsupported file type.")
    # Extension/MIME must be mutually consistent — prevents disguising one type
    # as another (e.g. an executable or a renamed document).
    if mime_type not in _EXT_MIME_MAP[suffix]:
        return FileValidationResult(False, "File extension does not match its content type.")
    if size_bytes <= 0:
        return FileValidationResult(False, "Uploaded file is empty.")
    if size_bytes > max_size:
        return FileValidationResult(False, "Uploaded file exceeds the allowed size.")
    return FileValidationResult(True, "")
