from __future__ import annotations

from app.schemas.academic import PaperBlueprint


class BlueprintService:
    def normalize_blueprint(self, blueprint: PaperBlueprint) -> PaperBlueprint:
        return blueprint

    def validate_feasibility(self, blueprint: PaperBlueprint) -> list[str]:
        issues: list[str] = []
        if blueprint.total_marks <= 0:
            issues.append("Total marks must be positive.")
        if not blueprint.sections:
            issues.append("At least one section is required.")
        return issues
