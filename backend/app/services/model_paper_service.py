from __future__ import annotations

import re

from app.schemas.model_paper import ModelPaperAnalysisResult, ModelPaperFinding, ModelPaperSectionFinding


class ModelPaperService:
    title_pattern = re.compile(r"^(.*question paper.*)$", re.IGNORECASE | re.MULTILINE)
    marks_pattern = re.compile(r"(\d+)\s*marks?", re.IGNORECASE)
    duration_pattern = re.compile(r"duration\s*[:\-]?\s*(\d+)\s*minutes?", re.IGNORECASE)
    section_pattern = re.compile(r"^\s*(part\s+[a-z0-9]+|section\s+[a-z0-9]+)\s*$", re.IGNORECASE | re.MULTILINE)
    question_pattern = re.compile(r"(?:^|\n)\s*(\d+)[\).]\s*(.+)$", re.IGNORECASE | re.MULTILINE)

    def analyze(self, extracted_text: str) -> ModelPaperAnalysisResult:
        findings: list[ModelPaperFinding] = []
        sections: list[ModelPaperSectionFinding] = []

        title_match = self.title_pattern.search(extracted_text)
        if title_match:
            findings.append(ModelPaperFinding(field="exam_title", value=title_match.group(1).strip(), confidence="inferred"))

        marks = [int(match.group(1)) for match in self.marks_pattern.finditer(extracted_text)]
        total_marks = sum(marks) if marks else None
        if total_marks is not None:
            findings.append(ModelPaperFinding(field="total_marks", value=str(total_marks), confidence="inferred"))

        duration_match = self.duration_pattern.search(extracted_text)
        duration_minutes = int(duration_match.group(1)) if duration_match else None
        if duration_minutes is not None:
            findings.append(ModelPaperFinding(field="duration_minutes", value=str(duration_minutes), confidence="inferred"))

        for section_match in self.section_pattern.finditer(extracted_text):
            sections.append(ModelPaperSectionFinding(name=section_match.group(1).strip(), confidence="inferred"))

        question_numbers = [int(match.group(1)) for match in self.question_pattern.finditer(extracted_text)]
        if question_numbers:
            findings.append(ModelPaperFinding(field="question_numbering", value=", ".join(map(str, question_numbers)), confidence="inferred"))

        bloom_hints = []
        lowered = extracted_text.lower()
        if "analyze" in lowered:
            bloom_hints.append("L4")
        if "evaluate" in lowered:
            bloom_hints.append("L5")
        if "create" in lowered or "design" in lowered:
            bloom_hints.append("L6")

        return ModelPaperAnalysisResult(
            sections=sections,
            findings=findings,
            total_marks=total_marks,
            duration_minutes=duration_minutes,
            confidence="inferred" if findings or sections else "unknown",
            bloom_hints=bloom_hints,
        )
