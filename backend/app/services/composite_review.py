from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal

PART_A = "short_answer"
PART_B = "main"
ExamPart = Literal["short_answer", "main"]


@dataclass
class ResolvedQuestion:
    key: str
    question: dict[str, Any]
    exam_part: str
    question_number: int | None
    group_number: int | None
    part_label: str | None


def is_composite_paper(paper_json: dict[str, Any] | None) -> bool:
    parts = (paper_json or {}).get("parts")
    return bool(parts and (parts.get("part_a") or parts.get("part_b")))


def normalize_part_label(part_label: str | None) -> str | None:
    if part_label is None:
        return None
    value = str(part_label).strip().lower()
    return value or None


def composite_question_key(
    *,
    exam_part: str | None,
    question_number: int | None = None,
    group_number: int | None = None,
    part_label: str | None = None,
) -> str | None:
    if exam_part == PART_A and question_number is not None:
        return f"{PART_A}:q{int(question_number)}"
    if exam_part == PART_B and group_number is not None and normalize_part_label(part_label):
        return f"{PART_B}:g{int(group_number)}:{normalize_part_label(part_label)}"
    return None


def question_key_from_dict(question: dict[str, Any]) -> str | None:
    return composite_question_key(
        exam_part=question.get("exam_part"),
        question_number=_as_int(question.get("question_number")),
        group_number=_as_int(question.get("group_number")),
        part_label=question.get("part_label"),
    )


def resolve_composite_question(
    paper: dict[str, Any] | Any,
    exam_part: str | None,
    question_number: int | None = None,
    group_number: int | None = None,
    part_label: str | None = None,
) -> ResolvedQuestion | None:
    paper_json = paper if isinstance(paper, dict) else getattr(paper, "paper_json", {}) or {}
    if not is_composite_paper(paper_json):
        return None

    if exam_part == PART_A:
        for question in paper_json.get("parts", {}).get("part_a", {}).get("questions", []):
            if _as_int(question.get("question_number")) == question_number:
                return ResolvedQuestion(
                    key=composite_question_key(exam_part=PART_A, question_number=question_number) or "",
                    question=question,
                    exam_part=PART_A,
                    question_number=question_number,
                    group_number=None,
                    part_label=None,
                )
        return None

    if exam_part == PART_B:
        normalized_label = normalize_part_label(part_label)
        for group in paper_json.get("parts", {}).get("part_b", {}).get("groups", []):
            if _as_int(group.get("group_number")) != group_number:
                continue
            for question in group.get("parts", []):
                if normalize_part_label(question.get("part_label")) == normalized_label:
                    return ResolvedQuestion(
                        key=composite_question_key(
                            exam_part=PART_B,
                            group_number=group_number,
                            part_label=normalized_label,
                        )
                        or "",
                        question=question,
                        exam_part=PART_B,
                        question_number=_as_int(question.get("question_number")),
                        group_number=group_number,
                        part_label=normalized_label,
                    )
        return None

    return None


def resolve_legacy_question(
    paper: dict[str, Any] | Any,
    question_number: int | None,
) -> ResolvedQuestion | None:
    if question_number is None:
        return None
    paper_json = paper if isinstance(paper, dict) else getattr(paper, "paper_json", {}) or {}
    for question in paper_json.get("questions", []):
        if _as_int(question.get("question_number")) == question_number:
            return ResolvedQuestion(
                key=f"legacy:q{int(question_number)}",
                question=question,
                exam_part=str(question.get("exam_part") or "legacy"),
                question_number=int(question_number),
                group_number=_as_int(question.get("group_number")),
                part_label=normalize_part_label(question.get("part_label")),
            )
    return None


