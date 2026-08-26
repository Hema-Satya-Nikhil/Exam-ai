from __future__ import annotations

from app.services.blueprint_service import BlueprintService
from app.services.documents.generator import DocumentGenerator
from app.services.validation_service import ValidationService


def get_blueprint_service() -> BlueprintService:
    return BlueprintService()


def get_validation_service() -> ValidationService:
    return ValidationService()


def get_document_generator() -> DocumentGenerator:
    return DocumentGenerator()
