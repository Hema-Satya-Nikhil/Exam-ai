"""Regression tests for the NVIDIA provider's incomplete-generation handling.

Covers the live-production failure mode where NVIDIA returns HTTP 200 but
``choices[0].message.content`` is null/empty (or ``finish_reason == "length"``).
The provider must treat those as *incomplete* and retry with a COMPACTED
prompt instead of resending the identical request.

The NVIDIA HTTP API is mocked at the transport level; no real network calls
and no LLM_STUB involvement.
"""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.core.config import settings
from app.schemas.academic import QuestionRequirement
from app.services.generation_service import GenerationService
from app.services.llm import nvidia as nvidia_module


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, body: dict, status_code: int = 200) -> None:
        self._body = body
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("POST", "https://unit.test/v1/chat/completions"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> dict:
        return self._body


class FakeAsyncClient:
    """Scripted transport: pops one entry per POST call.

    Entries are either ``Exception`` instances (raised instead of responding)
    or response body dicts.
    """

    script: list = []
    calls: list[dict] = []

    def __init__(self, timeout=None) -> None:  # noqa: ARG002 - mirrors httpx API
        pass

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *exc_info) -> bool:
        return False

    async def post(self, url, headers=None, json=None):  # noqa: A002
        FakeAsyncClient.calls.append(json)
        item = FakeAsyncClient.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)


async def _noop_sleep(_seconds: float) -> None:  # pragma: no cover - trivial
    return None


@pytest.fixture()
def provider_env(monkeypatch):
    """Configure the provider without touching the real environment file."""
    monkeypatch.setattr(settings, "nvidia_api_key", "unit-test-key")
    monkeypatch.setattr(settings, "nvidia_model", "unit-test-model")
    monkeypatch.setattr(settings, "llm_max_retries", 3)
    # Isolate the module's httpx namespace so the fake transport is used while
    # the real exception classes stay intact for `except` matching.
    monkeypatch.setattr(
        nvidia_module,
        "httpx",
        SimpleNamespace(
            AsyncClient=FakeAsyncClient,
            Timeout=httpx.Timeout,
            TimeoutException=httpx.TimeoutException,
            ReadTimeout=httpx.ReadTimeout,
            HTTPStatusError=httpx.HTTPStatusError,
            HTTPError=httpx.HTTPError,
            Request=httpx.Request,
            Response=httpx.Response,
        ),
    )
    # Short-circuit exponential backoff so exhausted-retry tests stay fast.
    monkeypatch.setattr(nvidia_module, "_sleep", _noop_sleep)
    FakeAsyncClient.calls = []
    yield


def chat_body(content="{}", finish_reason="stop") -> dict:
    return {
        "choices": [
            {"message": {"content": content}, "finish_reason": finish_reason}
        ],
        "usage": {"completion_tokens": 10},
    }


def requirement(marks: int = 5) -> QuestionRequirement:
    return QuestionRequirement(
        question_number=1,
        section="Section A",
        marks=marks,
        unit=2,
        topic="Process scheduling",
        bloom_level="L4",
        difficulty="medium",
        question_type="analytical",
    )


LONG_CONTEXT = (
    "Subject: OPERATING SYSTEMS. Exam: MID 1. Units: 1, 2.\n"
    + ("Filler sentence about unrelated syllabus material that repeats. " * 40)
)


# ---------------------------------------------------------------------------
# Provider-level tests
# ---------------------------------------------------------------------------


async def test_normal_successful_response(provider_env):
    FakeAsyncClient.script = [chat_body('{"question_text": "Q?"}')]
    result = await nvidia_module.NVIDIAProvider().generate_question(requirement(), LONG_CONTEXT)

    assert result["question_text"] == "Q?"
    assert len(FakeAsyncClient.calls) == 1
    # Task 1: the completion budget must be raised to 4096.
    assert FakeAsyncClient.calls[0]["max_tokens"] == nvidia_module.MAX_COMPLETION_TOKENS == 4096
    # The read timeout stays finite at 240 s.
    assert nvidia_module.READ_TIMEOUT_S == 240.0


async def test_empty_content_is_incomplete_not_hard_failure(provider_env):
    """Empty content must NOT raise immediately; it retries (task 2)."""
    FakeAsyncClient.script = [
        chat_body(content=None),                      # attempt 1: empty
        chat_body('{"question_text": "Recovered"}'),  # attempt 2 succeeds
    ]
    result = await nvidia_module.NVIDIAProvider().generate_question(requirement(), LONG_CONTEXT)

    assert result["question_text"] == "Recovered"
    assert len(FakeAsyncClient.calls) == 2


