"""
Composite review workflow regression suite.

Guards the LIVE-verified composite review behavior end-to-end through the
real HTTP routes and the real (SQLite-hosted) database layer:

  - Part A / Part B / OR regeneration preserves marks, unit, topic, Bloom
    level, difficulty and question_type, and applies the faculty instruction.
  - Regenerating one OR alternative changes ONLY that alternative; the
    opposite alternative stays intact and choice_group_id / choice_member_id
    are preserved.
  - Lock PERSISTS after commit + re-read from a second, independent database
    connection (regression for the async commit fix in PaperWorkflowService).
  - A locked question cannot be regenerated (HTTP 400); content and lock
    state stay unchanged.
  - Unlock persists; regeneration after unlock succeeds.
  - Legacy (flat) papers still regenerate and lock/unlock.
  - The flattened compatibility view stays synchronized after edits.
  - Missing composite identity returns 404.
  - After composite mutations: approval + PDF/DOCX export succeed and
    ExportAudit.approved_version == the real PaperVersion.id, with the
    authenticated user recorded as exported_by.

GenerationService.generate_single_question (the LLM boundary) is stubbed;
the composite resolver and workflow service under test are NOT mocked.
"""

from __future__ import annotations

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
from app.models.audit import ExportAudit
from app.models.generation import GeneratedPaper, GenerationJob, PaperVersion
from app.schemas.academic import GeneratedQuestionRead
from app.schemas.auth import UserContext
from app.schemas.paper_workflow import PaperDraftRead
from app.services.composite_review import refresh_flattened_views
from app.services.generation_service import GenerationService

# ---------------------------------------------------------------------------
# paper_json builders (realistic composite + legacy structures)
# ---------------------------------------------------------------------------


def _part_a_question(i: int) -> dict:
    return {
        "question_number": i,
        "section": "Part A",
        "marks": 2,
        "unit": 1 if i % 2 else 2,
        "topic": f"Short topic {i}",
        "bloom_level": "L2",
        "difficulty": "easy",
        "question_type": "short_answer",
        "exam_part": "short_answer",
        "group_number": None,
        "part_label": None,
        "choice_group_id": None,
        "choice_member_id": None,
        "locked": False,
        "question_text": f"Short answer {i}",
        "source_references": [{"ref": f"A{i}"}],
    }


def _main_part(qn: int, gn: int, label: str, *, cg: str | None, cm: str | None,
               topic: str, bloom: str) -> dict:
    return {
        "question_number": qn,
        "marks": 10,
        "unit": gn,
        "topic": topic,
        "bloom_level": bloom,
        "difficulty": "hard",
        "question_type": "analytical",
        "exam_part": "main",
        "group_number": gn,
        "part_label": label,
        "choice_group_id": cg,
        "choice_member_id": cm,
        "locked": False,
        "question_text": f"Explain {topic}.",
        "source_references": [{"ref": f"B{gn}{label}"}],
    }


def composite_paper_json() -> dict:
    paper_json = {
        "title": "Composite draft",
        "status": "under_review",
        "parts": {
            "part_a": {
                "name": "PART A - SHORT ANSWER",
                "total_marks": 20,
                "duration_minutes": 20,
                "questions": [_part_a_question(i) for i in range(1, 11)],
            },
            "part_b": {
                "name": "PART B - MAIN PAPER",
                "total_marks": 30,
                "duration_minutes": 90,
                "groups": [
                    {
                        "group_number": 1,
                        "choice_group": None,
                        "parts": [_main_part(11, 1, "a", cg=None, cm=None,
                                             topic="Deadlock", bloom="L4")],
                    },
                    {
                        "group_number": 5,
                        "choice_group": "cg-56",
                        "parts": [
                            _main_part(51, 5, "a", cg="cg-56", cm="m5a",
                                       topic="Paging", bloom="L3"),
                            _main_part(52, 5, "b", cg="cg-56", cm="m5b",
                                       topic="Virtual memory", bloom="L3"),
                        ],
                    },
                    {
                        "group_number": 6,
                        "choice_group": "cg-67",
                        "parts": [
                            _main_part(61, 6, "a", cg="cg-67", cm="m6a",
                                       topic="Scheduling", bloom="L3"),
                            _main_part(62, 6, "b", cg="cg-67", cm="m6b",
                                       topic="File systems", bloom="L3"),
                        ],
                    },
                ],
            },
        },
        "locked_question_numbers": [],
        "locked_question_keys": [],
    }
    refresh_flattened_views(paper_json)
    return paper_json


