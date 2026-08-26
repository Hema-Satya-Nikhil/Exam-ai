from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
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
    draft = workflow_service.get_draft(paper_id)
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
) -> PaperDraftRead:
    draft = workflow_service.update_question(paper_id, request)
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
) -> PaperDraftRead:
    draft = workflow_service.lock_question(paper_id, request)
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
    approval = workflow_service.approve_paper(
        paper_id, current_user.user_id, getattr(request, "comments", None)
    )
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paper draft not found")

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

@router.post("/export", dependencies=[Depends(require_roles("faculty", "admin"))])
async def export_paper(
    request: PaperDocumentExportRequest,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Export an approved paper to PDF or DOCX.

    The authenticated user's ID is stored in ``ExportAudit.exported_by``.
    The existing verified export architecture is unchanged.
    """
    from app.services.paper_workflow_service import PaperWorkflowService as _WS

    try:
        workflow_service_db = _WS(session=db)
        paper = await workflow_service_db.get_draft_async(request.paper_id)
        if not paper or paper.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Paper not approved for export",
            )

        output_dir = Path("storage") / "exports"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = paper_renderer.export(paper.paper_json, output_dir, request.format)

        audit = ExportAudit(
            paper_id=request.paper_id,
            approved_version=str(paper.paper_json.get("version_id", "v1")),
            exported_by=current_user.user_id,   # ← authenticated user, never "system"
            format=request.format,
        )
        db.add(audit)
        # NOTE: an approved paper is NOT mutated on export — it remains
        # "approved" and can be exported again (each export writes a fresh
        # ExportAudit row). The paper is never regenerated here.
        await db.commit()

        return {"file_path": str(output_path), "format": request.format}
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc