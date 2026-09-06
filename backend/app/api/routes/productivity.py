from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import ensure_paper_access, get_current_user, get_db, require_roles
from app.models.academic import PaperTemplate, PaperTemplateVersion, User
from app.models.audit import AuditLog
from app.models.generation import GeneratedPaper, GenerationJob, PaperVersion
from app.services.generation_worker import enqueue_job

router = APIRouter()


def _is_admin(user: User) -> bool:
    return user.has_role("admin")


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    template_json: dict


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    template_json: dict | None = None


class CloneRequest(BaseModel):
    title: str | None = None


def _template_read(template: PaperTemplate, version: PaperTemplateVersion | None) -> dict:
    return {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "created_by": template.created_by,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
        "version": version.version_number if version else None,
        "template_json": version.template_json if version else {},
    }


@router.get("/jobs")
async def list_generation_jobs(
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, list[dict]]:
    stmt = select(GenerationJob).order_by(GenerationJob.created_at.desc()).limit(100)
    if not _is_admin(current_user):
        stmt = stmt.where(GenerationJob.created_by == current_user.user_id)
    if status_filter:
        stmt = stmt.where(GenerationJob.status == status_filter)
    jobs = (await db.execute(stmt)).scalars().all()
    return {"jobs": [
        {
            "id": job.id, "status": job.status, "current_step": job.current_step,
            "progress_percent": job.progress_percent, "retry_count": job.retry_count,
            "error_message": job.error_message, "paper_id": job.paper_id,
            "total_questions": job.total_questions, "created_at": job.created_at.isoformat() if job.created_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        } for job in jobs
    ]}


@router.post("/jobs/{job_id}/retry")
async def retry_generation_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    job = await db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Generation job not found")
    if not _is_admin(current_user) and job.created_by != current_user.user_id:
        raise HTTPException(status_code=403, detail="You do not have access to this job.")
    if job.status != "failed":
        raise HTTPException(status_code=409, detail="Only failed jobs can be retried.")
    job.status = "queued"
    job.current_step = "Retry queued"
    job.error_message = None
    job.retry_count += 1
    job.finished_at = None
    await db.commit()
    enqueue_job(job.id)
    return {"job_id": job.id, "status": job.status}


