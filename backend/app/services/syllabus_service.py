from __future__ import annotations

import re

from app.schemas.academic import TopicRead, UnitRead
from app.schemas.syllabus import SyllabusParseResult


class SyllabusService:
    unit_pattern = re.compile(r"(?:unit|module)\s*(\d+)", re.IGNORECASE)
    topic_pattern = re.compile(r"(?:topic|lesson)\s*[:\-]?\s*(.+)", re.IGNORECASE)

    def parse_text(self, extracted_text: str, source_file_name: str) -> SyllabusParseResult:
        units: list[UnitRead] = []
        current_unit: UnitRead | None = None
        notes: list[str] = []

        for raw_line in extracted_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            unit_match = self.unit_pattern.search(line)
            if unit_match:
                current_unit = UnitRead(unit_number=int(unit_match.group(1)), title=line, confidence="inferred")
                units.append(current_unit)
                continue

            topic_match = self.topic_pattern.search(line)
            if current_unit and topic_match:
                current_unit.topics.append(TopicRead(topic_name=topic_match.group(1).strip(), confidence="inferred"))
                continue

            if current_unit:
                current_unit.topics.append(TopicRead(topic_name=line, confidence="inferred"))
            else:
                notes.append(f"Unassigned line: {line}")

        if not units:
            notes.append("No explicit unit headings were detected; faculty confirmation is required.")

        return SyllabusParseResult(source_file_name=source_file_name, units=units, confidence="inferred", notes=notes)

    def extract_units(self, parsed_result: SyllabusParseResult) -> list[int]:
        return [unit.unit_number for unit in parsed_result.units]
