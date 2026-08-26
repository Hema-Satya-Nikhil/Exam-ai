from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.core.config import settings
from app.schemas.syllabus import SyllabusUploadRequest
from app.services.document_ingestion_service import DocumentIngestionService
from app.services.syllabus_service import SyllabusService

router = APIRouter()
document_service = DocumentIngestionService()
syllabus_service = SyllabusService()


@router.post("/upload")
async def upload_syllabus(subject_id: str = Form(...), file: UploadFile = File(...)) -> dict[str, object]:
    try:
        data = await file.read()
        extracted = document_service.extract(file.filename, file.content_type or "application/octet-stream", data, settings.max_upload_size)
        parsed = syllabus_service.parse_text(extracted.text, file.filename)
        return {
            "subject_id": subject_id,
            "source_file_name": file.filename,
            "warnings": extracted.warnings + parsed.notes,
            "parsed": parsed.model_dump(),
            "page_references": extracted.page_references,
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/parse")
async def parse_syllabus(request: SyllabusUploadRequest) -> dict[str, object]:
    parsed = syllabus_service.parse_text(request.extracted_text, request.file_name)
    return parsed.model_dump()
