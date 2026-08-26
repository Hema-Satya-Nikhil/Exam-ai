from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import fitz
from docx import Document

from app.validators.file_validation import validate_upload_file


@dataclass(slots=True)
class ExtractionResult:
    text: str
    page_references: list[str]
    warnings: list[str]


class DocumentIngestionService:
    def extract(self, file_name: str, mime_type: str, data: bytes, max_size: int) -> ExtractionResult:
        validation = validate_upload_file(file_name, mime_type, len(data), max_size)
        if not validation.allowed:
            raise ValueError(validation.message)

        suffix = Path(file_name).suffix.lower()
        if suffix == ".pdf":
            return self._extract_pdf(data)
        if suffix == ".docx":
            return self._extract_docx(data)
        if suffix == ".txt":
            return self._extract_txt(data)
        raise ValueError("Unsupported file extension.")

    def _extract_pdf(self, data: bytes) -> ExtractionResult:
        warnings: list[str] = []
        page_references: list[str] = []
        texts: list[str] = []

        try:
            with fitz.open(stream=data, filetype="pdf") as document:
                if document.page_count == 0:
                    warnings.append("The uploaded PDF does not contain any pages.")
                for index in range(document.page_count):
                    page = document.load_page(index)
                    page_text = page.get_text().strip()
                    if page_text:
                        texts.append(page_text)
                        page_references.append(f"page-{index + 1}")
        except Exception as exc:  # pragma: no cover - defensive wrapper
            raise ValueError("Unable to read the uploaded PDF.") from exc

        if not texts:
            warnings.append("No extractable text was found; the PDF may be scanned and require OCR.")
        return ExtractionResult(text="\n".join(texts), page_references=page_references, warnings=warnings)

    def _extract_docx(self, data: bytes) -> ExtractionResult:
        try:
            document = Document(BytesIO(data))
        except Exception as exc:  # pragma: no cover - defensive wrapper
            raise ValueError("Unable to read the uploaded DOCX file.") from exc

        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        if not paragraphs:
            return ExtractionResult(text="", page_references=[], warnings=["The uploaded DOCX did not contain readable text."])
        return ExtractionResult(text="\n".join(paragraphs), page_references=["docx"], warnings=[])

    def _extract_txt(self, data: bytes) -> ExtractionResult:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("utf-16", errors="ignore")
        warnings = [] if text.strip() else ["The uploaded TXT file is empty."]
        return ExtractionResult(text=text, page_references=["txt"], warnings=warnings)
