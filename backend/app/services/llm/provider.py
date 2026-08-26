from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.academic import QuestionRequirement


class LLMProvider(ABC):
    @abstractmethod
    async def generate_question(self, requirement: QuestionRequirement, source_context: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def analyze_model_paper(self, paper_text: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def regenerate_question(self, requirement: QuestionRequirement, previous_question: str, failure_reason: str) -> dict:
        raise NotImplementedError
