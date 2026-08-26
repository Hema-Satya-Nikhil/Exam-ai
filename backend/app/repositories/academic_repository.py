from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import (
    PaperTemplate,
    PaperTemplateVersion,
    QuestionBlueprint,
    Subject,
    Syllabus,
    SyllabusTopic,
    SyllabusUnit,
    SyllabusVersion,
    UnitMaterial,
)


@dataclass
class AcademicRepository:
    session: AsyncSession

    async def list_subjects(self) -> Sequence[Subject]:
        result = await self.session.execute(select(Subject).where(Subject.is_active == True))
        return result.scalars().all()

    async def get_subject(self, subject_id: str) -> Subject | None:
        return await self.session.get(Subject, subject_id)

    async def get_subject_by_code(self, code: str) -> Subject | None:
        result = await self.session.execute(select(Subject).where(Subject.code == code))
        return result.scalar_one_or_none()

    async def create_subject(self, code: str, name: str, department: str | None = None) -> Subject:
        subject = Subject(code=code, name=name, department=department)
        self.session.add(subject)
        await self.session.flush()
        return subject

    async def create_syllabus(self, subject_id: str, title: str, structured_data: dict, file_name: str | None = None, file_hash: str | None = None) -> SyllabusVersion:
        syllabus = Syllabus(subject_id=subject_id, title=title)
        self.session.add(syllabus)
        await self.session.flush()

        version = SyllabusVersion(
            syllabus_id=syllabus.id,
            version_number=1,
            source_file_name=file_name,
            source_file_hash=file_hash,
            structured_data=structured_data,
        )
        self.session.add(version)
        await self.session.flush()
        return version

    async def get_syllabus_version(self, version_id: str) -> SyllabusVersion | None:
        return await self.session.get(SyllabusVersion, version_id)

    async def create_unit_material(self, syllabus_version_id: str, unit_number: int, file_name: str, file_hash: str, mime_type: str, extracted_content: dict, page_references: dict) -> UnitMaterial:
        material = UnitMaterial(
            syllabus_version_id=syllabus_version_id,
            unit_number=unit_number,
            file_name=file_name,
            file_hash=file_hash,
            mime_type=mime_type,
            extracted_content=extracted_content,
            page_references=page_references,
        )
        self.session.add(material)
        await self.session.flush()
        return material

    async def list_unit_materials(self, syllabus_version_id: str) -> Sequence[UnitMaterial]:
        result = await self.session.execute(select(UnitMaterial).where(UnitMaterial.syllabus_version_id == syllabus_version_id))
        return result.scalars().all()

    async def create_blueprint(self, exam_type: str, subject_id: str, blueprint_json: dict, source_mode: str) -> QuestionBlueprint:
        blueprint = QuestionBlueprint(
            exam_type=exam_type,
            subject_id=subject_id,
            blueprint_json=blueprint_json,
            source_mode=source_mode,
            validation_status="valid",
        )
        self.session.add(blueprint)
        await self.session.flush()
        return blueprint

    async def get_blueprint(self, blueprint_id: str) -> QuestionBlueprint | None:
        return await self.session.get(QuestionBlueprint, blueprint_id)
