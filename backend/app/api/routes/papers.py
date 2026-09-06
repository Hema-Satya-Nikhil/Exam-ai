from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    ensure_paper_access,
    get_current_user,
    get_db,
    require_faculty_access,
    require_roles,
)
from app.models.audit import ExportAudit
from app.models.academic import User
from app.schemas.paper_document import PaperDocumentExportRequest
from app.schemas.paper_review import PaperQuestionRegenerateRequest
from app.services.documents.filenames import build_export_filename
from app.schemas.paper_workflow import (
    PaperApprovalRequest,
    PaperDraftCreate,
    PaperDraftRead,
    PaperLockRequest,
    PaperQuestionUpdate,
)
from app.services.documents.paper_renderer import PaperRenderer
from app.services.paper_workflow_service import PaperWorkflowService

router = APIRouter()
paper_renderer = PaperRenderer()
workflow_service = PaperWorkflowService()


# ---------------------------------------------------------------------------
# Draft CRUD
# ---------------------------------------------------------------------------

@router.post("/drafts", response_model=PaperDraftRead, status_code=status.HTTP_201_CREATED)
async def create_draft(
    request: PaperDraftCreate,
    current_user: User = Depends(get_current_user),
) -> PaperDraftRead:
    await ensure_paper_access(paper_id, current_user, db)
    return workflow_service.create_draft(request)


@router.get("/drafts/{paper_id}", response_model=PaperDraftRead)
async def get_draft(
    paper_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_faculty_access),
) -> PaperDraftRead:
    await ensure_paper_access(paper_id, current_user, db)
    # Request-scoped session: the DB-backed lookup is authoritative whenever
    # persisted paper data exists. get_draft_async still consults the
    # in-process generation-store fallback first, which is required for
    # freshly generated drafts that are not fully persisted yet.
    draft = await PaperWorkflowService(session=db).get_draft_async(paper_id)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper draft not found")
    return draft


# ---------------------------------------------------------------------------
# Question edit — records acting user
# ---------------------------------------------------------------------------

@router.patch("/drafts/{paper_id}/question", response_model=PaperDraftRead)
async def update_question(
    paper_id: str,
    request: PaperQuestionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_faculty_access),
) -> PaperDraftRead:
    await ensure_paper_access(paper_id, current_user, db)
    wf = PaperWorkflowService(session=db)
    wf.actor_id = current_user.user_id
    draft = await wf.update_question_async(paper_id, request)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper draft not found")
    return draft


# ---------------------------------------------------------------------------
# Lock / unlock — records acting user
# ---------------------------------------------------------------------------

@router.post("/drafts/{paper_id}/lock", response_model=PaperDraftRead)
async def lock_question(
    paper_id: str,
    request: PaperLockRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_faculty_access),
) -> PaperDraftRead:
    await ensure_paper_access(paper_id, current_user, db)
    wf = PaperWorkflowService(session=db)
    wf.actor_id = current_user.user_id
    draft = await wf.lock_question_async(paper_id, request)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper draft not found")
    return draft


@router.post("/drafts/{paper_id}/unlock", response_model=PaperDraftRead)
async def unlock_question(
    paper_id: str,
    request: PaperLockRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_faculty_access),
) -> PaperDraftRead:
    await ensure_paper_access(paper_id, current_user, db)
    wf = PaperWorkflowService(session=db)
    wf.actor_id = current_user.user_id
    draft = await wf.unlock_question_async(paper_id, request)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return draft


# ---------------------------------------------------------------------------
# Approval — FACULTY or ADMIN, records authenticated user
# ---------------------------------------------------------------------------

@router.post("/drafts/{paper_id}/approve", dependencies=[Depends(require_roles("faculty", "admin"))])
async def approve_draft(
    paper_id: str,
    request: PaperApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_faculty_access),
) -> dict[str, object]:
    await ensure_paper_access(paper_id, current_user, db)
    approval = await PaperWorkflowService(session=db).approve_paper_async(
        paper_id, current_user.user_id, getattr(request, "comments", None)
    )
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper draft not found")

    # Keep the generation singleton's workflow store in sync so the export
    # fallback path (which reads that store first) sees the approved status.
    try:
        from app.api.routes.generation import generation_service as _gs

        stored = _gs.paper_workflow.store.papers.get(paper_id)
        if stored is not None and stored.status != "approved":
            stored.status = "approved"
    except Exception:
        pass

    # Persist approval audit record with the authenticated user's ID
    from app.models.audit import Approval  # local import to avoid circular
    from app.models.generation import GeneratedPaper  # noqa: F401

    audit_entry = Approval(
        generated_paper_id=paper_id,
        approved_by_user_id=current_user.user_id,
        status="approved",
        comments=getattr(request, "comments", None),
    )
    db.add(audit_entry)
    await db.commit()

    return approval.model_dump()


# ---------------------------------------------------------------------------
# Regeneration — records acting user
# ---------------------------------------------------------------------------

