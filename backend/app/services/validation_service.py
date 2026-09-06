from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re

from app.schemas.academic import PaperBlueprint, QuestionRequirement
from app.schemas.generation import ValidationIssue, ValidationSummary


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _token_signature(value: str) -> tuple[str, ...]:
    tokens = re.findall(r"[a-z0-9]+", value.lower())
    return tuple(sorted(set(tokens)))


def _jaccard_similarity(text1: str, text2: str) -> float:
    set1 = set(re.findall(r"[a-z0-9]+", text1.lower()))
    set2 = set(re.findall(r"[a-z0-9]+", text2.lower()))
    if not set1 or not set2:
        return 0.0
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    return len(intersection) / len(union)


class ValidationService:
    def validate_blueprint(self, blueprint: PaperBlueprint) -> ValidationSummary:
        issues: list[ValidationIssue] = []
        if blueprint.total_marks != sum(question.marks for question in blueprint.questions):
            issues.append(
                ValidationIssue(
                    code="total_marks_mismatch",
                    message="Blueprint total marks do not match the sum of question marks.",
                    path="total_marks",
                )
            )

        section_counts = Counter(question.section for question in blueprint.questions)
        for section in blueprint.sections:
            if section_counts.get(section.name, 0) != section.question_count:
                issues.append(
                    ValidationIssue(
                        code="section_question_count_mismatch",
                        message=f"Section {section.name} question count does not match the blueprint.",
                        path=f"sections.{section.name}",
                    )
                )

        expected_number = 1
        for question in sorted(blueprint.questions, key=lambda item: item.question_number):
            if question.question_number != expected_number:
                issues.append(
                    ValidationIssue(
                        code="question_number_sequence_error",
                        message="Question numbering must be contiguous and start at 1.",
                        path=f"questions.{question.question_number}",
                    )
                )
                break
            expected_number += 1

        issues.extend(self.validate_question_scope(blueprint).issues)
        issues.extend(self.detect_duplicate_questions(blueprint.questions).issues)

        # Only ERROR-severity issues block generation. Warnings (e.g. a section
        # reusing a topic because the confirmed syllabus lists fewer topics than
        # the section has questions) are reported to the faculty but must not
        # make a legitimate paper ungeneratable.
        errors = [issue for issue in issues if issue.severity == "error"]
        return ValidationSummary(passed=not errors, issues=issues)

    def validate_question(self, requirement: QuestionRequirement, generated_text: str, model_paper_text: str | None = None) -> ValidationSummary:
        issues: list[ValidationIssue] = []
        if requirement.marks <= 0:
            issues.append(ValidationIssue(code="invalid_marks", message="Marks must be positive."))
        if not generated_text.strip():
            issues.append(ValidationIssue(code="empty_question", message="Question text cannot be empty."))

        # Separate 2-mark constraints check
        if requirement.marks == 2:
            if len(generated_text.split()) > 45:
                issues.append(ValidationIssue(code="2_mark_length_excess", message="2-mark questions should be concise (under 45 words)."))

        # Model paper copy protection
        if model_paper_text and generated_text:
            similarity = _jaccard_similarity(generated_text, model_paper_text)
            if similarity > 0.6:
                issues.append(ValidationIssue(code="model_paper_copy_detected", message="Generated question text is too similar to the model paper."))

        return ValidationSummary(passed=not issues, issues=issues)

    def validate_question_scope(self, blueprint: PaperBlueprint) -> ValidationSummary:
        issues: list[ValidationIssue] = []
        allowed_units = set(blueprint.selected_units)
        for question in blueprint.questions:
            if question.unit not in allowed_units:
                issues.append(
                    ValidationIssue(
                        code="unit_out_of_scope",
                        message=f"Question {question.question_number} uses a unit outside the selected syllabus coverage.",
                        path=f"questions.{question.question_number}.unit",
                    )
                )
            if not question.topic.strip():
                issues.append(
                    ValidationIssue(
                        code="missing_topic",
                        message=f"Question {question.question_number} must include a topic.",
                        path=f"questions.{question.question_number}.topic",
                    )
                )
        return ValidationSummary(passed=not issues, issues=issues)

    def detect_duplicate_questions(self, questions: list[QuestionRequirement]) -> ValidationSummary:
        """Flag redundant topic reuse inside the blueprint.

        Duplicate scope is the (unit, topic) identity, never the topic alone:
        the same topic name may legitimately appear in different syllabus units
        (e.g. "Process Scheduling" in both Unit 1 and Unit 2) and must NOT be
        treated as a duplicate across those units. Rules enforced here (per
        section; reuse across *different* sections is normal exam practice):

        * same (unit, topic) repeated while that unit demonstrably offers other
          topics elsewhere in the paper -> error. The variety existed and was
          not used;
        * same (unit, topic) repeated because the confirmed syllabus lists no
          further topics for that unit -> warning only ("topic_pool_exhausted").
          The faculty should enrich the syllabus, but a legitimate thin-syllabus
          paper must remain generatable;
        * same topic text on a DIFFERENT unit -> valid, never flagged.
        """
        issues: list[ValidationIssue] = []

        # Topic vocabulary actually observed per unit across the whole paper.
        topics_per_unit: dict[int, set[str]] = {}
        for question in questions:
            topics_per_unit.setdefault(question.unit, set()).add(_normalize_text(question.topic))

        by_section: dict[str, list[QuestionRequirement]] = {}
        for question in questions:
            by_section.setdefault(question.section, []).append(question)

        for section_name, section_questions in by_section.items():
            # Keyed by (unit, topic) so a topic name shared across different
            # units never collides as a duplicate.
            normalized_first: dict[tuple[int, str], QuestionRequirement] = {}
            signature_first: dict[tuple[int, tuple[str, ...]], QuestionRequirement] = {}

            for question in section_questions:
                normalized = _normalize_text(question.topic)
                signature = _token_signature(question.topic)
                unit = question.unit

                original = normalized_first.get((unit, normalized))
                if original is None and signature:
                    original = signature_first.get((unit, signature))

                if original is not None:
                    if len(topics_per_unit.get(unit, set())) >= 2:
                        issues.append(
                            ValidationIssue(
                                code="exact_duplicate_topic"
                                if _normalize_text(original.topic) == normalized
                                else "near_duplicate_topic",
                                message=(
                                    f"Question {question.question_number} in section "
                                    f"{section_name} repeats topic '{question.topic.strip()}' "
                                    f"on unit {unit} even though other topics of that "
                                    "unit are available."
                                ),
                                path=f"questions.{question.question_number}.topic",
                            )
                        )
                    else:
                        issues.append(
                            ValidationIssue(
                                code="topic_pool_exhausted",
                                message=(
                                    f"Section {section_name} reuses topic "
                                    f"'{question.topic.strip()}' because unit "
                                    f"{unit} lists no further topics. Add topics "
                                    "to the syllabus for richer coverage."
                                ),
                                path=f"questions.{question.question_number}.topic",
                                severity="warning",
                            )
                        )

                normalized_first.setdefault((unit, normalized), question)
                if signature:
                    signature_first.setdefault((unit, signature), question)

        return ValidationSummary(passed=not issues, issues=issues)
