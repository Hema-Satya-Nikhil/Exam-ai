"""Additive exam-structure service.

Computes the printed-vs-attempted marks model and validates a two-part
institutional examination (Part A short-answer + Part B main paper with
explicit ChoiceGroup OR relationships). Purely additive: it does not touch the
existing flat `PaperBlueprint` pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.exam_structure import (
    ChoiceGroup,
    ExamConfig,
    ExamMarks,
    MainPaperConfig,
    PartMarks,
    QuestionGroup,
    QuestionPart,
    ShortAnswerPaperConfig,
)
from app.schemas.generation import ValidationIssue, ValidationSummary


def _part_key(part: QuestionPart, group: QuestionGroup) -> str:
    return f"{group.group_number}{part.part_label or ''}"


def _group_key(group: QuestionGroup) -> str:
    return str(group.group_number)


@dataclass
class _ChoiceResolution:
    """Resolved member keys for a ChoiceGroup with computed marks."""

    group_member_marks: dict[str, int] = field(default_factory=dict)
    part_member_keys: set[str] = field(default_factory=set)


def _resolve_choices(config: MainPaperConfig) -> dict[str, _ChoiceResolution]:
    by_number = {g.group_number: g for g in config.groups}
    res: dict[str, _ChoiceResolution] = {}
    for cg in config.choice_groups:
        r = _ChoiceResolution()
        for member in cg.members:
            key = member.key
            if key.isdigit():
                group = by_number.get(int(key))
                if group and group.choice_group == cg.id:
                    r.group_member_marks[key] = sum(p.marks for p in group.parts)
                    continue
            r.part_member_keys.add(key)
        res[cg.id] = r
    return res


def part_b_marks(config: MainPaperConfig) -> PartMarks:
    """Part B marks split into printed-available vs attempted-required."""
    resolutions = _resolve_choices(config)
    covered_parts: set[str] = set()
    for r in resolutions.values():
        covered_parts |= r.part_member_keys
    # Whole-group choice: every part of a group-level alternative is covered.
    for g in config.groups:
        r = resolutions.get(g.choice_group) if g.choice_group else None
        if r is not None and str(g.group_number) in r.group_member_marks:
            for p in g.parts:
                covered_parts.add(_part_key(p, g))

    printed = 0
    attempted = 0
    for g in config.groups:
        for p in g.parts:
            printed += p.marks
            if _part_key(p, g) not in covered_parts:
                attempted += p.marks  # compulsory part
    for cg in config.choice_groups:
        r = resolutions.get(cg.id)
        if r is None:
            continue
        member_marks = []
        for member in cg.members:
            gmarks = r.group_member_marks.get(member.key)
            member_marks.append(gmarks if gmarks is not None else member.marks)
        attempted += sum(sorted(member_marks)[: cg.select_count])

    return PartMarks(printed_available_marks=printed, attempted_required_marks=attempted)


def compute_exam_marks(config: ExamConfig) -> ExamMarks:
    part_a = PartMarks(
        printed_available_marks=config.part_a.total_marks,
        attempted_required_marks=config.part_a.total_marks,
    )
    part_b = part_b_marks(config.part_b)
    return ExamMarks(part_a=part_a, part_b=part_b)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_part_a(cfg: ShortAnswerPaperConfig) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if cfg.question_count != 10:
        issues.append(ValidationIssue(
            code="part_a_count", message="Part A defaults to exactly 10 questions."))
    if cfg.marks_per_question != 2:
        issues.append(ValidationIssue(
            code="part_a_marks", message="Part A each question is 2 marks."))
    if cfg.total_marks != 20:
        issues.append(ValidationIssue(code="part_a_total", message="Part A total must be 20 marks."))
    if cfg.duration_minutes != 20:
        issues.append(ValidationIssue(
            code="part_a_duration", message="Part A duration is 20 minutes."))
    return issues


def validate_exam(config: ExamConfig) -> ValidationSummary:
    issues: list[ValidationIssue] = []

    # Part A
    issues += validate_part_a(config.part_a)

    # Part B attempted marks must equal its declared total.
    marks = compute_exam_marks(config)
    if marks.part_b.attempted_required_marks != config.part_b.total_marks:
        issues.append(ValidationIssue(
            code="part_b_attempted_mismatch",
            message="Part B attempted marks ({}) != configured total ({}).".format(
                marks.part_b.attempted_required_marks, config.part_b.total_marks),
        ))

    # Choice members must resolve to a real group or part.
    group_keys = {_group_key(g) for g in config.part_b.groups}
    part_keys = {_part_key(p, g) for g in config.part_b.groups for p in g.parts}
    for cg in config.part_b.choice_groups:
        for member in cg.members:
            if member.key not in group_keys and member.key not in part_keys:
                issues.append(ValidationIssue(
                    code="choice_member_unresolved",
                    message=f"choice group '{cg.id}' member '{member.key}' not found.",
                ))

    # Duplicate topic detection within a group part-set is intentionally left to
    # the existing validation layer during generation; here we only enforce the
    # structure and marks invariants described in the institutional format.

    return ValidationSummary(passed=not issues, issues=issues)