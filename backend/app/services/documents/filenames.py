from __future__ import annotations

import re

# Everything outside the ASCII alphanumeric range is removed so that
# a multi-word subject collapses to a clean, deterministic, filesystem-safe
# slug. Spaces are dropped (not replaced with underscores) so that
# "Data Warehousing and Data Mining" becomes "DataWarehousingandDataMining".
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9]")

ALLOWED_EXPORT_FORMATS = ("pdf", "docx")


def build_export_filename(subject: str | None, format_name: str) -> str:
    """Build a deterministic, filesystem-safe exam export filename.

    The user-facing download filename is derived from the paper's *persisted
    subject* (never its UUID title or an internal id) and always carries the
    ``_Exam_ai`` suffix so exports are recognizable and disambiguatable from
    machine-generated artefacts.

    Examples
    --------
    >>> build_export_filename("Operating System", "pdf")
    'OperatingSystem_Exam_ai.pdf'
    >>> build_export_filename("Data Warehousing and Data Mining", "docx")
    'DataWarehousingandDataMining_Exam_ai.docx'
    """
    raw = (subject or "").strip()
    slug = _UNSAFE_CHARS.sub("", raw)
    if not slug:
        slug = "Exam"
    if format_name not in ALLOWED_EXPORT_FORMATS:
        raise ValueError(
            f"Unsupported export format {format_name!r}; "
            f"expected one of {', '.join(ALLOWED_EXPORT_FORMATS)}"
        )
    return f"{slug}_Exam_ai.{format_name}"