def refresh_flattened_views(paper_json: dict[str, Any]) -> None:
    if not is_composite_paper(paper_json):
        return

    part_a = paper_json.get("parts", {}).get("part_a", {}) or {}
    part_b = paper_json.get("parts", {}).get("part_b", {}) or {}
    part_a_questions = part_a.get("questions", []) or []
    part_b_groups = part_b.get("groups", []) or []

    flat_questions: list[dict[str, Any]] = []
    flat_sections: list[dict[str, Any]] = []

    part_a_section_questions: list[dict[str, Any]] = []
    for question in part_a_questions:
        entry = _flat_entry(question, section="Part A", prefix_question_text=False)
        flat_questions.append(deepcopy(entry))
        part_a_section_questions.append(deepcopy(entry))

    flat_sections.append(
        {
            "name": str(part_a.get("name") or "PART A - SHORT ANSWER"),
            "section_type": "short_answer",
            "marks_per_question": _as_int(part_a_questions[0].get("marks")) if part_a_questions else 0,
            "questions": part_a_section_questions,
        }
    )

    part_b_section_questions: list[dict[str, Any]] = []
    for group in part_b_groups:
        group_number = _as_int(group.get("group_number")) or 0
        for question in group.get("parts", []) or []:
            label = f"{group_number}{question.get('part_label') or ''}"
            flat_entry = _flat_entry(question, section=f"Q{label}", prefix_question_text=False)
            flat_questions.append(deepcopy(flat_entry))
            section_entry = deepcopy(flat_entry)
            part_b_section_questions.append(section_entry)

    flat_sections.append(
        {
            "name": str(part_b.get("name") or "PART B - MAIN PAPER"),
            "section_type": "main",
            "marks_per_question": _as_int(part_b_section_questions[0].get("marks")) if part_b_section_questions else 0,
            "questions": part_b_section_questions,
        }
    )

    paper_json["questions"] = flat_questions
    paper_json["sections"] = flat_sections


def sync_locked_question_state(
    paper_json: dict[str, Any],
    resolved: ResolvedQuestion,
    *,
    locked: bool,
) -> None:
    locked_keys = list(paper_json.get("locked_question_keys", []) or [])
    locked_numbers = list(paper_json.get("locked_question_numbers", []) or [])

    if locked:
        if resolved.key not in locked_keys:
            locked_keys.append(resolved.key)
        if resolved.question_number is not None and resolved.question_number not in locked_numbers:
            locked_numbers.append(resolved.question_number)
    else:
        locked_keys = [key for key in locked_keys if key != resolved.key]
        if resolved.question_number is not None:
            locked_numbers = [number for number in locked_numbers if number != resolved.question_number]

    paper_json["locked_question_keys"] = locked_keys
    paper_json["locked_question_numbers"] = locked_numbers


def rebuild_locked_question_keys(paper_json: dict[str, Any]) -> list[str]:
    if not is_composite_paper(paper_json):
        return list(paper_json.get("locked_question_keys", []) or [])
    keys: list[str] = []
    for question in paper_json.get("parts", {}).get("part_a", {}).get("questions", []):
        if question.get("locked"):
            key = question_key_from_dict(question)
            if key:
                keys.append(key)
    for group in paper_json.get("parts", {}).get("part_b", {}).get("groups", []):
        for question in group.get("parts", []):
            if question.get("locked"):
                enriched = dict(question)
                enriched.setdefault("exam_part", PART_B)
                enriched.setdefault("group_number", group.get("group_number"))
                key = question_key_from_dict(enriched)
                if key:
                    keys.append(key)
    paper_json["locked_question_keys"] = keys
    return keys


def _flat_entry(question: dict[str, Any], *, section: str, prefix_question_text: bool) -> dict[str, Any]:
    entry = deepcopy(question)
    entry["section"] = section
    entry["question_number"] = _as_int(question.get("question_number")) or 0
    entry["marks"] = _as_int(question.get("marks")) or 0
    # NOTE: internal identifiers (choice_group_id / choice_member_id) are
    # deliberately NOT copied into the flat/renderer-facing view. The official
    # document renderer must never receive (or print) internal metadata; the
    # composite `parts` view remains the authoritative source for OR layout.
    entry.pop("choice_group_id", None)
    entry.pop("choice_member_id", None)
    entry.pop("source_references", None)
    if prefix_question_text:
        entry["question_text"] = f"Q{entry['question_number']}. {question.get('question_text', '')}"
    return entry


def _as_int(value: Any) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None
