"""Pluggable OCR engine for scanned/image-based syllabus extraction.

Design goals
------------
* No hard dependency on any single OCR engine at import time. Each provider is
  imported lazily and reports ``is_available()`` so an unavailability is a
  first-class, graceful outcome rather than a crash.
* We deliberately do NOT use NVIDIA or MongoDB for OCR (those integrations are
  out of scope / unchanged per the architecture constraints).
* When no OCR engine is available we *never fabricate content*: we return an
  empty result plus an explanatory warning, and the caller surfaces it as low
  confidence instead of invented units/topics.

Current engine: Tesseract via ``pytesseract`` -- the canonical Python OCR
stack. It requires the ``tesseract`` binary on PATH (or configured). If it is
not present, ``default_ocr_provider()`` still works but reports unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Protocol


@dataclass(slots=True)
class OcrResult:
    text: str
    confidence: float | None = None  # None = unknown / not provided by engine
    warnings: list[str] = field(default_factory=list)


class OcrProvider(Protocol):
    """OCP-style contract every engine must satisfy."""

    def is_available(self) -> bool: ...  # pragma: no cover

    def image_to_text(self, image_bytes: bytes) -> OcrResult: ...  # pragma: no cover


class TesseractOCRProvider:
    """Tesseract-backed OCR via ``pytesseract`` (lazy import).

    ``tesseract_cmd`` may be supplied explicitly (e.g. from config) or left
    auto-discovered from PATH.
    """

    def __init__(self, tesseract_cmd: str | None = None) -> None:
        self._tesseract_cmd = tesseract_cmd

    def is_available(self) -> bool:
        try:
            import pytesseract  # noqa: F401
        except Exception:
            return False
        # Presence of the binary is required, not just the pip wrapper.
        if self._tesseract_cmd:
            from pathlib import Path

            return Path(self._tesseract_cmd).exists()
        return self._binary_available()

    @staticmethod
    def _binary_available() -> bool:
        import shutil

        return shutil.which("tesseract") is not None

    def image_to_text(self, image_bytes: bytes) -> OcrResult:
        from PIL import Image

        import pytesseract

        if self._tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self._tesseract_cmd
        with Image.open(BytesIO(image_bytes)) as image:
            text = pytesseract.image_to_string(image)
        warnings: list[str] = []
        if not text.strip():
            warnings.append("OCR returned no readable text; the image may be unclear.")
        return OcrResult(text=text, confidence=None, warnings=warnings)


class RapidOcrProvider:
    """RapidOCR (ONNX Runtime) — pip-installable OCR, no system binary needed.

    Chosen as the fallback engine because it installs as a pure wheel
    (``rapidocr-onnxruntime``, bundles its ONNX detection/recognition models),
    needs no administrator rights and no external executable, and satisfies the
    same :class:`OcrProvider` contract as Tesseract. Results are returned in
    reading order (top-to-bottom, left-to-right) which is what the line-based
    syllabus parser expects.
    """

    def __init__(self) -> None:
        self._engine: object | None = None

    def _load_engine(self):
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR

            self._engine = RapidOCR()
        return self._engine

    def is_available(self) -> bool:
        try:
            import rapidocr_onnxruntime  # noqa: F401
        except Exception:
            return False
        try:
            self._load_engine()
        except Exception:
            return False
        return True

    def image_to_text(self, image_bytes: bytes) -> OcrResult:
        import numpy as np
        from PIL import Image

        engine = self._load_engine()
        with Image.open(BytesIO(image_bytes)) as image:
            array = np.asarray(image.convert("RGB"))

        raw, _elapsed = engine(array)
        lines: list[str] = []
        scores: list[float] = []
        for item in raw or []:
            # RapidOCR rows are [box, text, confidence].
            text = str(item[1]).strip()
            if text:
                lines.append(text)
                try:
                    scores.append(float(item[2]))
                except (TypeError, ValueError, IndexError):
                    pass

        warnings: list[str] = []
        if not lines:
            warnings.append("OCR returned no readable text; the image may be unclear.")
        confidence = (sum(scores) / len(scores)) if scores else None
        return OcrResult(text="\n".join(lines), confidence=confidence, warnings=warnings)


def is_ocr_available() -> bool:
    """True when at least one configured OCR engine can run."""
    return default_ocr_provider().is_available()


def default_ocr_provider(tesseract_cmd: str | None = None) -> OcrProvider:
    """Return the best available OCR provider.

    Preference order: Tesseract (if the binary is present) then RapidOCR
    (pip-only). If neither can run, the Tesseract provider is returned anyway —
    ``is_available()`` is False and callers surface a graceful, explicit warning
    instead of fabricating syllabus content.
    """
    tesseract = TesseractOCRProvider(tesseract_cmd=tesseract_cmd)
    if tesseract.is_available():
        return tesseract
    rapid = RapidOcrProvider()
    if rapid.is_available():
        return rapid
    return tesseract