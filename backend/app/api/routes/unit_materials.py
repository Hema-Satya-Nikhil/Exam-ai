from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.core.config import settings
from app.services.document_ingestion_service import DocumentIngestionService

router = APIRouter()
document_service = DocumentIngestionService()


@router.post("/upload")
async def upload_unit_material(
    syllabus_id: str = Form("default"),
    unit_number: int = Form(...),
    file: UploadFile = File(...),
) -> dict[str, object]:
    try:
        data = await file.read()
        extracted = document_service.extract(file.filename, file.content_type or "application/octet-stream", data, settings.max_upload_size)
        return {
            "syllabus_id": syllabus_id,
            "unit_number": unit_number,
            "file_name": file.filename,
            "extracted_text": extracted.text,
            "warnings": extracted.warnings,
            "page_references": extracted.page_references,
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
