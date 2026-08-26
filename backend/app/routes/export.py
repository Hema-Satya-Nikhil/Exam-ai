from fastapi import APIRouter, Query, FileResponse, HTTPException
from typing import Optional
from pydantic import BaseModel
from datetime import datetime

from ..services.export_service import ExportService, ExportFormat
from ..models.export_audit import ExportAudit

router = APIRouter(prefix="/papers", tags=["exports"])


class ExportRequest(BaseModel):
    format: ExportFormat

@router.get("/{paper_id}/export")
async def export_paper(
    paper_id: str,
    request: ExportRequest = Depends(),
    user_id: str = Query(..., example="user-123")
) -> FileResponse:
    """
    Export a paper to the requested format
    """
    export_service = ExportService(
        paper_repository=...,  # Placeholder for actual repository
        audit_repository=...   # Placeholder for actual repository
    )
    
    file_content = await export_service.export_paper(paper_id, request.format, user_id)
    
    # Determine filename and content type
    if request.format == ExportFormat.pdf:
        filename = f"paper_{paper_id}.pdf"
        content_type = "application/pdf"
    else:
        filename = f"paper_{paper_id}.docx"
        content_type = "application/vnd.openxmlformats-officedocuments.wordprocessingml.document"
    
    return FileResponse(
        content=file_content,
        media_type=content_type,
        filename=filename
    )