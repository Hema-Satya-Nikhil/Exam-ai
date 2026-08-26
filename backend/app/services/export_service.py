# Service for handling paper export functionality

from enum import Enum
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
import datetime
import io
from backend.app.services.pdf_renderer import PDFRenderer
from backend.app.services.docx_renderer import DOCXRenderer
from ..repositories.paper_workflow_repository import PaperWorkflowRepository
from ..repositories.export_audit_repository import ExportAuditRepository
from ..repositories.generation_repository import GeneratedPaper
from ..schemas.export_audit import ExportAuditModel

class ExportFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"

class ExportRequest(BaseModel):
    format: ExportFormat
    paper_id: str

class ExportService:
    def __init__(self, paper_repo: PaperRepository, export_audit_repo: ExportAuditRepository, pdf_renderer: PDFRenderer, docx_renderer: DOCXRenderer):
        self.paper_repo = paper_repo
        self.export_audit_repo = export_audit_repo
        self.pdf_renderer = pdf_renderer
        self.docx_renderer = docx_renderer

    async def export_paper(self, paper_id: str, format: ExportFormat, user_id: str) -> bytes:
        # Check if paper exists and is approved
        paper = await self.paper_repo.get_by_id(paper_id)
        if not paper or paper.status != GeneratedPaperStatus.APPROVED:
            raise HTTPException(status_code=404, detail="Paper not approved for export")

        # Load approved content from MongoDB
        content = paper.content  # Assuming content is stored in the Paper model

        # Create audit record
        audit = ExportAuditModel(
            paper_id=paper_id,
            approved_version=paper.version,
            exported_by=user_id,
            format=format.name
        )
        self.export_audit_repo.save(audit)

        # Pass content to renderer
        if format == ExportFormat.PDF:
            return self.pdf_renderer.render(content)
        elif format == ExportFormat.DOCX:
            return self.docx_renderer.render(content)