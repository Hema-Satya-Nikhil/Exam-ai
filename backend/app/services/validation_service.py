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

        return ValidationSummary(passed=not issues, issues=issues)

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
        issues: list[ValidationIssue] = []
        normalized_texts: dict[str, int] = {}
        signatures: dict[tuple[str, ...], int] = {}

        for question in questions:
            normalized = _normalize_text(question.topic)
            if normalized in normalized_texts:
                issues.append(
                    ValidationIssue(
                        code="exact_duplicate_topic",
                        message=f"Question {question.question_number} duplicates topic text.",
                        path=f"questions.{question.question_number}.topic",
                    )
                )
            else:
                normalized_texts[normalized] = question.question_number

            signature = _token_signature(question.topic)
            if signature and signature in signatures:
                issues.append(
                    ValidationIssue(
                        code="near_duplicate_topic",
                        message=f"Question {question.question_number} is too similar to an existing topic.",
                        path=f"questions.{question.question_number}.topic",
                    )
                )
            else:
                signatures[signature] = question.question_number

        return ValidationSummary(passed=not issues, issues=issues)
