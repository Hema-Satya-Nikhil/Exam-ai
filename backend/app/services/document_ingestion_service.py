from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import fitz
from docx import Document

from app.services.ocr_service import OcrProvider, default_ocr_provider
from app.validators.file_validation import validate_upload_file


@dataclass(slots=True)
class ExtractionResult:
    text: str
    page_references: list[str]
    warnings: list[str]
    ocr_used: bool = False


class DocumentIngestionService:
    """Extract plain text from syllabus/uploads.

    Supports PDF, DOCX and image (JPG/JPEG/PNG) inputs. PDFs are read as text
    first; when the text is insufficient (scanned page) we fall back to OCR.
    Images always go through OCR. When OCR is unavailable we surface a clear,
    low-confidence warning rather than fabricating content.
    """

    def __init__(self, ocr_provider: OcrProvider | None = None) -> None:
        self.ocr = ocr_provider or default_ocr_provider()

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
        if suffix in {".jpg", ".jpeg", ".png"}:
            return self._extract_image(data)
        raise ValueError("Unsupported file extension.")

    # ------------------------------------------------------------------
    # PDF: text first, OCR fallback for scanned pages
    # ------------------------------------------------------------------

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
            if self.ocr.is_available():
                return self._ocr_pdf(data, warnings)
            return ExtractionResult(text="", page_references=[], warnings=warnings, ocr_used=False)

        return ExtractionResult(text="\n".join(texts), page_references=page_references, warnings=warnings)

    def _ocr_pdf(self, data: bytes, warnings: list[str]) -> ExtractionResult:
        """Render each PDF page to a raster and OCR it (used for scanned PDFs)."""
        page_references: list[str] = []
        ocr_texts: list[str] = []
        try:
            with fitz.open(stream=data, filetype="pdf") as document:
                for index in range(document.page_count):
                    page = document.load_page(index)
                    pix = page.get_pixmap(dpi=200)
                    result = self.ocr.image_to_text(pix.tobytes("png"))
                    if result.text.strip():
                        ocr_texts.append(result.text.strip())
                        page_references.append(f"page-{index + 1}")
                    warnings.extend(result.warnings)
        except Exception as exc:  # pragma: no cover - defensive wrapper
            raise ValueError("Unable to OCR the uploaded PDF.") from exc
        if not ocr_texts:
            warnings.append("OCR could not read the scanned PDF; please upload a clearer document.")
        return ExtractionResult(text="\n".join(ocr_texts), page_references=page_references, warnings=warnings, ocr_used=bool(ocr_texts))

    # ------------------------------------------------------------------
    # DOCX / TXT
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Images (JPG/JPEG/PNG): decode + validate, then OCR
    # ------------------------------------------------------------------

    def _extract_image(self, data: bytes) -> ExtractionResult:
        from PIL import Image, UnidentifiedImageError

        try:
            with Image.open(BytesIO(data)) as image:
                image.load()
        except UnidentifiedImageError as exc:
            raise ValueError("The uploaded image is not a valid, readable image.") from exc
        except Exception as exc:  # pragma: no cover - defensive wrapper
            raise ValueError("The uploaded image could not be read.") from exc

        warnings: list[str] = []
        if not self.ocr.is_available():
            warnings.append(
                "OCR engine is not available in this environment; the syllabus structure "
                "could not be read from the image. Please upload a text-based PDF/DOCX or "
                "add the units manually."
            )
            return ExtractionResult(text="", page_references=["image"], warnings=warnings, ocr_used=False)

        result = self.ocr.image_to_text(data)
        warnings.extend(result.warnings)
        if not result.text.strip():
            warnings.append("OCR could not read the image; the text may be unclear.")
        return ExtractionResult(
            text=result.text,
            page_references=["image"],
            warnings=warnings,
            ocr_used=bool(result.text.strip()),
        )
