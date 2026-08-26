from app.schemas.academic import PaperBlueprint, PaperSectionSpec, QuestionRequirement
from app.services.blueprint_service import BlueprintService


def test_validate_feasibility_requires_sections_and_marks() -> None:
    blueprint = PaperBlueprint(
        exam_type="Mid 2",
        subject="Data Mining",
        selected_units=[3, 4, 5],
        total_marks=0,
        duration_minutes=180,
        sections=[],
        questions=[],
        source_mode="manual",
    )

    issues = BlueprintService().validate_feasibility(blueprint)

    assert "Total marks must be positive." in issues
    assert "At least one section is required." in issues
