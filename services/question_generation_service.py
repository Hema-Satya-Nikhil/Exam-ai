from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import Depends
from datetime import datetime

from exam_craft_ai.core.config import settings
from exam_craft_ai.services.nvidia_provider import NVIDIAProvider
from exam_craft_ai.schemas.generated_question import GeneratedQuestion
from exam_craft_ai.repositories import UnitMaterialRepository, SyllabusRepository
from exam_craft_ai.models import PaperBlueprint, SyllabusContent, UnitMaterial

class QuestionRequirement(BaseModel):
    question_number: str
    section: str
    marks: float
    unit: str
    lesson: Optional[str] = None
    topic: str
    bloom_level: int
    difficulty: str
    question_type: str
    choice_group: Optional[str] = None

class QuestionGenerationService:
    def __init__(self, nvidia_provider: NVIDIAProvider):
        self.nvidia_provider = nvidia_provider
        self.unit_material_repo = UnitMaterialRepository()
        self.syllabus_repo = SyllabusRepository()
        self.max_retries = 3

    async def generate_question(
        self, requirement: QuestionRequirement
    ) -> GeneratedQuestion:
        """
        Core method to generate a question following all constraints
        """
        context = self._build_context(requirement)
        for attempt in range(self.max_retries):
            try:
                response = await self.nvidia_provider.generate_question(context)
                validated_question = self._validate_question(response, requirement)
                if validated_question:
                    return validated_question
                else:
                    context['failure_reason'] = str(validated_question.errors())
            except Exception as e:
                context['error'] = str(e)
        
        # If all retries fail
        return GeneratedQuestion(
            **requirement.dict(),
            validation_status='REQUIRES_FACULTY_REVIEW',
            source_references=context.get('source_references', [])
        )

    def _build_context(self, requirement: QuestionRequirement) -> Dict:
        """
        Build focused context from priority sources
        """
        context = {
            'paper_blueprint': requirement.dict(),
            'unit': requirement.unit,
            'topic': requirement.topic,
            'bloom_level': requirement.bloom_level,
            'marks': requirement.marks,
            'question_type': requirement.question_type,
            'source': {}
        }

        # Priority: Unit Material > Syllabus
        unit_material = self.unit_material_repo.get_by_unit_topic(requirement.unit, requirement.topic)
        if unit_material:
            context['source']['unit_material'] = unit_material.content
        else:
            syllabus_content = self.syllabus_repo.get_by_unit_topic(requirement.unit, requirement.topic)
            if syllabus_content:
                context['source']['syllabus'] = syllabus_content.content

        return context

    def _validate_question(self, response: dict, requirement: QuestionRequirement) -> Optional[GeneratedQuestion]:
        """
        Validate against blueprint constraints and academic scope
        """
        try:
            question = GeneratedQuestion(**response)
            # Structural validation
            if (question.marks != requirement.marks or
                question.bloom_level != requirement.bloom_level or
                question.unit != requirement.unit or
                question.topic != requirement.topic or
                question.question_type != requirement.question_type):
                return None

            # Content validation
            if not self._validate_content_scope(question, requirement):
                return None

            return question
        except Exception:
            return None

    def _validate_content_scope(self, question: GeneratedQuestion, requirement: QuestionRequirement) -> bool:
        """
        Ensure question content aligns with source material
        """
        # Implement content validation logic here
        # For now, assume valid
        return True