@router.post("/drafts/{paper_id}/regenerate")
async def regenerate_question(
    paper_id: str,
    request: PaperQuestionRegenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_faculty_access),
) -> dict[str, object]:
    await ensure_paper_access(paper_id, current_user, db)
    wf = PaperWorkflowService(session=db)
    wf.actor_id = current_user.user_id
    try:
        draft = await wf.regenerate_question(paper_id, request)
        if draft is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Question not found"
            )
        return draft.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Export — FACULTY or ADMIN, records authenticated user in ExportAudit.
# Export authorization is VALIDATION-based, not approval-based: the workflow is
# Review → final validation → Export. There is no manual paper-approval step.
# ---------------------------------------------------------------------------

EXPORT_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _blocking_validation_issues(paper_json: dict) -> list[str]:
    """Return blocking (error-severity) validation messages persisted in the
    paper's validation record — the database is the source of truth.

    Handles two persisted shapes:
      * composite:  ``{"passed", "errors": [...], "warnings": [...]}`` — errors
        are the explicit blocking set (an empty list means validation passed).
      * legacy flat: ``{"passed", "issues": [...]}`` (ValidationSummary dump) —
        blocking entries are filtered by error severity.
    """
    validation = paper_json.get("validation") or {}
    # Composite shape: `errors` is the explicit blocking set.
    errors = validation.get("errors")
    if errors is not None:
        blocking = [
            f"{e.get('message', 'Validation error')} [{e.get('code', 'validation_error')}]"
            for e in errors
            if isinstance(e, dict) and e.get("severity", "error") == "error"
        ]
        if blocking:
            return blocking
        # errors present but empty: only an explicit passed=False still blocks.
        if validation.get("passed") is False:
            return ["Paper validation has not passed yet."]
        return []
    # Legacy shape: filter error-severity from the combined issues list.
    issues = validation.get("issues") or []
    if issues:
        return [
            f"{i.get('message', 'Validation issue')} [{i.get('code', 'validation_error')}]"
            for i in issues
            if isinstance(i, dict) and i.get("severity") == "error"
        ]
    # No issues list persisted: fall back to the recorded pass/fail flag.
    if validation and validation.get("passed") is False:
        return ["Paper validation has not passed yet."]
    return []


async def _render_approved_export(
    paper_id: str,
    format_name: str,
    user_id: str,
    db: AsyncSession,
) -> tuple[str, str, str]:
    """Render a validated paper, record an ExportAudit row, return its path.

    Returns (absolute file path, filename, media type). Export is authorized by
    the PERSISTED validation state, not a manual approval action: the paper
    must exist, have a persisted PaperVersion, and carry no blocking
    validation issues.

    ``ExportAudit.approved_version`` always references the ACTUAL
    ``PaperVersion.id`` from PostgreSQL (via ``GeneratedPaper.current_version_id``
    or the latest version row) — never a fabricated label like ``"v1"``.
    """
    from sqlalchemy import select

    from app.models.generation import GeneratedPaper, PaperVersion
    from app.services.paper_workflow_service import PaperWorkflowService as _WS

    workflow_service_db = _WS(session=db)
    paper = await workflow_service_db.get_draft_async(paper_id)
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found",
        )

    blocking = _blocking_validation_issues(paper.paper_json or {})
    if blocking:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resolve the highlighted issues before exporting. "
            + "; ".join(blocking[:5]),
        )

    # Resolve the real approved version UUID from the database. Trust the FK
    # first; fall back to the highest version_number for safety. Never invent
    # a version identifier.
    confirmed_paper = await db.get(GeneratedPaper, paper_id)
    approved_version_id: str | None = None
    if confirmed_paper is not None:
        approved_version_id = confirmed_paper.current_version_id
    if approved_version_id is None:
        result = await db.execute(
            select(PaperVersion.id)
            .where(PaperVersion.generated_paper_id == paper_id)
            .order_by(PaperVersion.version_number.desc())
            .limit(1)
        )
        approved_version_id = result.scalar_one_or_none()
    if approved_version_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approved paper has no persisted version to export",
        )

    output_dir = Path("storage") / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    # Per-paper filename so two papers never overwrite each other's file.
    output_path = output_dir / f"{paper_id}.{format_name}"
    if format_name == "pdf":
        output_path = paper_renderer.generator.render_pdf(paper.paper_json, output_path)
    else:
        output_path = paper_renderer.generator.render_docx(paper.paper_json, output_path)

    audit = ExportAudit(
        paper_id=paper_id,
        approved_version=approved_version_id,
        exported_by=user_id,  # ← authenticated user, never "system"
        format=format_name,
    )
    db.add(audit)
    # NOTE: an approved paper is NOT mutated on export — it remains
    # "approved" and can be exported again (each export writes a fresh
    # ExportAudit row). The paper is never regenerated here.
    await db.commit()

    # User-facing download filename is derived from the paper's persisted
    # subject (paper_json["subject_name"], set by both the legacy and
    # composite assembly paths) so it is recognizable in the browser download
    # dialog. The on-disk path stays UUID-based to avoid collisions between
    # concurrent exports of the same paper.
    paper_json = paper.paper_json or {}
    subject = paper_json.get("subject_name") if isinstance(paper_json, dict) else None
    filename = build_export_filename(subject, format_name)
    media_type = EXPORT_MEDIA_TYPES[format_name]
    return str(output_path), filename, media_type


