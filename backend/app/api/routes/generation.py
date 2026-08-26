from fastapi import APIRouter, HTTPException, status

from app.schemas.generation import BatchGenerationResult, GenerationJobCreate, GenerationJobRead, QuestionGenerationRequest
from app.services.generation_service import GenerationService

router = APIRouter()
generation_service = GenerationService()


@router.post("/jobs", response_model=GenerationJobRead, status_code=status.HTTP_201_CREATED)
async def create_generation_job(request: GenerationJobCreate) -> GenerationJobRead:
    return generation_service.create_job(request)


@router.get("/jobs/{job_id}", response_model=GenerationJobRead)
async def get_generation_job(job_id: str) -> GenerationJobRead:
    job = generation_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation job not found")
    return job


@router.post("/questions/generate")
async def generate_single_question(request: QuestionGenerationRequest) -> dict[str, object]:
    try:
        result = await generation_service.generate_single_question(request.requirement, request.source_context)
        return result.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/papers/generate", response_model=BatchGenerationResult)
async def generate_paper(request: GenerationJobCreate) -> BatchGenerationResult:
    try:
        return await generation_service.generate_paper_from_blueprint(request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