def legacy_paper_json() -> dict:
    return {
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
                "source_references": [{"ref": "legacy"}],
                "locked": False,
            }
        ]
    }


# ---------------------------------------------------------------------------
# Database environment — file-backed SQLite so that a SECOND independent
# connection can verify that mutations were actually COMMITTED.
# ---------------------------------------------------------------------------


class _Env:
    def __init__(self, main_session_maker, verify_session_maker,
                 paper_id: str, version_id: str, legacy_paper_id: str,
                 faculty_user_id: str) -> None:
        self.Session = main_session_maker
        self.VerifySession = verify_session_maker
        self.paper_id = paper_id
        self.version_id = version_id
        self.legacy_paper_id = legacy_paper_id
        self.faculty_user_id = faculty_user_id

    def client(self) -> AsyncClient:
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def db_json(self, paper_id: str) -> dict:
        """Re-read paper_json from the independent verification connection."""
        from sqlalchemy import select

        async with self.VerifySession() as session:
            row = await session.execute(
                select(PaperVersion.paper_json).where(
                    PaperVersion.generated_paper_id == paper_id
                )
            )
            return row.scalar_one()

    async def fresh_draft(self) -> dict:
        return await self.db_json(self.paper_id)


@pytest_asyncio.fixture
async def env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> _Env:
    monkeypatch.chdir(tmp_path)  # isolate storage/exports output

    # One file, TWO independent engines/connections: the verify connection
    # only sees data that was actually COMMITTED by the main connection
    # (a session that merely flush()es stays invisible — that IS the test).
    db_file = tmp_path / "workflow.db"
    main_engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    verify_engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    Session = async_sessionmaker(main_engine, expire_on_commit=False, class_=AsyncSession)
    VerifySession = async_sessionmaker(verify_engine, class_=AsyncSession)

    async with main_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as session:
        faculty_role = Role(name="faculty", description="Faculty member")
        session.add(faculty_role)
        await session.flush()
        faculty = User(
            email="faculty@test.com",
            full_name="Test Faculty",
            password_hash=security.hash_password("SecurePass1!"),
            is_active=True,
            roles=[faculty_role],
        )
        session.add(faculty)
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
        job = GenerationJob(blueprint_id=blueprint.id, status="completed",
                            current_step="done", progress_percent=100)
        session.add(job)
        await session.flush()

        paper_id, version_id, legacy_paper_id = str(uuid4()), str(uuid4()), str(uuid4())
        paper = GeneratedPaper(id=paper_id, generation_job_id=job.id,
                               title="Composite OS Paper", status="draft")
        session.add(paper)
        await session.flush()
        version = PaperVersion(id=version_id, generated_paper_id=paper_id,
                               version_number=1, paper_json=composite_paper_json(),
                               blueprint_version={}, rules_version={},
                               validation_summary={})
        session.add(version)
        await session.flush()
        paper.current_version_id = version.id

        legacy = GeneratedPaper(id=legacy_paper_id, generation_job_id=job.id,
                                title="Legacy Paper", status="draft")
        session.add(legacy)
        await session.flush()
        session.add(PaperVersion(generated_paper_id=legacy_paper_id, version_number=1,
                                 paper_json=legacy_paper_json(), blueprint_version={},
                                 rules_version={}, validation_summary={}))
        await session.commit()
        faculty_user_id = faculty.id

    async def override_db():
        async with Session() as session:
            yield session

    async def override_user():
        return UserContext(user_id=faculty_user_id, email="faculty@test.com",
                           full_name="Test Faculty", roles=["faculty"], is_active=True)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        yield _Env(Session, VerifySession, paper_id, version_id,
                   legacy_paper_id, faculty_user_id)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        await main_engine.dispose()
        await verify_engine.dispose()


