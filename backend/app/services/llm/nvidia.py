from __future__ import annotations

import asyncio
import json
import logging
import re
import time

import httpx

from app.core.config import settings
from app.schemas.academic import QuestionRequirement
from app.services.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NVIDIA HTTP transport budget (provider-scoped; no other subsystem affected).
#
# Measured production latency for one question: ~54 s (2-mark) to ~80 s
# (10-mark analytical), scaling with output length. The previous single 90 s
# read timeout sat inside that band and caused intermittent ReadTimeouts that
# aborted whole papers. 240 s gives comfortable headroom while remaining a
# bounded, finite timeout — nothing here is infinite.
# ---------------------------------------------------------------------------
CONNECT_TIMEOUT_S = 10.0
READ_TIMEOUT_S = 240.0
WRITE_TIMEOUT_S = 30.0
POOL_TIMEOUT_S = 10.0

# Completion budget. The previous 1200-token ceiling sat directly inside the
# band where long 10-mark analytical completions land (~1100 tokens measured),
# so the model intermittently returned HTTP 200 with EMPTY/null content once
# the budget was exhausted mid-generation. 4096 removes that ceiling while
# staying a bounded, finite request parameter.
MAX_COMPLETION_TOKENS = 4096

# Compact-prompt retry: target size for the condensed source-context block used
# from the second attempt onwards when a response came back incomplete.
COMPACT_CONTEXT_TARGET_CHARS = 1600


class _IncompleteGeneration(Exception):
    """HTTP 200 was received but the assistant turn carries no usable content.

    Two distinct upstream shapes map here:

    * ``empty_content``   – ``choices[0].message.content`` is null/blank.
    * ``length_truncation``– ``finish_reason == "length"`` (the completion hit
      ``max_tokens`` before finishing).

    Both are treated as *incomplete generations*, not hard failures: the caller
    retries with an adjusted (compacted) prompt instead of resending the exact
    same request that just failed.
    """

    def __init__(self, failure_class: str, finish_reason: str | None = None) -> None:
        self.failure_class = failure_class
        self.finish_reason = finish_reason
        super().__init__(failure_class)


async def _sleep(seconds: float) -> None:
    """Indirection over ``asyncio.sleep`` so tests can short-circuit backoff."""
    await asyncio.sleep(seconds)


