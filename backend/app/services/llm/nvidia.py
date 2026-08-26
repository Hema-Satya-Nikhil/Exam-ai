from __future__ import annotations

import asyncio
import json

import httpx

from app.core.config import settings
from app.schemas.academic import QuestionRequirement
from app.services.llm.provider import LLMProvider


class NVIDIAProvider(LLMProvider):
    def __init__(self) -> None:
        self.base_url = settings.nvidia_base_url.rstrip("/")
        self.api_key = settings.nvidia_api_key
        self.model = settings.nvidia_model
        self.timeout = settings.llm_timeout
        self.max_retries = settings.llm_max_retries

    def _ensure_configured(self) -> None:
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY is not configured.")
        if not self.model:
            raise ValueError("NVIDIA_MODEL is not configured.")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _post_chat_completion(self, messages: list[dict[str, str]], schema_hint: str) -> dict:
        self._ensure_configured()


        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 1200,
            "response_format": {"type": "json_object"},
        }
        url = f"{self.base_url}/chat/completions"

        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.post(url, headers=self._headers(), json=payload)
                    response.raise_for_status()
                    body = response.json()
                    content = body["choices"][0]["message"]["content"]
                    return json.loads(content)
                except (httpx.HTTPError, KeyError, json.JSONDecodeError) as exc:
                    last_error = exc
                    if attempt >= self.max_retries:
                        break
                    await asyncio.sleep(min(0.25 * (attempt + 1), 1.0))

        raise ValueError(f"NVIDIA request failed while generating {schema_hint}.") from last_error

    def _question_messages(self, requirement: QuestionRequirement, context: str) -> list[dict[str, str]]:
        bloom_verbs = {
            "L2": "Explain, Describe, Illustrate, Summarize",
            "L3": "Apply, Calculate, Solve, Demonstrate",
            "L4": "Analyze, Compare, Contrast, Differentiate",
            "L5": "Evaluate, Justify, Assess, Criticize",
            "L6": "Design, Formulate, Construct, Create",
        }
        target_verbs = bloom_verbs.get(requirement.bloom_level, "Explain, Describe")
        return [
            {
                "role": "system",
                "content": (
                    "You are an academic question generation engine for departmental examinations. "
                    "You MUST follow all supplied blueprint rules strictly. "
                    "Never alter question number, marks, unit, section, topic, or Bloom level. "
                    "Return ONLY a JSON object with 'question_text' (string) and 'source_references' (array of objects)."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate question {requirement.question_number} for section '{requirement.section}'.\n"
                    f"Marks: {requirement.marks}\n"
                    f"Unit: {requirement.unit}\n"
                    f"Topic: {requirement.topic}\n"
                    f"Bloom Level: {requirement.bloom_level} (Use verbs such as: {target_verbs})\n"
                    f"Difficulty: {requirement.difficulty}\n"
                    f"Question Type: {requirement.question_type}\n"
                    f"Context & Source Materials: {context}"
                ),
            },
        ]

    def _analysis_messages(self, paper_text: str) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You analyze model question papers and return only JSON. "
                    "Extract exam title, subject, total marks, duration, section structure, numbering, and Bloom hints."
                ),
            },
            {"role": "user", "content": paper_text},
        ]

    async def generate_question(self, requirement: QuestionRequirement, source_context: str) -> dict:
        result = await self._post_chat_completion(self._question_messages(requirement, source_context), "question generation")
        result.setdefault("question_id", "placeholder")
        result.setdefault("marks", requirement.marks)
        result.setdefault("unit", requirement.unit)
        result.setdefault("topic", requirement.topic)
        result.setdefault("bloom_level", requirement.bloom_level)
        result.setdefault("difficulty", requirement.difficulty)
        result.setdefault("question_type", requirement.question_type)
        result.setdefault("source_references", [])
        return result

    async def analyze_model_paper(self, paper_text: str) -> dict:
        return await self._post_chat_completion(self._analysis_messages(paper_text), "model paper analysis")

    async def regenerate_question(self, requirement: QuestionRequirement, previous_question: str, failure_reason: str) -> dict:
        context = f"Previous question: {previous_question}. Failure reason: {failure_reason}."
        return await self.generate_question(requirement, context)