@pytest.fixture
def fake_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub ONLY the LLM boundary; the resolver/workflow are exercised for real."""

    async def fake_generate_single_question(self, requirement, source_context):
        return GeneratedQuestionRead(
            question_number=requirement.question_number,
            section=requirement.section,
            marks=requirement.marks,
            unit=requirement.unit,
            topic=requirement.topic,
            bloom_level=requirement.bloom_level,
            difficulty=requirement.difficulty,
            question_type=requirement.question_type,
            choice_group=requirement.choice_group,
            generation_instruction=requirement.generation_instruction,
            question_text=(
                f"Regenerated {requirement.topic} [{requirement.question_number}] "
                f":: {requirement.generation_instruction or 'no instruction'}"
            ),
            source_references=[{"ref": "new"}],
            locked=False,
        )

    monkeypatch.setattr(
        GenerationService, "generate_single_question", fake_generate_single_question
    )


def _snapshot(paper_json: dict) -> dict:
    """Map of composite identity-key -> question dict for change comparison."""
    snap: dict[str, dict] = {}
    for q in paper_json["parts"]["part_a"]["questions"]:
        snap[f"short_answer:q{q['question_number']}"] = q
    for g in paper_json["parts"]["part_b"]["groups"]:
        for q in g["parts"]:
            snap[f"main:g{g['group_number']}:{q['part_label']}"] = q
    return snap


async def _post(env: _Env, url: str, payload: dict) -> dict:
    async with env.client() as client:
        response = await client.post(url, json=payload)
    assert response.status_code == 200, response.text
    return response.json()



# ---------------------------------------------------------------------------
# Regeneration regressions (via the real HTTP routes)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_part_a_regeneration_preserves_metadata(env: _Env, fake_generation) -> None:
    before = _snapshot(await env.fresh_draft())

    body = await _post(
        env, f"/api/papers/drafts/{env.paper_id}/regenerate",
        {"exam_part": "short_answer", "question_number": 3,
         "instructions": "Make this question more application-oriented."},
    )
    after = _snapshot(body["paper_json"])

    target, old = after["short_answer:q3"], before["short_answer:q3"]
    assert "application-oriented" in target["question_text"]
    assert target["question_text"] != old["question_text"]
    for field in ("marks", "unit", "topic", "bloom_level", "difficulty",
                  "question_type", "exam_part", "part_label"):
        assert target[field] == old[field], field
    # only the target changed
    for key, question in after.items():
        if key != "short_answer:q3":
            assert question["question_text"] == before[key]["question_text"], key
    # change persisted to the database
    assert _snapshot(await env.fresh_draft())["short_answer:q3"]["question_text"] == \
        target["question_text"]


@pytest.mark.asyncio
async def test_part_b_regeneration_preserves_group_metadata(env: _Env, fake_generation) -> None:
    before = _snapshot(await env.fresh_draft())

    body = await _post(
        env, f"/api/papers/drafts/{env.paper_id}/regenerate",
        {"exam_part": "main", "group_number": 1, "part_label": "a",
         "instructions": "Add a numerical example."},
    )
    after = _snapshot(body["paper_json"])

    target, old = after["main:g1:a"], before["main:g1:a"]
    assert "numerical example" in target["question_text"]
    for field in ("marks", "unit", "topic", "bloom_level", "difficulty",
                  "question_type", "exam_part", "group_number", "part_label",
                  "choice_group_id", "choice_member_id"):
        assert target[field] == old[field], field


@pytest.mark.asyncio
async def test_or_regeneration_changes_only_target_alternative(env: _Env, fake_generation) -> None:
    before = _snapshot(await env.fresh_draft())

    body = await _post(
        env, f"/api/papers/drafts/{env.paper_id}/regenerate",
        {"exam_part": "main", "group_number": 6, "part_label": "b",
         "instructions": "Focus on inode allocation."},
    )
    after = _snapshot(body["paper_json"])

    target = after["main:g6:b"]
    assert "inode allocation" in target["question_text"]
    assert target["choice_group_id"] == "cg-67"
    assert target["choice_member_id"] == "m6b"
    # opposite OR alternative unchanged, identity intact
    opposite = after["main:g6:a"]
    assert opposite["question_text"] == before["main:g6:a"]["question_text"]
    assert opposite["choice_group_id"] == "cg-67"
    assert opposite["choice_member_id"] == "m6a"
    # unrelated questions untouched
    assert after["main:g5:a"]["question_text"] == before["main:g5:a"]["question_text"]
    assert after["short_answer:q10"] == before["short_answer:q10"]


@pytest.mark.asyncio
async def test_missing_composite_identity_returns_404(env: _Env, fake_generation) -> None:
    async with env.client() as client:
        response = await client.post(
            f"/api/papers/drafts/{env.paper_id}/regenerate",
            json={"exam_part": "main", "group_number": 99, "part_label": "a"},
        )
    assert response.status_code == 404
    assert "detail" in response.json()

    async with env.client() as client:
        lock_response = await client.post(
            f"/api/papers/drafts/{env.paper_id}/lock",
            json={"exam_part": "main", "group_number": 99, "part_label": "a"},
        )
    assert lock_response.status_code == 404



# ---------------------------------------------------------------------------
# Lock persistence / locked regeneration / unlock (the async commit fix)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lock_persists_after_commit_and_reread(env: _Env) -> None:
    # the lock endpoint's response body already reflects the locked state
    async with env.client() as client:
        lock_response = await client.post(
            f"/api/papers/drafts/{env.paper_id}/lock",
            json={"exam_part": "main", "group_number": 5, "part_label": "a"},
        )
    assert lock_response.status_code == 200
    locked_body = lock_response.json()
    assert "main:g5:a" in (locked_body.get("locked_question_keys") or
                           locked_body.get("paper_json", {}).get("locked_question_keys", []))

    # Re-read from an INDEPENDENT connection: proves the lock was COMMITTED,
    # not merely flushed (regression for the missing commit() bug).
    persisted = await env.fresh_draft()
    q5a = persisted["parts"]["part_b"]["groups"][1]["parts"][0]
    assert q5a["locked"] is True
    assert "main:g5:a" in persisted["locked_question_keys"]


@pytest.mark.asyncio
async def test_locked_regeneration_rejected(env: _Env, fake_generation) -> None:
    await _post(env, f"/api/papers/drafts/{env.paper_id}/lock",
                {"exam_part": "main", "group_number": 5, "part_label": "a"})
    before = _snapshot(await env.fresh_draft())

    async with env.client() as client:
        response = await client.post(
            f"/api/papers/drafts/{env.paper_id}/regenerate",
            json={"exam_part": "main", "group_number": 5, "part_label": "a",
                  "instructions": "should not happen"},
        )
    assert response.status_code == 400
    assert "locked" in response.json()["detail"].lower()

    after = _snapshot(await env.fresh_draft())
    assert after["main:g5:a"] == before["main:g5:a"]  # content + lock unchanged


@pytest.mark.asyncio
async def test_unlock_persists_and_regeneration_succeeds(env: _Env, fake_generation) -> None:
    await _post(env, f"/api/papers/drafts/{env.paper_id}/lock",
                {"exam_part": "short_answer", "question_number": 7})
    assert (await env.fresh_draft())["parts"]["part_a"]["questions"][6]["locked"] is True

    await _post(env, f"/api/papers/drafts/{env.paper_id}/unlock",
                {"exam_part": "short_answer", "question_number": 7})
    persisted = await env.fresh_draft()
    assert persisted["parts"]["part_a"]["questions"][6]["locked"] is False
    assert "short_answer:q7" not in persisted["locked_question_keys"]

    body = await _post(
        env, f"/api/papers/drafts/{env.paper_id}/regenerate",
        {"exam_part": "short_answer", "question_number": 7,
         "instructions": "Make it conceptual."},
    )
    target = _snapshot(body["paper_json"])["short_answer:q7"]
    assert "Make it conceptual." in target["question_text"]
    assert target["marks"] == 2



# ---------------------------------------------------------------------------
# Legacy (flat) compatibility + flattened view synchronization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_flat_paper_regeneration_and_lock(env: _Env, fake_generation) -> None:
    body = await _post(
        env, f"/api/papers/drafts/{env.legacy_paper_id}/regenerate",
        {"question_number": 1, "instructions": "Make it tougher."},
    )
    assert "Make it tougher." in body["paper_json"]["questions"][0]["question_text"]

    await _post(env, f"/api/papers/drafts/{env.legacy_paper_id}/lock",
                {"question_number": 1})
    assert (await env.db_json(env.legacy_paper_id))["questions"][0]["locked"] is True

    async with env.client() as client:
        response = await client.post(
            f"/api/papers/drafts/{env.legacy_paper_id}/regenerate",
            json={"question_number": 1, "instructions": "nope"},
        )
    assert response.status_code == 400

    await _post(env, f"/api/papers/drafts/{env.legacy_paper_id}/unlock",
                {"question_number": 1})
    assert (await env.db_json(env.legacy_paper_id))["questions"][0]["locked"] is False


@pytest.mark.asyncio
async def test_compatibility_view_stays_synchronized(env: _Env, fake_generation) -> None:
    body = await _post(
        env, f"/api/papers/drafts/{env.paper_id}/regenerate",
        {"exam_part": "main", "group_number": 6, "part_label": "b",
         "instructions": "Add a diagram."},
    )
    paper_json = body["paper_json"]
    composite_text = (
        paper_json["parts"]["part_b"]["groups"][2]["parts"][1]["question_text"]
    )
    flat = next(q for q in paper_json["questions"] if q["question_number"] == 62)
    section = next(
        q for s in paper_json["sections"] for q in s["questions"]
        if q["question_number"] == 62
    )
    assert flat["question_text"] == composite_text
    assert section["question_text"] == composite_text



# ---------------------------------------------------------------------------
# Approval + export + ExportAudit regression (after composite mutations)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approval_and_exports_record_real_version_and_user(
    env: _Env, fake_generation
) -> None:
    # mutate the composite paper before approval (composite workflow path)
    await _post(env, f"/api/papers/drafts/{env.paper_id}/regenerate",
                {"exam_part": "main", "group_number": 6, "part_label": "b",
                 "instructions": "polish"})

    async with env.client() as client:
        approve = await client.post(
            f"/api/papers/drafts/{env.paper_id}/approve", json={}
        )
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] == "approved"

    for fmt, magic, mime in (
        ("pdf", b"%PDF", "application/pdf"),
        ("docx", b"PK",
         "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ):
        async with env.client() as client:
            response = await client.get(
                "/api/papers/export/download",
                params={"paper_id": env.paper_id, "format": fmt},
            )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith(mime)
        assert len(response.content) > 0
        assert response.content.startswith(magic)

    from sqlalchemy import select

    async with env.VerifySession() as session:
        audits = (await session.execute(
            select(ExportAudit).where(ExportAudit.paper_id == env.paper_id)
        )).scalars().all()
        assert {a.format.value if hasattr(a.format, "value") else str(a.format)
                for a in audits} == {"pdf", "docx"}
        for audit in audits:
            assert audit.approved_version == env.version_id
            assert audit.exported_by == env.faculty_user_id


# ---------------------------------------------------------------------------
# GET /drafts/{paper_id} — request-scoped session refactor regressions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_current_committed_db_state(env: _Env, fake_generation) -> None:
    # mutate + commit in one request/session...
    new_text = await _post(
        env, f"/api/papers/drafts/{env.paper_id}/regenerate",
        {"exam_part": "short_answer", "question_number": 2,
         "instructions": " Make it applied."},
    )
    # ...then GET from a completely fresh request/session must reflect it.
    async with env.client() as client:
        draft = (await client.get(f"/api/papers/drafts/{env.paper_id}")).json()
    returned = draft["paper_json"]["parts"]["part_a"]["questions"][1]
    assert returned["question_text"] == \
        new_text["paper_json"]["parts"]["part_a"]["questions"][1]["question_text"]
    assert "Make it applied." in returned["question_text"]


@pytest.mark.asyncio
async def test_get_reflects_mutation_from_another_session(env: _Env) -> None:
    # lock commits in one request; a fresh GET must see locked state
    await _post(env, f"/api/papers/drafts/{env.paper_id}/lock",
                {"exam_part": "main", "group_number": 6, "part_label": "a"})

    async with env.client() as client:
        draft = (await client.get(f"/api/papers/drafts/{env.paper_id}")).json()
    q61 = draft["paper_json"]["parts"]["part_b"]["groups"][2]["parts"][0]
    assert q61["locked"] is True
    assert "main:g6:a" in draft["paper_json"]["locked_question_keys"]
    assert "main:g6:a" in (draft.get("locked_question_keys") or [])


@pytest.mark.asyncio
async def test_get_composite_structure(env: _Env) -> None:
    async with env.client() as client:
        draft = (await client.get(f"/api/papers/drafts/{env.paper_id}")).json()
    part_a = draft["paper_json"]["parts"]["part_a"]["questions"]
    part_b = draft["paper_json"]["parts"]["part_b"]["groups"]
    assert len(part_a) == 10
    assert all(q["exam_part"] == "short_answer" for q in part_a)
    assert [g["group_number"] for g in part_b] == [1, 5, 6]
    or_pair = part_b[1]["parts"]
    assert {p["part_label"] for p in or_pair} == {"a", "b"}
    assert or_pair[0]["choice_group_id"] == or_pair[1]["choice_group_id"] == "cg-56"


@pytest.mark.asyncio
async def test_get_legacy_flat_paper_unchanged(env: _Env) -> None:
    async with env.client() as client:
        draft = (await client.get(f"/api/papers/drafts/{env.legacy_paper_id}")).json()
    assert draft["paper_json"]["questions"][0]["question_number"] == 1
    assert draft["paper_json"]["questions"][0]["question_text"] == "Define clustering."
    assert "parts" not in draft["paper_json"]


@pytest.mark.asyncio
async def test_in_memory_fallback_for_fresh_generated_draft(env: _Env) -> None:
    """A draft held only in the in-process generation store is still GET-able."""
    from app.api.routes.generation import generation_service

    fresh_id = "fresh-inmemory-paper-id"
    generation_service.paper_workflow.store.papers[fresh_id] = PaperDraftRead(
        id=fresh_id,
        title="Freshly generated draft",
        status="draft",
        locked_question_numbers=[],
        locked_question_keys=[],
        paper_json={"questions": [{"question_number": 1,
                                   "question_text": "Fresh draft question"}]},
        validation_passed=False,
    )
    try:
        async with env.client() as client:
            draft = (await client.get(f"/api/papers/drafts/{fresh_id}")).json()
        assert draft["id"] == fresh_id
        assert draft["title"] == "Freshly generated draft"
        assert draft["paper_json"]["questions"][0]["question_text"] == \
            "Fresh draft question"
    finally:
        generation_service.paper_workflow.store.papers.pop(fresh_id, None)









