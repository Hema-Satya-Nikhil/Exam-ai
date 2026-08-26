from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_db
from app.core.config import settings
from app.schemas.syllabus import (
    SyllabusConfirmRequest,
    SyllabusConfirmResult,
    SyllabusUploadRequest,
)
from app.services.document_ingestion_service import DocumentIngestionService
from app.services.syllabus_service import (
    SyllabusService,
    persist_confirmed_syllabus,
)

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
            "warnings": extracted.warnings + parsed.warnings,
            "parsed": parsed.model_dump(),
            "page_references": extracted.page_references,
            "ocr_used": extracted.ocr_used,
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/parse")
async def parse_syllabus(request: SyllabusUploadRequest) -> dict[str, object]:
    parsed = syllabus_service.parse_text(request.extracted_text, request.file_name)
    return parsed.model_dump()


def _validate_no_duplicate_unit_numbers(units: list["SyllabusConfirmUnit"]) -> None:
    numbers = [u.unit_number for u in units]
    if len(numbers) != len(set(numbers)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate unit numbers are not allowed.")


@router.post("/confirm", response_model=SyllabusConfirmResult, status_code=status.HTTP_201_CREATED)
async def confirm_syllabus(
    request: SyllabusConfirmRequest,
    db: AsyncSession = Depends(get_db),
) -> SyllabusConfirmResult:
    """Persist a faculty-confirmed syllabus structure.

    ``POST /syllabi/confirm`` is only meaningful *after* a faculty member has
    reviewed the proposed structure produced by the upload/parse pipeline and
    explicitly confirmed it (editing titles/topics as needed). Until this
    endpoint is called the proposed structure is not authoritative.
    """
    if not request.units:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot confirm an empty syllabus.")
    # Validate ordering / duplicate unit numbers before persisting.
    _validate_no_duplicate_unit_numbers(request.units)
    version_id = await persist_confirmed_syllabus(
        db, request.subject_id, request.source_file_name, request.units
    )
    return SyllabusConfirmResult(
        syllabus_version_id=version_id,
        subject_id=request.subject_id,
        source_file_name=request.source_file_name,
        units=request.units,
    )
