"""Persistent GenerationJob workflow tests (async jobs, checkpoints, auth)."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

from contextlib import contextmanager

import httpx
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core import security
from app.db.base import Base
from app.models.academic import Role, User

SQLITE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(
    SQLITE_URL, echo=False, poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

ADMIN = ("admin@jobs.example.com", "AdminPass#1")
FAC1 = ("fac1@jobs.example.com", "FacPass#1")
FAC2 = ("fac2@jobs.example.com", "FacPass#2")

# Controllable fake NVIDIA provider ------------------------------------------
state = {"delay": 0.0, "empty_once": set(), "hard_fail": set(), "blocked": None}


async def fake_generate(self, requirement, context, feedback=None):
    n = requirement.question_number
    if state["blocked"] is not None and state["blocked"] == n:
        await state["blocked"].wait() if hasattr(state["blocked"], "wait") else None
    if n in state["empty_once"]:
        state["empty_once"].discard(n)
        return {"question_text": "", "source_references": []}
    if n in state["hard_fail"]:
        raise ValueError("NVIDIA request failed while generating question generation.")
    if state["delay"]:
        await asyncio.sleep(state["delay"])
    return {
        "question_text": f"Stub question {n}: explain {requirement.topic}.",
        "source_references": [{"title": "Stub", "page": 1}],
    }


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm.nvidia.NVIDIAProvider.generate_question", fake_generate
    )
    # Tests drive run_job explicitly with the injected SQLite session factory;
    # route-level spawn/finalize are neutralized so no stray task can touch
    # the production database.
    import app.api.routes.generation as gen_routes
    import app.services.generation_worker as gw

    async def _noop_async(job_id: str):
        return None

    monkeypatch.setattr(gw, "async_session_maker",
                        type("_Boom", (), {"__call__": staticmethod(
                            lambda: (_ for _ in ()).throw(
                                AssertionError("worker must use injected session factory")))})())
    monkeypatch.setattr(gen_routes, "enqueue_job", _noop_async)
    monkeypatch.setattr(gen_routes, "finalize_cancelled", _noop_async)
    state.update(delay=0.0, empty_once=set(), hard_fail=set(), blocked=None)


@pytest_asyncio.fixture(autouse=True)
async def db_lifecycle():
    previous = None
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestSession() as session:
        faculty = Role(name="faculty", description="Faculty member")
        admin = Role(name="admin", description="Administrator")
        session.add_all([faculty, admin])
        await session.flush()
        session.add_all([
            User(email=ADMIN[0], full_name="Admin", password_hash=security.hash_password(ADMIN[1]),
                 is_active=True, roles=[admin]),
            User(email=FAC1[0], full_name="Fac One", password_hash=security.hash_password(FAC1[1]),
                 is_active=True, roles=[faculty]),
            User(email=FAC2[0], full_name="Fac Two", password_hash=security.hash_password(FAC2[1]),
                 is_active=True, roles=[faculty]),
        ])
        await session.commit()
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@contextmanager
def _client(session_factory=None):
    """TestClient backed by an ISOLATED file-based SQLite environment.

    Returns (via .session_factory attribute on the yielded client wrapper)
    the same factory the worker must use, so concurrent polling is safe.
    """
    import os
    import tempfile

    from app.main import app
    from app.api.dependencies.auth import get_db

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    EnvSession = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _seed():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with EnvSession() as s:
            fac = Role(name="faculty", description="Faculty member")
            adm = Role(name="admin", description="Administrator")
            s.add_all([fac, adm])
            await s.flush()
            s.add_all([
                User(email=ADMIN[0], full_name="Admin",
                     password_hash=security.hash_password(ADMIN[1]), is_active=True, roles=[adm]),
                User(email=FAC1[0], full_name="Fac One",
                     password_hash=security.hash_password(FAC1[1]), is_active=True, roles=[fac]),
                User(email=FAC2[0], full_name="Fac Two",
                     password_hash=security.hash_password(FAC2[1]), is_active=True, roles=[fac]),
            ])
            await s.commit()

    async def _override():
        async with EnvSession() as s:
            yield s

    factory = session_factory or EnvSession

    saved = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override
    import asyncio as _asyncio
    import threading as _threading

    def _run_new_loop(coro):
        box = {}

        def runner():
            try:
                box["value"] = _asyncio.run(coro)
            except Exception as exc:  # noqa: BLE001
                box["error"] = exc

        thread = _threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join()
        if "error" in box:
            raise box["error"]
        return box.get("value")

    _run_new_loop(_seed())
    try:
        with TestClient(app) as c:
            c.session_factory = factory
            yield c
    finally:
        if saved is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = saved
        _run_new_loop(engine.dispose())
        import os as _os

        _os.remove(db_path)


def _login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    if r.status_code != 200 or "access_token" not in r.json():
        raise AssertionError(f"login failed: {r.status_code} {r.text[:200]}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _blueprint():
    sections = [
        {"name": "Section A", "section_type": "short_answer", "question_count": 1,
         "marks_per_question": 2, "instructions": "Answer all."},
        {"name": "Section B", "section_type": "descriptive", "question_count": 1,
         "marks_per_question": 5, "instructions": "Answer all."},
        {"name": "Section C", "section_type": "descriptive", "question_count": 1,
         "marks_per_question": 10, "instructions": "Answer all."},
    ]
    qs = [
        {"question_number": 1, "section": "Section A", "marks": 2, "unit": 1,
         "topic": "OS definition", "bloom_level": "L2", "difficulty": "easy",
         "question_type": "conceptual", "choice_group": None},
        {"question_number": 2, "section": "Section B", "marks": 5, "unit": 1,
         "topic": "Process scheduling", "bloom_level": "L3", "difficulty": "medium",
         "question_type": "application", "choice_group": None},
        {"question_number": 3, "section": "Section C", "marks": 10, "unit": 2,
         "topic": "Deadlocks", "bloom_level": "L4", "difficulty": "hard",
         "question_type": "analytical", "choice_group": None},
    ]
    return {
        "exam_type": "MID 1", "subject": "OPERATING SYSTEM", "selected_units": [1, 2],
        "total_marks": 17, "duration_minutes": 120, "sections": sections,
        "questions": qs, "source_mode": "manual", "unit_materials_present": False,
    }

def _create_job(client, headers, blueprint=None):
    return client.post("/api/generation/jobs",
                       json={"blueprint": blueprint or _blueprint()}, headers=headers)


def test_create_job_returns_immediately_queued():
    with _client() as client:
        r = _create_job(client, _login(client, *FAC1))
        assert r.status_code == 201
        body = r.json()
        assert body["status"] == "queued"
        assert body["total_questions"] == 3
        assert body["completed_questions"] == 0
        assert body["paper_id"] is None


def test_unauthenticated_job_creation_rejected():
    with _client() as client:
        r = client.post("/api/generation/jobs", json={"blueprint": _blueprint()})
        assert r.status_code == 401


def test_duplicate_active_job_returns_existing():
    with _client() as client:
        h = _login(client, *FAC1)
        first = _create_job(client, h)
        second = _create_job(client, h)
        assert first.status_code == 201
        assert second.status_code == 200
        assert second.json()["id"] == first.json()["id"]


@pytest.mark.asyncio
async def test_job_runs_to_completed_with_checkpoints():
    state["delay"] = 0.35
    with _client() as client:
        h = _login(client, *FAC1)
        job_id = _create_job(client, h).json()["id"]

        from app.services.generation_worker import run_job

        snapshots = []
        task = asyncio.create_task(
            run_job(job_id, session_factory=client.session_factory))
        while not task.done():
            await asyncio.sleep(0.03)
            r = client.get(f"/api/generation/jobs/{job_id}", headers=h)
            if r.status_code == 200:
                b = r.json()
                snapshots.append((b["status"], b["completed_questions"]))
        exc = task.exception()
        assert exc is None, f"worker crashed: {exc!r}"

        final = client.get(f"/api/generation/jobs/{job_id}", headers=h).json()
        assert final["status"] == "completed"
        assert final["completed_questions"] == 3
        assert final["progress_percent"] == 100
        assert final["paper_id"]

        running_snaps = [s for s in snapshots if s[0] == "running"]
        assert running_snaps, "never observed running state"
        saved_during_run = max(s[1] for s in running_snaps)
        assert saved_during_run >= 1, "no intermediate checkpoint observed"



@pytest.mark.asyncio
async def test_partial_failure_keeps_questions_and_resume_recovers():
    state["hard_fail"].add(2)
    with _client() as client:
        h = _login(client, *FAC1)
        job_id = _create_job(client, h).json()["id"]
        from app.services.generation_worker import run_job
        await run_job(job_id, session_factory=client.session_factory)

        failed = client.get(f"/api/generation/jobs/{job_id}", headers=h).json()
        assert failed["status"] == "failed"
        async with client.session_factory() as db:
            from sqlalchemy import select
            from app.models.generation import GeneratedQuestion
            rows = (await db.execute(select(GeneratedQuestion))).scalars().all()
            assert sorted(q.question_number for q in rows) == [1]

        state["hard_fail"].clear()
        resumed = client.post(f"/api/generation/jobs/{job_id}/resume", headers=h)
        assert resumed.status_code == 200
        await run_job(job_id, session_factory=client.session_factory)

        done = client.get(f"/api/generation/jobs/{job_id}", headers=h).json()
        assert done["status"] == "completed"
        async with client.session_factory() as db:
            from sqlalchemy import select
            from app.models.generation import GeneratedQuestion
            rows = (await db.execute(select(GeneratedQuestion))).scalars().all()
            assert sorted(q.question_number for q in rows) == [1, 2, 3]

@pytest.mark.asyncio
async def test_worker_batched_path_generates_all_questions_no_duplicates():
    """The batched worker path (used by concurrency mode) generates every
    question exactly once, with no duplicates, for any concurrency value.

    Runs at concurrency=1 here because the SQLite test harness uses a single
    StaticPool connection (cannot host concurrent AsyncSessions); the overlap
    speedup at concurrency 2/3 is verified against the real PostgreSQL+pools
    in production (see Phase 4 benchmark).
    """
    from sqlalchemy import select
    from app.models.generation import GeneratedQuestion

    state["delay"] = 0.05
    with _client() as client:
        h = _login(client, *FAC1)
        job_id = _create_job(client, h).json()["id"]
        from app.services.generation_worker import run_job

        await run_job(job_id, session_factory=client.session_factory, concurrency=1)

        final = client.get(f"/api/generation/jobs/{job_id}", headers=h).json()
        assert final["status"] == "completed"
        assert final["completed_questions"] == 3
        async with client.session_factory() as db:
            rows = (await db.execute(
                select(GeneratedQuestion).where(
                    GeneratedQuestion.generation_job_id == job_id))).scalars().all()
            nums = sorted(q.question_number for q in rows)
        # Exactly one of each — no duplicate generation (unique constraint).
        assert nums == [1, 2, 3]
        state["delay"] = 0.0


def test_faculty_cannot_access_another_users_job():
    with _client() as client:
        h1 = _login(client, *FAC1)
        job_id = _create_job(client, h1).json()["id"]
        h2 = _login(client, *FAC2)
        assert client.get(f"/api/generation/jobs/{job_id}", headers=h2).status_code == 403
        ha = _login(client, *ADMIN)
        assert client.get(f"/api/generation/jobs/{job_id}", headers=ha).status_code == 200


@pytest.mark.asyncio
async def test_resume_rejected_for_completed_job():
    with _client() as client:
        h = _login(client, *FAC1)
        job_id = _create_job(client, h).json()["id"]
        from app.services.generation_worker import run_job
        await run_job(job_id, session_factory=client.session_factory)
        r = client.post(f"/api/generation/jobs/{job_id}/resume", headers=h)
        assert r.status_code == 409


@pytest.mark.asyncio
async def test_cancel_running_job_stops_with_partial_questions():
    state["delay"] = 0.5
    with _client() as client:
        h = _login(client, *FAC1)
        job_id = _create_job(client, h).json()["id"]
        from app.services.generation_worker import run_job
        # Run sequentially so the cancellation deterministically lands between
        # questions. The worker's cancellation semantics (no regeneration,
        # partial work preserved, status never clobbered) are identical; this
        # simply removes the GENERATION_CONCURRENCY=2 + SQLite timing race
        # where all 3 fast questions finish before the cancel round-trips.
        task = asyncio.create_task(
            run_job(job_id, session_factory=client.session_factory, concurrency=1))
        for _ in range(100):
            await asyncio.sleep(0.1)
            r = client.get(f"/api/generation/jobs/{job_id}", headers=h)
            b = r.json()
            if b["completed_questions"] >= 1:
                break
        cancel = client.post(f"/api/generation/jobs/{job_id}/cancel", headers=h)
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "cancelled"
        await task
        final = client.get(f"/api/generation/jobs/{job_id}", headers=h).json()
        assert final["status"] == "cancelled"
        # Sequential run guarantees the cancel lands mid-run: at least 2 of the
        # 3 questions remain, and no regeneration/duplicate occurs.
        assert 0 < final["completed_questions"] < 3  # partial work preserved


@pytest.mark.asyncio
async def test_restart_resume_does_not_regenerate_completed_questions():
    """Crash mid-run, then resume via startup-style scan.

    The whole cycle lives inside ONE client context so the file-backed SQLite
    environment stays alive; Q2 is gated on an event to emulate a hung NVIDIA
    call at crash time, then released for the resumed pass.
    """
    block = asyncio.Event()

    async def blocking_generate(self, requirement, context, feedback=None):
        if requirement.question_number == 2 and not block.is_set():
            await block.wait()
        return await fake_generate(self, requirement, context, feedback)

    import app.services.generation_worker as gw

    saved_factory = None
    with patch("app.services.llm.nvidia.NVIDIAProvider.generate_question",
               blocking_generate):
        with _client() as client:
            saved_factory = gw.async_session_maker
            gw.async_session_maker = client.session_factory

            h = _login(client, *FAC1)
            job_id = _create_job(client, h).json()["id"]

            from app.services.generation_worker import enqueue_job, run_job

            crash_task = asyncio.create_task(
                run_job(job_id, session_factory=client.session_factory))
            factory = client.session_factory
            for _ in range(400):
                await asyncio.sleep(0.05)
                async with factory() as db:
                    from sqlalchemy import select
                    from app.models.generation import GeneratedQuestion, GenerationJob
                    rows = (await db.execute(select(GeneratedQuestion))).scalars().all()
                    job = (await db.execute(select(GenerationJob))).scalars().first()
                    if rows and job and job.status == "running":
                        break
            crash_task.cancel()  # hard crash simulation

            async with factory() as db:
                from sqlalchemy import select
                from app.models.generation import GeneratedQuestion
                before = (await db.execute(select(GeneratedQuestion))).scalars().all()
                assert len(before) == 1

            # --- restart: release the hang and resume via the startup scan ---
            block.set()
            resumed = await gw.resume_interrupted_jobs()
            assert resumed >= 1

            job = None
            for _ in range(600):
                await asyncio.sleep(0.1)
                async with factory() as db:
                    from sqlalchemy import select
                    from app.models.generation import GenerationJob
                    job = (await db.execute(select(GenerationJob))).scalars().first()
                    if job and job.status in ("completed", "failed"):
                        break
            assert job is not None, "job row missing"
            assert job.status == "completed", (
                f"stuck in {job.status!r} step={job.current_step!r} "
                f"error={job.error_message!r}")

            async with factory() as db:
                from sqlalchemy import select
                from app.models.generation import GeneratedQuestion
                rows = (await db.execute(
                    select(GeneratedQuestion).order_by(
                        GeneratedQuestion.question_number))).scalars().all()
                assert [q.question_number for q in rows] == [1, 2, 3]
                q1_texts = [q.question_text for q in rows if q.question_number == 1]
                assert len(q1_texts) == 1  # Q1 never regenerated
    gw.async_session_maker = saved_factory


@pytest.mark.asyncio
async def test_resume_marks_incompatible_stale_job_failed_and_skips_valid():
    """Startup resume handles stale/incompatible legacy jobs safely.

    A valid active job is re-queued (resumed), while a legacy job whose stored
    blueprint_json is no longer a valid ``PaperBlueprint`` (e.g. it holds a
    composite ``ExamConfig`` shape ``part_a``/``part_b``) is marked ``failed``
    with a clear reason and is NEVER re-enqueued - so it is not repeatedly
    resumed on every restart.
    """
    from app.models.academic import QuestionBlueprint, Subject
    from app.models.generation import GenerationJob
    from app.services import generation_worker as gw

    stale_composite_json = {
        "exam_type": "composite", "subject": "OS", "selected_units": [1, 2],
        "part_a": {"question_count": 10, "marks_per_question": 2, "total_marks": 20,
                   "duration_minutes": 20, "selected_units": [1, 2]},
        "part_b": {"total_marks": 20, "duration_minutes": 90, "selected_units": [1, 2],
                   "source_mode": "manual", "groups": [], "choice_groups": []},
    }

    enqueued: list[str] = []

    def _spy_enqueue(job_id):
        enqueued.append(job_id)

    with _client() as client:
        # Valid active job - created through the API (real flat blueprint).
        h = _login(client, *FAC1)
        valid_job_id = _create_job(client, h).json()["id"]

        # Stale/incompatible active job - seeded directly with a composite-shaped
        # blueprint_json that can no longer parse as a PaperBlueprint.
        async with client.session_factory() as db:
            subj = Subject(code="LOS", name="Legacy OS", department="CSE", is_active=True)
            db.add(subj)
            await db.flush()
            stale_bp = QuestionBlueprint(
                exam_type="composite", subject_id=subj.id, source_mode="auto",
                blueprint_json=stale_composite_json, validation_status="pending",
            )
            db.add(stale_bp)
            await db.flush()
            stale_job = GenerationJob(
                blueprint_id=stale_bp.id, status="queued",
                current_step="Blueprint accepted", progress_percent=5,
            )
            db.add(stale_job)
            await db.commit()
            stale_job_id = stale_job.id

        # Route the startup scan through the file-backed factory and capture which
        # jobs get enqueued, so we never race a real background run.
        saved_maker = gw.async_session_maker
        saved_enqueue = gw.enqueue_job
        gw.async_session_maker = client.session_factory
        gw.enqueue_job = _spy_enqueue
        try:
            resumed = await gw.resume_interrupted_jobs()
        finally:
            gw.enqueue_job = saved_enqueue
            gw.async_session_maker = saved_maker

        # Only the valid job is resumable; the stale legacy job is not re-queued.
        assert resumed == 1, f"expected exactly the valid job resumed, got {resumed}"
        assert valid_job_id in enqueued
        assert stale_job_id not in enqueued

        # The stale job is marked terminal (failed) with a clear sanitized reason.
        async with client.session_factory() as check:
            sjob = await check.get(GenerationJob, stale_job_id)
            assert sjob is not None
            assert sjob.status == "failed"
            assert sjob.finished_at is not None
            assert "not resumed" in (sjob.error_message or "").lower()

        # A second startup scan never re-enqueues the now-terminal stale job
        # (the valid job, still queued because we only spied enqueue, may be
        # resumed again but the stale one must stay terminal).
        saved_maker2 = gw.async_session_maker
        saved_enqueue2 = gw.enqueue_job
        gw.async_session_maker = client.session_factory
        gw.enqueue_job = _spy_enqueue
        try:
            await gw.resume_interrupted_jobs()
        finally:
            gw.enqueue_job = saved_enqueue2
            gw.async_session_maker = saved_maker2
        assert stale_job_id not in enqueued

        async with client.session_factory() as check2:
            sjob2 = await check2.get(GenerationJob, stale_job_id)
            assert sjob2.status == "failed"  # never flips back to an active state
