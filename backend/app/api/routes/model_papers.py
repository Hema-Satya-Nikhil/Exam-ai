from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.config import settings
from app.schemas.model_paper import ModelPaperAnalyzeRequest
from app.services.document_ingestion_service import DocumentIngestionService
from app.services.model_paper_service import ModelPaperService

router = APIRouter()
document_service = DocumentIngestionService()
model_paper_service = ModelPaperService()


@router.post("/upload")
async def upload_model_paper(file: UploadFile = File(...)) -> dict[str, object]:
    try:
        data = await file.read()
        extracted = document_service.extract(file.filename, file.content_type or "application/octet-stream", data, settings.max_upload_size)
        result = model_paper_service.analyze(extracted.text)
        return {
            "source_file_name": file.filename,
            "warnings": extracted.warnings,
            "page_references": extracted.page_references,
            "analysis": result.model_dump(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/analyze")
async def analyze_model_paper(request: ModelPaperAnalyzeRequest) -> dict[str, object]:
    result = model_paper_service.analyze(request.extracted_text)
    return result.model_dump()
