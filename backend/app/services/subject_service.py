from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from app.schemas.subject import SubjectCreate, SubjectRead, SubjectUpdate


@dataclass
class SubjectService:
    _subjects: dict[str, SubjectRead] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self._subjects:
            demo_subject = SubjectRead(
                id=str(uuid4()),
                code="CSE-402",
                name="Data Mining",
                department="CSE",
                is_active=True,
            )
            self._subjects[demo_subject.id] = demo_subject

    def list_subjects(self) -> list[SubjectRead]:
        return list(self._subjects.values())

    def create_subject(self, payload: SubjectCreate) -> SubjectRead:
        subject = SubjectRead(
            id=str(uuid4()),
            code=payload.code,
            name=payload.name,
            department=payload.department,
            is_active=True,
        )
        self._subjects[subject.id] = subject
        return subject

    def get_subject(self, subject_id: str) -> SubjectRead | None:
        return self._subjects.get(subject_id)

    def update_subject(self, subject_id: str, payload: SubjectUpdate) -> SubjectRead | None:
        subject = self._subjects.get(subject_id)
        if subject is None:
            return None

        updated = subject.model_copy(
            update={
                "name": payload.name if payload.name is not None else subject.name,
                "department": payload.department if payload.department is not None else subject.department,
                "is_active": payload.is_active if payload.is_active is not None else subject.is_active,
            }
        )
        self._subjects[subject_id] = updated
        return updated

    def delete_subject(self, subject_id: str) -> bool:
        return self._subjects.pop(subject_id, None) is not None
