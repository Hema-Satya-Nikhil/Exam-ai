from __future__ import annotations

from pydantic import BaseModel, Field


class SubjectCreate(BaseModel):
    code: str
    name: str
    department: str | None = None


class SubjectUpdate(BaseModel):
    name: str | None = None
    department: str | None = None
    is_active: bool | None = None


class SubjectRead(BaseModel):
    id: str
    code: str
    name: str
    department: str | None = None
    is_active: bool = True


class SubjectList(BaseModel):
    items: list[SubjectRead] = Field(default_factory=list)