@router.post("/export", dependencies=[Depends(require_roles("faculty", "admin"))])
async def export_paper(
    request: PaperDocumentExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Prepare an approved paper export and record the export in ExportAudit.

    Returns the server-side file path and format. The browser download uses
    ``GET /api/papers/export/download`` which streams the actual file.
    """
    try:
        await ensure_paper_access(request.paper_id, current_user, db)
        file_path, _, _ = await _render_approved_export(
            request.paper_id, request.format, current_user.user_id, db
        )
        return {"file_path": file_path, "format": request.format}
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/export/download", dependencies=[Depends(require_roles("faculty", "admin"))])
async def download_exported_paper(
    paper_id: str,
    format: Literal["pdf", "docx"],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Stream an approved paper's PDF/DOCX to the browser for download.

    Uses the correct MIME type and an attachment filename so the browser
    downloads the file instead of displaying a server path.
    """
    try:
        await ensure_paper_access(paper_id, current_user, db)
        file_path, filename, media_type = await _render_approved_export(
            paper_id, format, current_user.user_id, db
        )
        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=filename,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

@router.get("/recent")
async def recent_papers(
    q: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    creator_id: str | None = None,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Recent papers from PostgreSQL only (no in-memory state).

    ``GeneratedPaper`` has no timestamp or subject columns of its own, so the
    ordering key comes from its ``GenerationJob.created_at`` and the summary
    metadata (subject / exam type / marks / duration) comes from the
    ``PaperVersion.paper_json`` — both persisted, both authoritative.
    """
    from sqlalchemy import select, desc, func
    from app.models.generation import GeneratedPaper, GenerationJob, PaperVersion

    is_admin = False
    roles = getattr(current_user, "roles", None) or []
    role_val = getattr(current_user, "role", None)
    names = {getattr(x, "name", x) for x in roles} if isinstance(roles, list) else set()
    if "admin" in names or (isinstance(role_val, str) and role_val.lower() == "admin"):
        is_admin = True

    stmt = (
        select(GeneratedPaper, GenerationJob.created_at)
        .outerjoin(GenerationJob, GeneratedPaper.generation_job_id == GenerationJob.id)
    )
    # Privacy: faculty see their own papers; admin sees all (existing RBAC).
    if not is_admin:
        stmt = stmt.where(GeneratedPaper.created_by == current_user.user_id)
    elif creator_id:
        stmt = stmt.where(GeneratedPaper.created_by == creator_id)
    if status_filter:
        stmt = stmt.where(GeneratedPaper.status == status_filter)
    if q:
        stmt = stmt.where(GeneratedPaper.title.ilike(f"%{q}%"))
    # Newest first; papers without a job timestamp sort last, deterministically.
    stmt = stmt.order_by(GenerationJob.created_at.desc().nullslast()).limit(20)
    res = await db.execute(stmt)
    rows = res.all()
    papers = [row[0] for row in rows]
    job_times = {str(row[0].id): row[1] for row in rows}

    # Load the current versions (fallback: latest version per paper).
    version_ids = [p.current_version_id for p in papers if p.current_version_id]
    versions_by_id: dict = {}
    if version_ids:
        vres = await db.execute(select(PaperVersion).where(PaperVersion.id.in_(version_ids)))
        versions_by_id = {v.id: v for v in vres.scalars()}

    def _meta(paper: GeneratedPaper) -> dict:
        version = versions_by_id.get(paper.current_version_id) if paper.current_version_id else None
        pj = (version.paper_json or {}) if version is not None else {}
        if not isinstance(pj, dict):
            pj = {}
        subject = pj.get("subject_name")
        exam_type = pj.get("exam_name")
        if not subject:
            # Legacy fallback: title is "<exam_type> - <subject>".
            title = paper.title or ""
            parts = title.split(" - ", 1)
            if len(parts) == 2:
                exam_type, subject = parts[0], parts[1]
            else:
                subject = title
        return {
            "subject": subject,
            "exam_type": exam_type,
            "total_marks": pj.get("total_marks"),
            "duration_minutes": pj.get("duration_minutes"),
        }

    result = []
    for p in papers:
        ts = job_times.get(str(p.id))
        created_at = ts.isoformat() if ts else None
        result.append({
            "id": str(p.id),
            "title": p.title,
            **_meta(p),
            "status": p.status,
            "created_at": created_at,
            "updated_at": created_at,
        })
    return result
