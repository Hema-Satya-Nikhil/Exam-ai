"""Phase 1 - additive model-paper extractor into the new exam model.

Parses uploaded model-paper text and produces a ``ModelPaperExtractionResult``
(GroupExtraction / ChoiceDetection) that is shown to the faculty for
confirmation before generation. Relationships are detected only from explicit
OR markers or (a)/(b) part patterns; nothing is ever fabricated.
"""
from __future__ import annotations

import re

from app.schemas.exam_structure import (
    ChoiceDetection,
    ExtractionSourceRef,
    GroupExtraction,
    ModelPaperExtractionResult,
    QuestionPart,
)

_GROUP_HEADER = re.compile(
    r"(?:Q\.?\s*)?(\d+)\s*[.)]?\s*\(?(\d{1,3})\s*(?:marks?)?\)?",
    re.IGNORECASE,
)
_PART_HEADER = re.compile(r"^\s*\(([a-z])\)\s*\(?(\d{1,3})\s*(?:marks?)?\)?", re.IGNORECASE)
_OR_LINE = re.compile(r"^\s*(?:or|else|any\s+one)\s*$", re.IGNORECASE)


def _looks_like_question_header(line: str) -> bool:
    first = line.split()[0].lower().rstrip(".).")
    return first.startswith("q") or first.isdigit()


def _bloom_to_level(btv: list[str]) -> str:
    return btv[0] if btv else "L3"


def _detect_part_choice(group: GroupExtraction) -> ChoiceDetection | None:
    if len(group.parts) < 2:
        return None
    labels = [p.part_label for p in group.parts if p.part_label]
    if len(labels) >= 2:
        keys = [f"{group.group_number}{lbl}" for lbl in labels]
        # (a)/(b) inside one group, combined with an explicit OR line seen -> candidate
        if group.group_evidence.confidence == "confirmed":
            return ChoiceDetection(
                choice_id=f"g{group.group_number}_or",
                member_keys=keys, select_count=1, confidence="inferred",
            )
    return None


class ModelPaperExtractor:
    """Determine groups/parts/marks/BTL/CO and explicit OR relationships."""

    def extract(self, text: str) -> ModelPaperExtractionResult:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        groups: list[GroupExtraction] = []
        current: GroupExtraction | None = None
        warnings: list[str] = []

        for line in lines:
            m = _GROUP_HEADER.match(line)
            if m and _looks_like_question_header(line):
                if current is not None:
                    if current.parts:
                        groups.append(current)
                    else:
                        warnings.append(
                            f"Group {current.group_number}: no parts detected; skipped.")
                current = GroupExtraction(
                    group_number=int(m.group(1)),
                    group_evidence=ExtractionSourceRef(
                        evidence=line[:60], confidence="inferred"),
                )
                if m.group(2):
                    current.marks_evidence.append(int(m.group(2)))
                self._capture_attributes(current, line)
                continue

            pm = _PART_HEADER.match(line)
            if pm and current is not None:
                part = QuestionPart(
                    question_number=current.group_number,
                    part_label=pm.group(1).lower(),
                    marks=int(pm.group(2)),
                    unit=0, topic="",
                    bloom_level=_bloom_to_level(current.btl),
                )
                current.parts.append(part)
                current.marks_evidence.append(int(pm.group(2)))
                self._capture_attributes(current, line)
                continue

            if _OR_LINE.match(line) and current is not None and current.parts:
                # explicit OR following parts -> mark as candidate (confirmed OR seen)
                current.group_evidence.confidence = "confirmed"

        if current is not None and current.parts:
            groups.append(current)

        choices = [c for c in (_detect_part_choice(g) for g in groups) if c is not None]

        total_printed = sum(p.marks for g in groups for p in g.parts)
        conf = "inferred" if groups else "unknown"
        return ModelPaperExtractionResult(
            exam_title="",
            total_printed_marks=total_printed or None,
            total_attempted_marks=None,
            groups=groups,
            choices=choices,
            warnings=warnings,
            confidence=conf,
        )

    @staticmethod
    def _capture_attributes(group: GroupExtraction, line: str) -> None:
        btl = re.findall(r"btl\s*[:=]?\s*([0-9]+)", line, re.IGNORECASE)
        if btl and not group.btl:
            group.btl = [f"L{btl[0]}"]
        co = re.findall(r"CO\s*[:=]?\.?\s*(\w+)", line, re.IGNORECASE)
        if co and not group.co:
            group.co = co[:1]