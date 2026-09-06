"""Phase 2 regression tests - composite ExamGenerationJob orchestration.

Exercises parent/child creation, Part A + Part B stages, choice metadata
persistence, resume/no-duplicate, failure gating, composite assembly and the
50-mark validation gate. Uses a fake NVIDIA provider and an in-memory SQLite
harness (same pattern as test_generation_jobs.py).
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.generation import ExamGenerationJob, GeneratedQuestion
from app.schemas.exam_structure import (
    ChoiceGroup,
    ChoiceMember,
    MainPaperConfig,
    QuestionGroup,
    QuestionPart,
    ShortAnswerPaperConfig,
)


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture()
async def harness(monkeypatch):
    engine = create_async_engine(
        SQLITE_URL, echo=False, poolclass=StaticPool,
        connect_args={"check_same_thread": False})
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def fake_generate(self, requirement, context, feedback=None):
        return {
            "question_text": f"Stub Q{requirement.question_number}: {requirement.topic}",
            "source_references": [{"title": "Stub", "page": 1}],
        }

    monkeypatch.setattr(
        "app.services.llm.nvidia.NVIDIAProvider.generate_question", fake_generate)

    yield maker
    await engine.dispose()


def part(n: int, unit: int = 2, marks: int = 5) -> QuestionPart:
    return QuestionPart(question_number=n, part_label=None, marks=marks,
                        unit=unit, topic=f"topic{n}", bloom_level="L3")


def part_a_config() -> ShortAnswerPaperConfig:
    return ShortAnswerPaperConfig(
        question_count=10, marks_per_question=2, total_marks=20,
        duration_minutes=20, selected_units=[1, 2],
    )


def part_b_config() -> MainPaperConfig:
    """Part B: g1(5)+g2(5)+cg1{g3,g4} sel1(5)+cg2{g5,g6} sel1(5)+g7(5)+g8(5)=30."""
    groups = [
        QuestionGroup(group_number=1, parts=[part(1)]),
        QuestionGroup(group_number=2, parts=[part(2)]),
        QuestionGroup(group_number=3, parts=[part(3)], choice_group="cg1"),
        QuestionGroup(group_number=4, parts=[part(4)], choice_group="cg1"),
        QuestionGroup(group_number=5, parts=[part(5)], choice_group="cg2"),
        QuestionGroup(group_number=6, parts=[part(6)], choice_group="cg2"),
        QuestionGroup(group_number=7, parts=[part(7)]),
        QuestionGroup(group_number=8, parts=[part(8)]),
    ]
    choices = [
        ChoiceGroup(id="cg1", choice_type="multi", select_count=1, members=[
            ChoiceMember(key="3", marks=5, unit=2, topic="topic3", bloom_level="L3"),
            ChoiceMember(key="4", marks=5, unit=2, topic="topic4", bloom_level="L3"),
        ]),
        ChoiceGroup(id="cg2", choice_type="multi", select_count=1, members=[
            ChoiceMember(key="5", marks=5, unit=2, topic="topic5", bloom_level="L3"),
            ChoiceMember(key="6", marks=5, unit=2, topic="topic6", bloom_level="L3"),
        ]),
    ]
    return MainPaperConfig(total_marks=30, duration_minutes=90,
                           selected_units=[1, 2], source_mode="model",
                           groups=groups, choice_groups=choices)


def json_safe(obj):
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    return obj


async def make_exam_job(maker) -> str:
    from app.schemas.exam_structure import ExamConfig

    cfg = ExamConfig(exam_type="MID 1", subject="OPERATING SYSTEMS",
                     selected_units=[1, 2], part_a=part_a_config(),
                     part_b=part_b_config())
    async with maker() as s:
        job = ExamGenerationJob(exam_config_json=json_safe(cfg.model_dump()),
                                status="queued", created_by=None,
                                current_step="Queued")
        s.add(job)
        await s.commit()
        return job.id
# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_part_a_requirements_are_10x2(harness):
    from app.services.exam_generation_service import build_part_a_requirements
    reqs = build_part_a_requirements(part_a_config(), [(1, "processes"), (2, "deadlocks")])
    assert len(reqs) == 10
    assert sum(r["marks"] for r in reqs) == 20
    assert all(r["exam_part"] == "short_answer" for r in reqs)
    assert all(r["marks"] == 2 for r in reqs)


@pytest.mark.asyncio
async def test_part_a_bloom_distribution_respected(harness):
    from app.schemas.exam_structure import BloomDistribution
    from app.services.exam_generation_service import build_part_a_requirements
    cfg = ShortAnswerPaperConfig(
        question_count=10, marks_per_question=2, total_marks=20,
        duration_minutes=20, selected_units=[1, 2],
        bloom_distribution=BloomDistribution(by_level={"L2": 4, "L3": 6}),
    )
    reqs = build_part_a_requirements(cfg, [(1, "processes")])
    blooms = [r["bloom_level"] for r in reqs]
    assert blooms == ["L2", "L2", "L2", "L2", "L3", "L3", "L3", "L3", "L3", "L3"]


@pytest.mark.asyncio
async def test_part_b_requirements_preserve_choice_metadata(harness):
    from app.services.exam_generation_service import build_part_b_requirements
    reqs = build_part_b_requirements(part_b_config())
    by_num = {r["question_number"]: r for r in reqs}
    # group-level OR members keep their choice ids (30 -> cg1, 50 -> cg2)
    assert by_num[30]["choice_group_id"] == "cg1"
    assert by_num[40]["choice_group_id"] == "cg1"
    assert by_num[50]["choice_group_id"] == "cg2"
    # compulsory questions carry no choice metadata
    assert by_num[10]["choice_group_id"] is None
    assert all(r["exam_part"] == "main" for r in reqs)
    assert len(reqs) == 8


@pytest.mark.asyncio
async def test_parent_job_completes_all_parts(harness):
    maker = harness
    job_id = await make_exam_job(maker)
    from app.services.exam_generation_service import run_exam_job
    await run_exam_job(job_id, session_factory=maker, concurrency=2,
                       part_a_topic_pool=[(1, "processes"), (2, "deadlocks")])

    async with maker() as s:
        job = await s.get(ExamGenerationJob, job_id)
        assert job.status == "completed"
        assert job.total_questions == 18      # 10 Part A + 8 Part B parts
        assert job.completed_questions == 18
        assert job.paper_id is not None
        rows = (await s.execute(select(GeneratedQuestion).where(
            GeneratedQuestion.exam_generation_job_id == job_id))).scalars().all()
        pa_nums = sorted(r.question_number for r in rows if r.exam_part == "short_answer")
        pa_nums = sorted(r.question_number for r in rows if r.exam_part == "short_answer")
        pb_nums = sorted(r.question_number for r in rows if r.exam_part == "main")
        # Part A/B are numbered independently; uniqueness is per paper
        assert len(pa_nums) == len(set(pa_nums)) == 10
        assert len(pa_nums) == len(set(pa_nums)) == 10


@pytest.mark.asyncio
async def test_choice_metadata_persisted(harness):
    maker = harness
    job_id = await make_exam_job(maker)
    from app.services.exam_generation_service import run_exam_job
    await run_exam_job(job_id, session_factory=maker, concurrency=2,
                       part_a_topic_pool=[])

    async with maker() as s:
        rows = (await s.execute(select(GeneratedQuestion).where(
            GeneratedQuestion.exam_generation_job_id == job_id))).scalars().all()
        chosen = [r for r in rows if r.choice_group_id == "cg1"]
        # BOTH alternatives of the OR pair are generated
        assert len(chosen) == 2
        assert {r.choice_member_id for r in chosen} >= {"3", "4"}
        assert all(r.group_number in (3, 4) for r in chosen)


@pytest.mark.asyncio
async def test_resume_does_not_regenerate_completed_questions(harness):
    maker = harness
    job_id = await make_exam_job(maker)

    async with maker() as s:
        import uuid
        s.add(GeneratedQuestion(
            generation_job_id=str(uuid.uuid4()), question_number=11,
            section="Part A", marks=2, unit=1, topic="pre",
            bloom_level="L2", difficulty="easy",
            question_type="short_answer", question_text="Pre-existing",
            source_references={}, locked=False,
            exam_generation_job_id=job_id, exam_part="short_answer"))
        await s.commit()

    from app.services.exam_generation_service import run_exam_job
    await run_exam_job(job_id, session_factory=maker, concurrency=2,
                       part_a_topic_pool=[(1, "p")])

    async with maker() as s:
        rows = (await s.execute(select(GeneratedQuestion).where(
            GeneratedQuestion.exam_generation_job_id == job_id))).scalars().all()
        seeded = [r.question_text for r in rows if r.question_number == 11]
        # the pre-existing checkpoint was never regenerated/duplicated
        assert len(seeded) == 1 and seeded[0] == "Pre-existing"


def test_full_exam_validation_gate_blocks_incomplete_paper():
    cfg = part_b_config()
    bad = MainPaperConfig(**{**cfg.model_dump(), "total_marks": 99})
    from app.schemas.exam_structure import ExamConfig
    from app.services.exam_structure_service import validate_exam
    ex = ExamConfig(exam_type="MID 1", subject="OS", selected_units=[1, 2],
                    part_a=part_a_config(), part_b=bad)
    v = validate_exam(ex)
    assert v.passed is False
    assert any(i.code == "part_b_attempted_mismatch" for i in v.issues)


def test_flat_blueprint_pipeline_still_validates():
    """Backward compatibility: the legacy flat blueprint path still works."""
    from app.schemas.academic import PaperBlueprint, QuestionRequirement
    from app.services.validation_service import ValidationService

    bp = PaperBlueprint(
        exam_type="MID 1", subject="OS", selected_units=[1, 2],
        total_marks=5, duration_minutes=60,
        sections=[{"name": "Section A", "section_type": "short_answer",
                   "question_count": 1, "marks_per_question": 5}],
        questions=[{"question_number": 1, "section": "Section A",
                    "marks": 5, "unit": 1, "topic": "Scheduling",
                    "bloom_level": "L3", "difficulty": "medium",
                    "question_type": "analytical"}],
        source_mode="manual")
    v = ValidationService().validate_blueprint(bp)
    assert v.passed is True

@pytest.mark.asyncio
async def test_debug_parent_error(harness):
    maker = harness
    job_id = await make_exam_job(maker)
    from app.services.exam_generation_service import run_exam_job
    await run_exam_job(job_id, session_factory=maker, concurrency=2, part_a_topic_pool=[(1,'a'),(2,'b')])
    async with maker() as s:
        job = await s.get(ExamGenerationJob, job_id)
        print('DBG_STATUS', job.status)
        print('DBG_ERROR', (job.error_message or '-')[:400])
        rows = (await s.execute(select(GeneratedQuestion).where(GeneratedQuestion.exam_generation_job_id == job_id))).scalars().all()
        print('DBG_ROWS', len(rows), sorted(r.question_number for r in rows)[:20])

# ---------------------------------------------------------------------------
# Composite API tests (TASK 3/4/7)
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient  # noqa: E402
from app.api.dependencies.auth import get_current_user as _real_get_user  # noqa: E402
from app.api.dependencies.auth import get_db as _real_get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.schemas.auth import UserContext  # noqa: E402


OWNER_ID  = "aaaa1111-1111-4111-8111-bbbb22223333"
OTHER_ID  = "cccc2222-2222-4222-8222-dddd44445555"
ADMIN_ID  = "eeee3333-3333-4333-8333-ffff55556666"

def _user(user_id: str, roles: list[str]):
    ctx = UserContext(user_id=user_id,
                       email=f"{user_id}@example.com",
                       full_name="Faculty", roles=roles, is_active=True)
    async def _provider() -> UserContext:
        return ctx
    return _provider


@pytest.fixture()
def api(monkeypatch, harness):
    maker = harness
    """TestClient bound to the SQLite harness; spawn stubbed for determinism."""
    async def fake(self, requirement, context, feedback=None):
        return {"question_text": "Stub", "source_references": []}
    monkeypatch.setattr(
        "app.services.llm.nvidia.NVIDIAProvider.generate_question", fake)

    async def override_db():
        async with maker() as s:
            yield s

    monkeypatch.setattr(
        "app.services.exam_generation_service.async_session_maker", maker)
    monkeypatch.setattr(
        "app.api.routes.exam_generation._spawn", lambda *a, **k: None)
    fastapi_app.dependency_overrides[_real_get_db] = override_db
    fastapi_app.dependency_overrides[_real_get_user] = _user(OWNER_ID, ["faculty"])
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


def _payload():
    from app.schemas.exam_structure import ExamConfig
    cfg = ExamConfig(exam_type="MID 1", subject="OPERATING SYSTEMS",
                     selected_units=[1, 2], part_a=part_a_config(),
                     part_b=part_b_config())
    return {"exam_config": json_safe(cfg.model_dump())}


def test_api_create_returns_job_and_progress(api):
    r = api.post("/api/exam-generation/jobs", json=_payload())
    assert r.status_code == 201
    body = r.json()
    assert body["job_id"]
    assert body["status"] in ("queued", "running")
    assert body["total_questions"] == 18          # 10 Part A + 8 Part B parts
    assert body["part_a"]["total_questions"] == 10
    assert body["part_b"]["total_questions"] == 8


def test_api_create_is_idempotent_for_active_job(api):
    first = api.post("/api/exam-generation/jobs", json=_payload()).json()
    second = api.post("/api/exam-generation/jobs", json=_payload()).json()
    assert second["job_id"] == first["job_id"]


def test_api_rejects_invalid_exam_config(api):
    payload = _payload()
    payload["exam_config"]["part_a"]["question_count"] = 5   # 5x2 != total 20
    r = api.post("/api/exam-generation/jobs", json=payload)
    assert r.status_code == 400


def test_api_ownership_blocks_other_users(api, monkeypatch):
    created = api.post("/api/exam-generation/jobs", json=_payload()).json()
    job_id = created["job_id"]
    # a different faculty member must be blocked
    fastapi_app.dependency_overrides[_real_get_user] = _user(OTHER_ID, ["faculty"])
    try:
        r = api.get(f"/api/exam-generation/jobs/{job_id}")
        assert r.status_code == 403
        r = api.post(f"/api/exam-generation/jobs/{job_id}/cancel")
        assert r.status_code == 403
    finally:
        fastapi_app.dependency_overrides[_real_get_user] = _user(OWNER_ID, ["faculty"])
    # admin always has access
    fastapi_app.dependency_overrides[_real_get_user] = _user(ADMIN_ID, ["admin"])
    r = api.get(f"/api/exam-generation/jobs/{job_id}")
    assert r.status_code in (200, 202)



@pytest.mark.asyncio
async def test_api_progress_exposes_part_breakdown(harness, monkeypatch):
    """Part A completed -> part_a reports completed, part_b pending."""
    import uuid as _uuid

    import httpx
    from app.api.dependencies.auth import get_current_user as gu
    from app.api.dependencies.auth import get_db as gdb
    from app.main import app as fastapi_app

    maker = harness

    async def fake(self, requirement, context, feedback=None):
        return {"question_text": "Stub", "source_references": []}

    monkeypatch.setattr(
        "app.services.llm.nvidia.NVIDIAProvider.generate_question", fake)

    async def override_db():
        async with maker() as s:
            yield s

    async def override_user():
        return UserContext(user_id=OWNER_ID,
                           email=f"{OWNER_ID}@example.com",
                           full_name="Faculty", roles=["faculty"], is_active=True)

    job_id = await make_exam_job(maker)
    async with maker() as s:
        for n in range(1, 11):
            s.add(GeneratedQuestion(
                generation_job_id=str(_uuid.uuid4()), question_number=n,
                section="Part A", marks=2, unit=1, topic=f"t{n}",
                bloom_level="L2", difficulty="easy",
                question_type="short_answer", question_text=f"Q{n}",
                source_references={}, locked=False,
                exam_generation_job_id=job_id, exam_part="short_answer"))
        job = await s.get(ExamGenerationJob, job_id)
        job.completed_questions = 10
        await s.commit()

    fastapi_app.dependency_overrides[gdb] = override_db
    fastapi_app.dependency_overrides[gu] = override_user
    try:
        transport = httpx.ASGITransport(app=fastapi_app)
        async with httpx.AsyncClient(transport=transport,
                                     base_url="http://test") as c:
            r = await c.get(f"/api/exam-generation/jobs/{job_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["part_a"]["completed_questions"] == 10
        assert body["part_a"]["status"] == "completed"
        assert body["part_b"]["total_questions"] == 8
        assert body["part_b"]["completed_questions"] == 0
        assert body["total_questions"] == 18
    finally:
        fastapi_app.dependency_overrides.pop(gdb, None)
        fastapi_app.dependency_overrides.pop(gu, None)
# ---------------------------------------------------------------------------
# _spawn -> run_exam_job integration (TASK 3: keyword + failure hardening)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spawn_passes_part_a_topic_pool_and_job_completes(harness, monkeypatch):
    import asyncio

    from app.api.routes import exam_generation as eg

    maker = harness
    job_id = await make_exam_job(maker)
    captured: dict = {}

    async def fake_run(exam_job_id, session_factory=None, concurrency=None,
                       part_a_topic_pool=None):
        captured["job_id"] = exam_job_id
        captured["pool"] = part_a_topic_pool
        # simulate the real worker finishing the job
        async with maker() as s:
            j = await s.get(ExamGenerationJob, exam_job_id)
            j.status = "completed"
            j.completed_questions = j.total_questions or 0
            await s.commit()

    monkeypatch.setattr(eg, "run_exam_job", fake_run)
    monkeypatch.setattr(eg, "async_session_maker", maker)

    eg._spawn(job_id, [(1, "processes"), (2, "deadlocks")])
    await asyncio.sleep(0.2)

    assert captured.get("job_id") == job_id
    assert captured.get("pool") == [(1, "processes"), (2, "deadlocks")]
    async with maker() as s:
        job = await s.get(ExamGenerationJob, job_id)
        assert job.status == "completed"


@pytest.mark.asyncio
async def test_spawn_marks_job_failed_on_background_error(harness, monkeypatch):
    import asyncio

    from app.api.routes import exam_generation as eg

    maker = harness
    job_id = await make_exam_job(maker)

    async def boom(exam_job_id, session_factory=None, concurrency=None,
                   part_a_topic_pool=None):
        raise RuntimeError("injected background failure")

    monkeypatch.setattr(eg, "run_exam_job", boom)
    monkeypatch.setattr(eg, "async_session_maker", maker)

    eg._spawn(job_id, None)
    await asyncio.sleep(0.3)

    async with maker() as s:
        job = await s.get(ExamGenerationJob, job_id)
        assert job.status == "failed"          # never stuck in queued
        assert job.error_message
        assert "RuntimeError" in job.error_message
        assert job.current_step == "Generation failed"
        assert job.finished_at is not None


def test_group_view_parts_carry_composite_identity():
    """Part B group-view parts must expose exam_part/group_number so the Review
    UI can build the composite regeneration payload (main:gN:label) instead of
    falling back to a legacy flat identity that would target the wrong question."""
    from types import SimpleNamespace

    from app.services.exam_generation_service import PART_B, _group_view

    config_b = MainPaperConfig(
        total_marks=20, duration_minutes=90, selected_units=[1, 2],
        source_mode="manual",
        groups=[
            QuestionGroup(group_number=2, choice_group="cg1", parts=[
                QuestionPart(question_number=2, part_label="a", marks=10, unit=2,
                             topic="Scheduling algorithms", bloom_level="L4",
                             choice_member="2a"),
            ]),
            QuestionGroup(group_number=3, choice_group="cg1", parts=[
                QuestionPart(question_number=3, part_label="a", marks=10, unit=2,
                             topic="Deadlock characterization", bloom_level="L4",
                             choice_member="3a"),
            ]),
        ],
    )
    rows = [
        SimpleNamespace(
            group_number=2, part_label="a", question_number=21, marks=10, unit=2,
            topic="Scheduling algorithms", bloom_level="L4", difficulty="medium",
            question_type="analytical", exam_part="main", choice_group_id="cg1",
            choice_member_id="2a", locked=False, source_references={"refs": []},
            question_text="Explain scheduling algorithms.",
        ),
        SimpleNamespace(
            group_number=3, part_label="a", question_number=31, marks=10, unit=2,
            topic="Deadlock characterization", bloom_level="L4", difficulty="medium",
            question_type="analytical", exam_part="main", choice_group_id="cg1",
            choice_member_id="3a", locked=False, source_references={"refs": []},
            question_text="Describe deadlock characterization.",
        ),
    ]

    view = _group_view(config_b, rows)
    assert len(view) == 2
    for group in view:
        for part in group["parts"]:
            assert part["exam_part"] == PART_B == "main"
            assert part["group_number"] == group["group_number"]
            assert part["part_label"]  # required by composite regeneration
    or_groups = [g for g in view if g["choice_group"] == "cg1"]
    assert len(or_groups) == 2
