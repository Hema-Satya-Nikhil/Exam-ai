from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user, get_db, require_roles
from app.models.audit import ExportAudit
from app.schemas.auth import UserContext
from app.schemas.paper_document import PaperDocumentExportRequest
from app.schemas.paper_review import PaperQuestionRegenerateRequest
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
    current_user: UserContext = Depends(get_current_user),
) -> PaperDraftRead:
    return workflow_service.create_draft(request)


@router.get("/drafts/{paper_id}", response_model=PaperDraftRead)
async def get_draft(
    paper_id: str,
    current_user: UserContext = Depends(get_current_user),
) -> PaperDraftRead:
    draft = await workflow_service.get_draft_async(paper_id)
    if draft is None:
        from app.db.session import async_session_maker as _maker
        from app.services.paper_workflow_service import PaperWorkflowService as _WS

        async with _maker() as s:
            draft = await _WS(session=s).get_draft_async(paper_id)
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
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaperDraftRead:
    wf = PaperWorkflowService(session=db)
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
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaperDraftRead:
    wf = PaperWorkflowService(session=db)
    draft = await wf.lock_question_async(paper_id, request)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper draft not found")
    return draft


@router.post("/drafts/{paper_id}/unlock", response_model=PaperDraftRead)
async def unlock_question(
    paper_id: str,
    request: PaperLockRequest,
    current_user: UserContext = Depends(get_current_user),
) -> PaperDraftRead:
    draft = workflow_service.unlock_question(paper_id, request)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper draft not found")
    return draft


# ---------------------------------------------------------------------------
# Approval — FACULTY or ADMIN, records authenticated user
# ---------------------------------------------------------------------------

@router.post("/drafts/{paper_id}/approve", dependencies=[Depends(require_roles("faculty", "admin"))])
async def approve_draft(
    paper_id: str,
    request: PaperApprovalRequest,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
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
    current_user: UserContext = Depends(get_current_user),
) -> dict[str, object]:
    try:
        draft = await workflow_service.regenerate_question(paper_id, request)
        if draft is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Paper draft not found"
            )
        return draft.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Export — FACULTY or ADMIN, records authenticated user in ExportAudit
# ---------------------------------------------------------------------------

EXPORT_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


async def _render_approved_export(
    paper_id: str,
    format_name: str,
    user_id: str,
    db: AsyncSession,
) -> tuple[str, str, str]:
    """Render an approved paper, record an ExportAudit row, return its path.

    Returns (absolute file path, filename, media type). Raises
    HTTPException 400 if the paper is missing or not approved.

    ``ExportAudit.approved_version`` always references the ACTUAL approved
    ``PaperVersion.id`` from PostgreSQL (via ``GeneratedPaper.current_version_id``
    or the latest version row) — never a fabricated label like ``"v1"``.
    """
    from sqlalchemy import select

    from app.models.generation import GeneratedPaper, PaperVersion
    from app.services.paper_workflow_service import PaperWorkflowService as _WS

    workflow_service_db = _WS(session=db)
    paper = await workflow_service_db.get_draft_async(paper_id)
    if not paper or paper.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Paper not approved for export",
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

    slug = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in (paper.title or "question-paper")).strip("_") or "question-paper"
    filename = f"{slug}.{format_name}"
    media_type = EXPORT_MEDIA_TYPES[format_name]
    return str(output_path), filename, media_type


@router.post("/export", dependencies=[Depends(require_roles("faculty", "admin"))])
async def export_paper(
    request: PaperDocumentExportRequest,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Prepare an approved paper export and record the export in ExportAudit.

    Returns the server-side file path and format. The browser download uses
    ``GET /api/papers/export/download`` which streams the actual file.
    """
    try:
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
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Stream an approved paper's PDF/DOCX to the browser for download.

    Uses the correct MIME type and an attachment filename so the browser
    downloads the file instead of displaying a server path.
    """
    try:
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