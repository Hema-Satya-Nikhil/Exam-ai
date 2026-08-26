from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, Table, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    roles: Mapped[list[Role]] = relationship(secondary=user_roles, lazy="selectin")


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)


class RefreshSession(Base):
    """Persists refresh-token sessions in PostgreSQL (no Redis needed).

    ``jti`` is the JWT ID embedded in the refresh token.  Revocation is done
    by flipping ``revoked=True`` so the session is never deleted until cleanup.
    """

    __tablename__ = "refresh_sessions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    jti: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Subject(Base, TimestampMixin):
    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    syllabus_versions: Mapped[list[Syllabus]] = relationship(back_populates="subject", cascade="all, delete-orphan")


class Syllabus(Base, TimestampMixin):
    __tablename__ = "syllabi"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    subject: Mapped[Subject] = relationship(back_populates="syllabus_versions")
    versions: Mapped[list[SyllabusVersion]] = relationship(back_populates="syllabus", cascade="all, delete-orphan")


class SyllabusVersion(Base, TimestampMixin):
    __tablename__ = "syllabus_versions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    syllabus_id: Mapped[str] = mapped_column(ForeignKey("syllabi.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_file_name: Mapped[Optional[str]] = mapped_column(String(255))
    source_file_hash: Mapped[Optional[str]] = mapped_column(String(128))
    structured_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    syllabus: Mapped[Syllabus] = relationship(back_populates="versions")
    units: Mapped[list[SyllabusUnit]] = relationship(back_populates="syllabus_version", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("syllabus_id", "version_number", name="uq_syllabus_version"),)


class SyllabusUnit(Base, TimestampMixin):
    __tablename__ = "syllabus_units"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    syllabus_version_id: Mapped[str] = mapped_column(ForeignKey("syllabus_versions.id", ondelete="CASCADE"), nullable=False)
    unit_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    confidence: Mapped[str] = mapped_column(String(20), default="confirmed", nullable=False)

    syllabus_version: Mapped[SyllabusVersion] = relationship(back_populates="units")
    topics: Mapped[list[SyllabusTopic]] = relationship(back_populates="unit", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("syllabus_version_id", "unit_number", name="uq_syllabus_unit"),)


class SyllabusTopic(Base, TimestampMixin):
    __tablename__ = "syllabus_topics"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    unit_id: Mapped[str] = mapped_column(ForeignKey("syllabus_units.id", ondelete="CASCADE"), nullable=False)
    topic_name: Mapped[str] = mapped_column(String(255), nullable=False)
    page_reference: Mapped[Optional[str]] = mapped_column(String(100))
    confidence: Mapped[str] = mapped_column(String(20), default="confirmed", nullable=False)

    unit: Mapped[SyllabusUnit] = relationship(back_populates="topics")


class UnitMaterial(Base, TimestampMixin):
    __tablename__ = "unit_materials"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    syllabus_version_id: Mapped[str] = mapped_column(ForeignKey("syllabus_versions.id", ondelete="CASCADE"), nullable=False)
    unit_number: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    extracted_content: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    page_references: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class PaperTemplate(Base, TimestampMixin):
    __tablename__ = "paper_templates"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    versions: Mapped[list[PaperTemplateVersion]] = relationship(back_populates="template", cascade="all, delete-orphan")


class PaperTemplateVersion(Base, TimestampMixin):
    __tablename__ = "paper_template_versions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    template_id: Mapped[str] = mapped_column(ForeignKey("paper_templates.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    template_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    template: Mapped[PaperTemplate] = relationship(back_populates="versions")
    sections: Mapped[list[PaperSection]] = relationship(back_populates="template_version", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("template_id", "version_number", name="uq_template_version"),)


class PaperSection(Base, TimestampMixin):
    __tablename__ = "paper_sections"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    template_version_id: Mapped[str] = mapped_column(ForeignKey("paper_template_versions.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    section_type: Mapped[str] = mapped_column(String(50), nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    marks_per_question: Mapped[int] = mapped_column(Integer, nullable=False)
    instructions: Mapped[Optional[str]] = mapped_column(Text)

    template_version: Mapped[PaperTemplateVersion] = relationship(back_populates="sections")


class QuestionBlueprint(Base, TimestampMixin):
    __tablename__ = "question_blueprints"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    paper_template_version_id: Mapped[Optional[str]] = mapped_column(ForeignKey("paper_template_versions.id", ondelete="SET NULL"))
    exam_type: Mapped[str] = mapped_column(String(120), nullable=False)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    blueprint_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    source_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