async def test_finish_reason_length_is_incomplete(provider_env):
    """finish_reason == 'length' is an incomplete generation even with text."""
    FakeAsyncClient.script = [
        chat_body('{"question_text": "truncat', finish_reason="length"),
        chat_body('{"question_text": "Complete now"}'),
    ]
    result = await nvidia_module.NVIDIAProvider().generate_question(requirement(), LONG_CONTEXT)

    assert result["question_text"] == "Complete now"
    assert len(FakeAsyncClient.calls) == 2


async def test_empty_content_retry_uses_compacted_prompt(provider_env):
    """Attempt 2+ must send a compacted prompt, not the identical request."""
    FakeAsyncClient.script = [
        chat_body(content=""),
        chat_body('{"question_text": "After compaction"}'),
    ]
    result = await nvidia_module.NVIDIAProvider().generate_question(requirement(10), LONG_CONTEXT)

    assert result["question_text"] == "After compaction"
    first_prompt = FakeAsyncClient.calls[0]["messages"][1]["content"]
    second_prompt = FakeAsyncClient.calls[1]["messages"][1]["content"]
    assert len(second_prompt) < len(first_prompt)
    # Semantic constraints are never dropped on compaction (task 3).
    for constraint in (
        "MARKS:\n10", "TOPIC:\nProcess scheduling",
        "BLOOM:\nL4", "DIFFICULTY:\nmedium", "QUESTION TYPE:\nanalytical",
    ):
        assert constraint in second_prompt


async def test_length_truncation_then_compact_retry_then_success(provider_env):
    body_truncated = {
        "choices": [{
            "message": {"content": '{"question_text": "part'},
            "finish_reason": "length",
        }]
    }
    FakeAsyncClient.script = [body_truncated, chat_body('{"question_text": "final answer"}')]
    result = await nvidia_module.NVIDIAProvider().generate_question(requirement(10), LONG_CONTEXT)

    assert result["question_text"] == "final answer"
    assert len(FakeAsyncClient.calls) == 2
    assert len(FakeAsyncClient.calls[1]["messages"][1]["content"]) < len(
        FakeAsyncClient.calls[0]["messages"][1]["content"]
    )


async def test_all_retries_exhausted_raises_value_error(provider_env):
    FakeAsyncClient.script = [chat_body(content=None) for _ in range(4)]
    with pytest.raises(ValueError, match="NVIDIA request failed"):
        await nvidia_module.NVIDIAProvider().generate_question(requirement(), LONG_CONTEXT)
    # max_retries=3 -> exactly 4 attempts.
    assert len(FakeAsyncClient.calls) == 4


async def test_malformed_json_is_retryable_failure_class(provider_env, caplog):
    caplog.set_level("WARNING")
    FakeAsyncClient.script = [
        chat_body("not json at all {{"),
        chat_body('{"question_text": "ok json"}'),
    ]
    result = await nvidia_module.NVIDIAProvider().generate_question(requirement(), LONG_CONTEXT)
    assert result["question_text"] == "ok json"
    assert any("malformed_json" in rec.message for rec in caplog.records)


async def test_read_timeout_is_retryable_failure_class(provider_env, caplog):
    caplog.set_level("WARNING")
    FakeAsyncClient.script = [
        httpx.ReadTimeout("timed out"),
        chat_body('{"question_text": "recovered"}'),
    ]
    result = await nvidia_module.NVIDIAProvider().generate_question(requirement(), LONG_CONTEXT)
    assert result["question_text"] == "recovered"
    assert any("read_write_timeout" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Service-level tests — validation loop preserved (task 4)
# ---------------------------------------------------------------------------


async def test_validation_failure_feeds_back_and_regenerates(provider_env, monkeypatch):
    """Valid JSON whose question text fails validation triggers regeneration."""
    service = GenerationService()
    calls: list[str | None] = []

    async def scripted_generate(req, context, feedback=None):
        calls.append(feedback)
        if feedback is None:
            return {"question_text": ""}  # passes JSON parse, fails validation
        return {"question_text": "Explain Round Robin scheduling with a numeric example."}

    monkeypatch.setattr(service.provider, "generate_question", scripted_generate)

    question = await service.generate_single_question(requirement(10), LONG_CONTEXT)
    assert question.question_text.startswith("Explain Round Robin")
    # First call had no feedback; second carried the validator violations.
    assert calls[0] is None and calls[1]

