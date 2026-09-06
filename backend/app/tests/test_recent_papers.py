"""
Recent Papers regression suite (GET /api/papers/recent).

Guards the dashboard data source end-to-end through the real HTTP route and
the real (SQLite-hosted) database layer:

  - Both composite and legacy persisted papers are returned.
  - Ordering is newest-first (by the parent GenerationJob.created_at,
    since GeneratedPaper itself has no timestamp column).
  - The summary metadata is mapped from the persisted
    PaperVersion.paper_json, with the legacy "<exam_type> - <subject>"
    title fallback.
  - Faculty see only their own papers (privacy); admin sees all (RBAC).

No in-memory generation state — PostgreSQL-only source of truth, so
refreshes and backend restarts retain the papers.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.main import app
from app.api.dependencies.auth import get_current_user, get_db
from app.core import security
from app.db.base import Base
from app.models.academic import QuestionBlueprint, Role, Subject, User
from app.models.generation import GeneratedPaper, GenerationJob, PaperVersion
from app.schemas.auth import UserContext


def _paper_json(subject: str, exam_name: str, total_marks: int, duration: int) -> dict:
    return {
        "title": "Paper",
        "status": "under_review",
        "subject_name": subject,
        "exam_name": exam_name,
        "total_marks": total_marks,
        "duration_minutes": duration,
        "questions": [
            {
                "question_number": 1,
                "section": "Part A",
                "marks": 2,
                "unit": 1,
                "topic": "Clustering",
                "bloom_level": "L2",
                "difficulty": "easy",
                "question_type": "conceptual",
                "question_text": "Define clustering.",
                "source_references": [],
                "locked": False,
            }
        ],
    }


class _Env:
    def __init__(self, session_maker, faculty_user_id: str, other_user_id: str,
                 composite_id: str, legacy_id: str, other_id: str) -> None:
        self.Session = session_maker
        self.faculty_user_id = faculty_user_id
        self.other_user_id = other_user_id
        self.composite_id = composite_id
        self.legacy_id = legacy_id
        self.other_id = other_id

    def client(self) -> AsyncClient:
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture
async def env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> _Env:
    monkeypatch.chdir(tmp_path)

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'recent.db'}")
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    composite_id, legacy_id, other_id = str(uuid4()), str(uuid4()), str(uuid4())

    async with Session() as session:
        faculty_role = Role(name="faculty", description="Faculty member")
        admin_role = Role(name="admin", description="Administrator")
        session.add_all([faculty_role, admin_role])
        await session.flush()

        faculty = User(email="faculty@test.com", full_name="Test Faculty",
                       password_hash=security.hash_password("SecurePass1!"),
                       is_active=True, roles=[faculty_role])
        admin = User(email="admin@test.com", full_name="Test Admin",
                     password_hash=security.hash_password("SecurePass1!"),
                     is_active=True, roles=[admin_role])
        other = User(email="other@test.com", full_name="Other Faculty",
                     password_hash=security.hash_password("SecurePass1!"),
                     is_active=True, roles=[faculty_role])
        session.add_all([faculty, admin, other])
        await session.flush()

        subject = Subject(code="CS-402", name="Operating Systems",
                          department="Computer Science", is_active=True)
        session.add(subject)
        await session.flush()
        blueprint = QuestionBlueprint(
            exam_type="mid1", subject_id=subject.id, source_mode="model",
            blueprint_json={}, validation_status="validated",
        )
        session.add(blueprint)
        await session.flush()

        now = datetime.utcnow()

        async def add_paper(paper_id: str, title: str, owner: User,
                            *, age_minutes: int, pj: dict | None = None) -> None:
            job = GenerationJob(blueprint_id=blueprint.id, status="completed",
                                current_step="done", progress_percent=100,
                                created_at=now - timedelta(minutes=age_minutes))
            session.add(job)
            await session.flush()
            paper = GeneratedPaper(id=paper_id, generation_job_id=job.id,
                                   title=title, status="draft", created_by=owner.id)
            session.add(paper)
            await session.flush()
            version = PaperVersion(
                id=str(uuid4()), generated_paper_id=paper_id, version_number=1,
                paper_json=pj if pj is not None else _paper_json(
                    "Operating Systems", "MID 1", 50, 110),
                blueprint_version={}, rules_version={}, validation_summary={},
            )
            session.add(version)
            await session.flush()
            paper.current_version_id = version.id

        # Composite (newest), legacy (older), another faculty's private paper
        # (oldest) — all persisted with real GenerationJob timestamps.
        await add_paper(composite_id, "Composite OS Paper", faculty, age_minutes=5)
        # Legacy paper whose paper_json predates subject metadata — the
        # dashboard must fall back to the "<exam_type> - <subject>" title.
        await add_paper(legacy_id, "MID 1 - Data Warehousing and Data Mining",
                        faculty, age_minutes=60,
                        pj={"title": "MID 1 - Data Warehousing and Data Mining",
                            "status": "under_review", "total_marks": 50,
                            "duration_minutes": 110, "questions": []})
        await add_paper(other_id, "Other Faculty Private Paper", other,
                        age_minutes=120)
        await session.commit()

    async def override_db():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        yield _Env(Session, str(faculty.id), str(other.id),
                   composite_id, legacy_id, other_id)
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


async def _get_recent_as(env: _Env, user_id: str, roles: list[str]) -> list[dict]:
    async def override_user():
        return UserContext(user_id=user_id, email=f"{user_id}@test.com",
                           full_name=user_id, roles=roles, is_active=True)

    app.dependency_overrides[get_current_user] = override_user
    try:
        async with env.client() as client:
            response = await client.get("/api/papers/recent")
        assert response.status_code == 200, response.text
        return response.json()
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_recent_returns_composite_and_legacy_newest_first(env: _Env) -> None:
    papers = await _get_recent_as(env, env.faculty_user_id, ["faculty"])

    # Faculty's own two papers; the other faculty's private paper is excluded.
    ids = [p["id"] for p in papers]
    assert env.composite_id in ids
    assert env.legacy_id in ids
    assert env.other_id not in ids

    # Newest first: composite (5 min old) before legacy (60 min old).
    assert ids.index(env.composite_id) < ids.index(env.legacy_id)

    by_id = {p["id"]: p for p in papers}

    composite = by_id[env.composite_id]
    assert composite["subject"] == "Operating Systems"
    assert composite["exam_type"] == "MID 1"
    assert composite["total_marks"] == 50
    assert composite["duration_minutes"] == 110
    assert composite["status"] == "draft"
    assert composite["created_at"]  # persisted job timestamp, ISO formatted

    legacy = by_id[env.legacy_id]
    # Legacy fallback: summary derived from the "<exam_type> - <subject>" title.
    assert legacy["exam_type"] == "MID 1"
    assert legacy["subject"] == "Data Warehousing and Data Mining"


@pytest.mark.asyncio
async def test_recent_admin_sees_all_papers(env: _Env) -> None:
    papers = await _get_recent_as(env, env.faculty_user_id, ["admin"])
    ids = [p["id"] for p in papers]
    assert env.composite_id in ids
    assert env.legacy_id in ids
    assert env.other_id in ids  # admin visibility across users (RBAC)
    # Newest first across ALL users.
    assert ids.index(env.composite_id) < ids.index(env.legacy_id) < ids.index(env.other_id)


@pytest.mark.asyncio
async def test_recent_is_persisted_state_only(env: _Env) -> None:
    """A fresh request (new session) still returns the papers — no in-memory state."""
    first = await _get_recent_as(env, env.faculty_user_id, ["faculty"])
    second = await _get_recent_as(env, env.faculty_user_id, ["faculty"])
    assert first == second
