from fastapi import APIRouter

from app.core.dependencies import get_blueprint_service, get_validation_service
from app.schemas.academic import PaperBlueprint

router = APIRouter()


@router.post("/validate")
async def validate_blueprint(blueprint: PaperBlueprint) -> dict[str, object]:
    blueprint_service = get_blueprint_service()
    validation_service = get_validation_service()
    normalized = blueprint_service.normalize_blueprint(blueprint)
    feasibility_issues = blueprint_service.validate_feasibility(normalized)
    validation = validation_service.validate_blueprint(normalized)
    return {
        "feasibility_issues": feasibility_issues,
        "validation": validation.model_dump(),
    }
