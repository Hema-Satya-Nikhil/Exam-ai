"""Defensive post-processing of LLM question text (Task 7).

The generation prompt forbids metadata prefixes, but the model can still
occasionally echo them ("16. (5 marks) Section C - Unit 2 - Topic: ... (L5)
Analyze ..."). This layer strips ONLY prefixes that are confidently
recognizable as metadata — never meaningful question content.
"""

from __future__ import annotations

import re

# Prefix fragments removed only when they appear at the START of the text.
# Each pattern anchors at the beginning so interior sentence content that
# merely mentions "Unit 2" is never touched.
_PREFIX_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^question\s*\d+\s*[:.\-]\s*", re.IGNORECASE),
    re.compile(r"^q\d+\s*[:.\-]\s*", re.IGNORECASE),
    re.compile(r"^\d{1,3}\s*[.)]\s*"),
    re.compile(r"^\(\s*\d{1,2}\s*(?:marks?|m)\s*\)\s*", re.IGNORECASE),
    re.compile(r"^\d{1,2}\s*marks?\s*[:.\-]\s*", re.IGNORECASE),
    re.compile(r"^section\s+[a-d1-5]\s*[:\-–]\s*", re.IGNORECASE),
    re.compile(r"^unit\s+\d+\s*[:\-–]\s*", re.IGNORECASE),
    re.compile(r"^topic\s*[:\-–]\s*", re.IGNORECASE),
    re.compile(r"^bloom(?:\s*level)?\s*[:\-–]\s*[Ll]\d\s*[:\-–]?\s*", re.IGNORECASE),
    re.compile(r"^\(\s*[Ll]\d\s*\)\s*"),
    # "Scheduling criteria (L5) Analyze ..." — a topic value glued to a Bloom
    # parenthetical; a genuine question virtually never opens with "(L5)".
    re.compile(r"^[A-Z][\w'’,.\- ]{2,80}?\s*\(\s*[Ll]\d\s*\)\s+"),
    re.compile(r"^difficulty\s*[:\-–]\s*\w+\s*[:\-–]?\s*", re.IGNORECASE),
)

# Metadata fragments that may appear JOINED after another stripped fragment
# (e.g. "16. Section B - (5 marks) Topic: X ..."). Loop until stable.
_REPEAT_LIMIT = 6


def sanitize_question_text(raw: str) -> str:
    """Strip recognized metadata prefixes from a question string."""
    text = raw.strip()
    if not text:
        return text

    for _ in range(_REPEAT_LIMIT):
        original = text
        for pattern in _PREFIX_PATTERNS:
            text = pattern.sub("", text, count=1).strip()
        if text == original:
            break
    return text