class NVIDIAProvider(LLMProvider):
    def __init__(self) -> None:
        self.base_url = settings.nvidia_base_url.rstrip("/")
        self.api_key = settings.nvidia_api_key
        self.model = settings.nvidia_model
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

    async def _post_chat_completion(
        self,
        messages: list[dict[str, str]],
        schema_hint: str,
        *,
        messages_for_attempt=None,
        marks: int | None = None,
    ) -> dict:
        """POST one chat-completion request with bounded retries.

        ``messages_for_attempt(attempt)`` optionally rebuilds the prompt for a
        given attempt number; when a response comes back *incomplete* (empty
        content or ``finish_reason == "length"``) the next attempt uses the
        compacted variant instead of resending the identical request.
        """
        self._ensure_configured()

        url = f"{self.base_url}/chat/completions"
        # Finite, role-split timeouts: generous read budget for long
        # completions, tight connect/write/pool so real network faults still
        # surface quickly.
        timeout = httpx.Timeout(
            CONNECT_TIMEOUT_S, read=READ_TIMEOUT_S, write=WRITE_TIMEOUT_S, pool=POOL_TIMEOUT_S
        )

        total_attempts = self.max_retries + 1
        last_error: Exception | None = None

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(1, total_attempts + 1):
                current_messages = (
                    messages_for_attempt(attempt) if messages_for_attempt else messages
                )
                payload = {
                    "model": self.model,
                    "messages": current_messages,
                    "temperature": 0.2,
                    "max_tokens": MAX_COMPLETION_TOKENS,
                    "response_format": {"type": "json_object"},
                }
                started = time.perf_counter()

                def _telemetry(level: str, failure_class: str, finish_reason, content_present) -> None:
                    duration = time.perf_counter() - started
                    message = (
                        "nvidia %s %s attempt=%d/%d marks=%s max_tokens=%d "
                        "duration_s=%.1f finish_reason=%s content_present=%s failure_class=%s"
                    )
                    args = (
                        schema_hint, level, attempt, total_attempts,
                        "-" if marks is None else marks, MAX_COMPLETION_TOKENS,
                        duration, finish_reason, content_present, failure_class,
                    )
                    (logger.info if level == "ok" else logger.warning)(message, *args)

                try:
                    response = await client.post(url, headers=self._headers(), json=payload)
                    response.raise_for_status()
                    body = response.json()
                    choice = body["choices"][0]
                    content = choice["message"].get("content")
                    finish_reason = choice.get("finish_reason")
                    content_present = isinstance(content, str) and bool(content.strip())

                    # Incomplete generation: HTTP 200 but nothing usable came
                    # back. Retry with an adjusted request rather than failing.
                    if not content_present:
                        raise _IncompleteGeneration("empty_content", finish_reason) from None
                    if finish_reason == "length":
                        raise _IncompleteGeneration("length_truncation", finish_reason) from None

                    match = re.search(r"^\s*```(?:json)?\s*(.*?)```\s*$", content, flags=re.DOTALL)
                    if match:
                        content = match.group(1)
                    parsed = json.loads(content)
                    _telemetry("ok", "-", finish_reason, True)
                    return parsed
                except _IncompleteGeneration as exc:
                    last_error = exc
                    reason = f"incomplete response ({exc.failure_class})"
                    _telemetry(
                        "failed", exc.failure_class, exc.finish_reason,
                        exc.failure_class != "empty_content",
                    )
                except httpx.TimeoutException as exc:
                    last_error = exc
                    reason = f"read/write timeout after {READ_TIMEOUT_S:.0f}s"
                    _telemetry("failed", "read_write_timeout", None, False)
                except httpx.HTTPStatusError as exc:
                    last_error = exc
                    reason = f"HTTP {exc.response.status_code}"
                    _telemetry("failed", f"http_{exc.response.status_code}", None, False)
                except httpx.HTTPError as exc:
                    last_error = exc
                    reason = type(exc).__name__
                    _telemetry("failed", type(exc).__name__, None, False)
                except KeyError as exc:
                    last_error = exc
                    reason = f"unexpected response shape (missing {exc})"
                    _telemetry("failed", "unexpected_shape", None, False)
                except json.JSONDecodeError as exc:
                    last_error = exc
                    reason = f"invalid JSON ({exc.msg})"
                    _telemetry("failed", "malformed_json", None, True)

                # Sanitized telemetry only: attempt number and failure class.
                # Never the API key, Authorization header, prompt, or syllabus text.
                logger.warning("nvidia %s attempt %d/%d failed after %.1fs: %s",
                               schema_hint, attempt, total_attempts,
                               time.perf_counter() - started, reason)
                if attempt >= total_attempts:
                    break
                # Small exponential backoff so an immediate duplicate request
                # doesn't hammer a struggling endpoint.
                await _sleep(min(1.5 * 2 ** (attempt - 1), 8.0))

        raise ValueError(f"NVIDIA request failed while generating {schema_hint}.") from last_error

    def _compact_context(self, context: str, requirement: QuestionRequirement) -> str:
        """Condense the source-context block without losing syllabus scope.

        Keeps: the structured header lines (Subject/Exam/Units), the
        unit-material availability statement, every sentence mentioning the
        requirement's topic or its unit, and — so scope is never silently
        dropped when nothing matches — a bounded tail of the original text.
        Only redundant/repeated filler is removed.
        """
        if not context:
            return context
        segments = [s.strip() for s in re.split(r"\n+|(?<=[.;])\s+", context) if s.strip()]
        if sum(len(s) for s in segments) <= COMPACT_CONTEXT_TARGET_CHARS:
            return context

        topic_tokens = {
            t for t in re.findall(r"[a-z0-9]+", requirement.topic.lower()) if len(t) > 2
        }
        unit_markers = (
            f"unit {requirement.unit}",
            f"unit:{requirement.unit}",
            f"units: {requirement.unit}",
        )

        kept: list[str] = []
        seen: set[str] = set()
        fallback_tail: list[str] = []
        for segment in segments:
            key = " ".join(segment.lower().split())
            if key in seen:
                continue  # drop exact-duplicate / repeated filler
            seen.add(key)
            low = segment.lower()
            is_header = low.startswith(("subject:", "exam:", "units:", "unit materials"))
            hit = any(t in low for t in topic_tokens) or any(m in low for m in unit_markers)
            if is_header or hit:
                kept.append(segment)
            elif len("\n".join(fallback_tail)) < COMPACT_CONTEXT_TARGET_CHARS // 2:
                fallback_tail.append(segment)

        compacted = kept + fallback_tail[: max(1, len(fallback_tail) // 2)]
        result = " ".join(compacted)
        # Never return something emptier than a bounded slice of the original.
        if len(result.strip()) < 40:
            result = context[:COMPACT_CONTEXT_TARGET_CHARS]
        return result

    def _question_messages(
        self,
        requirement: QuestionRequirement,
        context: str,
        feedback: str | None = None,
        *,
        compact: bool = False,
    ) -> list[dict[str, str]]:
        bloom_verbs = {
            "L2": "Explain, Describe, Illustrate, Summarize",
            "L3": "Apply, Calculate, Solve, Demonstrate",
            "L4": "Analyze, Compare, Contrast, Differentiate",
            "L5": "Evaluate, Justify, Assess, Criticize",
            "L6": "Design, Formulate, Construct, Create",
        }
        target_verbs = bloom_verbs.get(requirement.bloom_level, "Explain, Describe")
        # State the length rule up front so the model complies on the first
        # attempt instead of failing post-generation validation.
        length_rule = (
            "\nLength: at most 45 words — 2-mark questions must be concise."
            if requirement.marks <= 2
            else ""
        )
        correction = (
            f"\n\nYour previous attempt violated these rules:\n{feedback}\n"
            "Regenerate the question so it complies with every rule above."
            if feedback else ""
        )
        effective_context = (
            self._compact_context(context, requirement) if compact else context
        )
        compact_note = (
            "\nNOTE: The context below is condensed to the parts relevant to this "
            "question. All blueprint constraints (marks, unit, topic, Bloom level, "
            "difficulty, question type) remain fully binding."
            if compact else ""
        )
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
                    f"Question Type: {requirement.question_type}"
                    f"{length_rule}\n"
                    f"{compact_note}"
                    f"Context & Source Materials: {effective_context}"
                    f"{correction}"
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

    async def generate_question(
        self,
        requirement: QuestionRequirement,
        source_context: str,
        feedback: str | None = None,
    ) -> dict:
        # Deterministic stub for tests/E2E: LLM_STUB=1 short-circuits the network
        # call so the review->approve->export pipeline can be verified without
        # depending on live model latency/availability. Returns a question that
        # passes the validator (non-empty text).
        if settings.llm_stub:
            return {
                "question_text": (
                    f"Canned stub question for {requirement.topic} "
                    f"(section {requirement.section}, marks {requirement.marks})."
                ),
                "source_references": [{"title": "Stub source", "page": 1}],
            }
        def _messages_for_attempt(attempt: int) -> list[dict[str, str]]:
            # Attempt 1: the normal prompt. Attempts 2+: same semantic
            # constraints (marks / unit / topic / Bloom / difficulty /
            # question type / required JSON schema all retained verbatim),
            # but with a COMPACTED context block so an incomplete generation
            # is retried with an adjusted request instead of the identical
            # payload that just came back empty or token-capped.
            return self._question_messages(
                requirement, source_context, feedback,
                compact=attempt > 1,
            )

        result = await self._post_chat_completion(
            self._question_messages(requirement, source_context, feedback),
            "question generation",
            messages_for_attempt=_messages_for_attempt,
            marks=requirement.marks,
        )
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