@router.get("/templates")
async def list_templates(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = select(PaperTemplate).where(PaperTemplate.is_active.is_(True))
    if not _is_admin(current_user):
        stmt = stmt.where(PaperTemplate.created_by == current_user.user_id)
    templates = (await db.execute(stmt.order_by(PaperTemplate.updated_at.desc()))).scalars().all()
    result = []
    for template in templates:
        version = (await db.execute(
            select(PaperTemplateVersion).where(PaperTemplateVersion.template_id == template.id)
            .order_by(PaperTemplateVersion.version_number.desc()).limit(1)
        )).scalars().first()
        result.append(_template_read(template, version))
    return {"templates": result}


@router.post("/templates", status_code=status.HTTP_201_CREATED)
async def create_template(payload: TemplateCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    template = PaperTemplate(name=payload.name, description=payload.description, created_by=current_user.user_id)
    db.add(template)
    await db.flush()
    version = PaperTemplateVersion(template_id=template.id, version_number=1, template_json=payload.template_json)
    db.add(version)
    await db.commit()
    await db.refresh(template)
    return _template_read(template, version)


@router.patch("/templates/{template_id}")
async def update_template(template_id: str, payload: TemplateUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    template = await db.get(PaperTemplate, template_id)
    if template is None or (not _is_admin(current_user) and template.created_by != current_user.user_id):
        raise HTTPException(status_code=404, detail="Template not found")
    if payload.name is not None:
        template.name = payload.name
    if payload.description is not None:
        template.description = payload.description
    version = (await db.execute(select(PaperTemplateVersion).where(PaperTemplateVersion.template_id == template.id).order_by(PaperTemplateVersion.version_number.desc()).limit(1))).scalars().first()
    if payload.template_json is not None:
        version = PaperTemplateVersion(template_id=template.id, version_number=(version.version_number + 1 if version else 1), template_json=payload.template_json)
        db.add(version)
    await db.commit()
    return _template_read(template, version)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(template_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    template = await db.get(PaperTemplate, template_id)
    if template is None or (not _is_admin(current_user) and template.created_by != current_user.user_id):
        raise HTTPException(status_code=404, detail="Template not found")
    template.is_active = False
    await db.commit()


async def _paper_or_404(paper_id: str, user: User, db: AsyncSession) -> GeneratedPaper:
    await ensure_paper_access(paper_id, user, db)
    paper = await db.get(GeneratedPaper, paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


@router.get("/papers/{paper_id}/versions")
async def list_versions(paper_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _paper_or_404(paper_id, current_user, db)
    versions = (await db.execute(select(PaperVersion).where(PaperVersion.generated_paper_id == paper_id).order_by(PaperVersion.version_number.desc()))).scalars().all()
    return {"versions": [{"id": v.id, "version_number": v.version_number, "validation_summary": v.validation_summary, "created_at": None, "paper_json": v.paper_json} for v in versions]}


@router.post("/papers/{paper_id}/versions/{version_id}/restore")
async def restore_version(paper_id: str, version_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    paper = await _paper_or_404(paper_id, current_user, db)
    source = await db.get(PaperVersion, version_id)
    if source is None or source.generated_paper_id != paper_id:
        raise HTTPException(status_code=404, detail="Paper version not found")
    latest = (await db.execute(select(func.max(PaperVersion.version_number)).where(PaperVersion.generated_paper_id == paper_id))).scalar() or 0
    restored = PaperVersion(generated_paper_id=paper_id, version_number=latest + 1, paper_json=source.paper_json, blueprint_version=source.blueprint_version, rules_version=source.rules_version, llm_model=source.llm_model, prompt_version=source.prompt_version, validation_summary=source.validation_summary)
    db.add(restored)
    await db.flush()
    paper.current_version_id = restored.id
    db.add(AuditLog(actor_user_id=current_user.user_id, action="restore_paper_version", entity_type="paper", entity_id=paper_id, payload={"source_version_id": version_id}))
    await db.commit()
    return {"paper_id": paper_id, "version_id": restored.id, "version_number": restored.version_number}


@router.post("/papers/{paper_id}/clone")
async def clone_paper(paper_id: str, payload: CloneRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    paper = await _paper_or_404(paper_id, current_user, db)
    version = await db.get(PaperVersion, paper.current_version_id) if paper.current_version_id else None
    if version is None:
        raise HTTPException(status_code=409, detail="Paper has no version to clone")
    source_job = await db.get(GenerationJob, paper.generation_job_id)
    if source_job is None:
        raise HTTPException(status_code=409, detail="Paper has no generation configuration to clone")
    clone_job = GenerationJob(
        blueprint_id=source_job.blueprint_id,
        status="queued",
        current_step="Cloned paper ready for editing",
        created_by=current_user.user_id,
        total_questions=source_job.total_questions,
    )
    db.add(clone_job)
    await db.flush()
    clone = GeneratedPaper(
        generation_job_id=clone_job.id,
        title=payload.title or f"{paper.title} (Copy)",
        status="draft",
        created_by=current_user.user_id,
    )
    db.add(clone)
    await db.flush()
    clone_version = PaperVersion(
        generated_paper_id=clone.id,
        version_number=1,
        paper_json=version.paper_json,
        blueprint_version=version.blueprint_version,
        rules_version=version.rules_version,
        llm_model=version.llm_model,
        prompt_version=version.prompt_version,
        validation_summary=version.validation_summary,
    )
    db.add(clone_version)
    await db.flush()
    clone.current_version_id = clone_version.id
    clone_job.paper_id = clone.id
    db.add(AuditLog(actor_user_id=current_user.user_id, action="clone_paper", entity_type="paper", entity_id=paper_id, payload={}))
    await db.commit()
    return {"source_paper_id": paper_id, "paper_id": clone.id, "title": clone.title, "paper_json": version.paper_json}


@router.get("/papers/{paper_id}/downloads")
async def list_downloads(paper_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _paper_or_404(paper_id, current_user, db)
    versions = (await db.execute(select(PaperVersion).where(PaperVersion.generated_paper_id == paper_id).order_by(PaperVersion.version_number.desc()))).scalars().all()
    return {"downloads": [{"version_id": v.id, "version_number": v.version_number, "pdf_available": bool(v.exported_pdf_path), "docx_available": bool(v.exported_docx_path), "pdf_path": v.exported_pdf_path, "docx_path": v.exported_docx_path} for v in versions]}


@router.get("/usage", dependencies=[Depends(require_roles("admin"))])
async def usage_summary(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(GenerationJob.status, func.count(GenerationJob.id)).group_by(GenerationJob.status))).all()
    logs = (await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100))).scalars().all()
    return {"generation_counts": {status: count for status, count in rows}, "audit_activity": [{"action": l.action, "entity_type": l.entity_type, "created_at": l.created_at.isoformat() if l.created_at else None} for l in logs]}
