"""
Comprehensive test suite for POST /api/papers/export.

Runs entirely on an in-memory SQLite database (aiosqlite) so no real
PostgreSQL instance is required during CI / local testing.

Coverage:
  1.  PDF export success — 200, file exists, valid PDF binary
  2.  DOCX export success — 200, file exists, valid DOCX binary
  3.  DOCX output contains the exact question texts from paper_json
  4.  PDF file is non-empty and starts with the %PDF header
  5.  ExportAudit record is persisted with correct paper_id / approved_version
  6.  ExportAudit.exported_by is the authenticated user UUID (never "system")
  7.  GeneratedPaper.status stays "approved" after export (paper remains exportable)
  8.  ExportAudit is the authoritative export audit trail (no status mutation)
  9.  Unapproved (draft) paper is rejected with 400
 10.  Missing paper is rejected with 400
 11.  User with no roles is rejected with 403
 12.  Missing auth token is rejected with 401
 13.  Admin-role user can export (200)
 14.  Invalid format value is rejected with 422 (Pydantic validation)
 15.  Response body has file_path and format keys
 16.  ExportAudit.timestamp is auto-populated
 17.  PDF + DOCX both work across two approved papers (two audit records)
 18.  An approved paper can be exported repeatedly — each export writes a
     fresh ExportAudit record and the paper stays approved
"""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.future import select
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# Pre-import compatibility shims
# ---------------------------------------------------------------------------

# passlib (used by app.core.security) reads bcrypt.__about__.__version__.
# bcrypt 4.x removed __about__, so inject a dummy to avoid the noisy warning.
import bcrypt as _bcrypt  # noqa: E402

if not hasattr(_bcrypt, "__about__"):
    _bcrypt.__about__ = type("_about", (object,), {"__version__": "4.0.0"})()

# SQLite cannot natively render the PostgreSQL JSONB type.  The
# JSONB.__visit_name__ is "JSONB" (uppercase), so the SQLite type compiler
# looks for `visit_JSONB`.  Teach it to fall back to plain JSON so that
# create_all / drop_all work against the in-memory test database.
if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):

    def _visit_JSONB(self, type_, **kw):  # noqa: ARG001
        return self.process(JSON(), **kw)

    SQLiteTypeCompiler.visit_JSONB = _visit_JSONB
# ---------------------------------------------------------------------------
# Test database — a single shared in-memory SQLite connection
# ---------------------------------------------------------------------------

SQLITE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    SQLITE_URL,
    echo=False,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

async def _get_test_db():
    """Override for app.api.dependencies.auth.get_db."""
    async with TestSession() as session:
        yield session

# ---------------------------------------------------------------------------
# App — the DB dependency override is installed/restored by _db_lifecycle so
# that multiple test modules sharing the same app instance do not clobber
# each other's overrides.
# ---------------------------------------------------------------------------

from app.main import app  # noqa: E402
from app.api.dependencies.auth import get_db  # noqa: E402

# ---------------------------------------------------------------------------
# Model / helper imports
# ---------------------------------------------------------------------------

from app.core import security  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.models.academic import QuestionBlueprint, Role, Subject, User  # noqa: E402
from app.models.audit import ExportAudit, ExportFormat  # noqa: E402
from app.models.generation import (  # noqa: E402
    GeneratedPaper,
    GenerationJob,
    PaperVersion,
)
# ---------------------------------------------------------------------------
# Static test data
# ---------------------------------------------------------------------------

QUESTION_TEXTS: dict[int, str] = {
    1: "Define clustering and enumerate its types.",
    2: "Differentiate between classification and regression.",
    3: "Outline the major steps of the CRISP-DM methodology.",
    4: "Describe the Apriori algorithm with a suitable example.",
}

def _make_paper_json(version_id: str) -> dict:
    """Build a realistic paper_json payload that the renderer can consume."""
    return {
        "version_id": version_id,
        "title": "Midterm Examination",
        "institution_name": "Test University",
        "department_name": "Department of Computer Science",
        "subject_name": "Data Mining",
        "subject_code": "CS-402",
        "exam_name": "Midterm Exam",
        "duration_minutes": 180,
        "total_marks": 70,
        "instructions": [
            "Answer all questions.",
            "Draw diagrams wherever necessary.",
            "All questions carry equal marks.",
        ],
        "sections": [
            {
                "name": "Section A — Short Answer (20 marks)",
                "instructions": "Answer any two questions.",
                "questions": [
                    {
                        "question_number": 1,
                        "marks": 10,
                        "question_text": QUESTION_TEXTS[1],
                        "unit": 1,
                        "topic": "Clustering",
                        "bloom_level": "L1",
                        "difficulty": "easy",
                        "question_type": "conceptual",
                    },
                    {
                        "question_number": 2,
                        "marks": 10,
                        "question_text": QUESTION_TEXTS[2],
                        "unit": 2,
                        "topic": "Classification",
                        "bloom_level": "L2",
                        "difficulty": "medium",
                        "question_type": "conceptual",
                    },
                ],
            },
            {
                "name": "Section B — Long Answer (50 marks)",
                "instructions": "Answer any two questions.",
                "questions": [
                    {
                        "question_number": 3,
                        "marks": 25,
                        "question_text": QUESTION_TEXTS[3],
                        "unit": 3,
                        "topic": "CRISP-DM",
                        "bloom_level": "L3",
                        "difficulty": "hard",
                        "question_type": "conceptual",
                    },
                    {
                        "question_number": 4,
                        "marks": 25,
                        "question_text": QUESTION_TEXTS[4],
                        "unit": 4,
                        "topic": "Association Rules",
                        "bloom_level": "L3",
                        "difficulty": "medium",
                        "question_type": "conceptual",
                    },
                ],
            },
        ],
    }

# Globals populated by the autouse fixture — consumed by sync token helpers
_faculty_user_id: str = ""
_admin_user_id: str = ""
_plain_user_id: str = ""
_paper_id: str = ""
_version_id: str = ""
_paper2_id: str = ""
_version2_id: str = ""
_draft_paper_id: str = ""
# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def _db_lifecycle() -> None:
    """Create tables, seed data, yield, then drop tables + clean exports.

    Also installs (and restores) the ``get_db`` dependency override so this
    module can coexist with other test modules that share the same app.
    """
    global _faculty_user_id, _admin_user_id, _plain_user_id
    global _paper_id, _version_id, _paper2_id, _version2_id, _draft_paper_id

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _get_test_db
    try:
        # --- create tables ----------------------------------------------------
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # --- seed ---------------------------------------------------------------
        async with TestSession() as session:
            # Roles
            faculty_role = Role(name="faculty", description="Faculty member")
            admin_role = Role(name="admin", description="Administrator")
            session.add_all([faculty_role, admin_role])
            await session.flush()

            # Users
            faculty_user = User(
                email="faculty@test.com",
                full_name="Test Faculty",
                password_hash=security.hash_password("SecurePass1!"),
                is_active=True,
                roles=[faculty_role],
            )
            admin_user = User(
                email="admin@test.com",
                full_name="Test Admin",
                password_hash=security.hash_password("SecurePass1!"),
                is_active=True,
                roles=[admin_role],
            )
            plain_user = User(
                email="plain@test.com",
                full_name="Plain User",
                password_hash=security.hash_password("SecurePass1!"),
                is_active=True,
                roles=[],
            )
            session.add_all([faculty_user, admin_user, plain_user])
            await session.flush()

            # Academic chain: Subject -> QuestionBlueprint -> GenerationJob
            subject = Subject(
                code="CS-402",
                name="Data Mining",
                department="Computer Science",
                is_active=True,
            )
            session.add(subject)
            await session.flush()

            blueprint = QuestionBlueprint(
                exam_type="midterm",
                subject_id=subject.id,
                source_mode="auto",
                blueprint_json={},
                validation_status="validated",
            )
            session.add(blueprint)
            await session.flush()

            job = GenerationJob(
                blueprint_id=blueprint.id,
                status="completed",
                current_step="done",
                progress_percent=100,
            )
            session.add(job)
            await session.flush()

            # Approved paper + version
            _paper_id = str(uuid4())
            _version_id = str(uuid4())
            paper = GeneratedPaper(
                id=_paper_id,
                generation_job_id=job.id,
                title="Midterm Exam Paper",
                status="approved",
            )
            session.add(paper)
            await session.flush()

            version = PaperVersion(
                id=_version_id,
                generated_paper_id=paper.id,
                version_number=1,
                paper_json=_make_paper_json(_version_id),
                blueprint_version={},
                rules_version={},
                validation_summary={},
            )
            session.add(version)
            await session.flush()
            paper.current_version_id = version.id
            await session.flush()

            # Draft (unapproved) paper — for error-path tests
            _draft_paper_id = str(uuid4())
            draft_paper = GeneratedPaper(
                id=_draft_paper_id,
                generation_job_id=job.id,
                title="Draft Paper",
                status="draft",
            )
            session.add(draft_paper)
            await session.flush()

            draft_version = PaperVersion(
                generated_paper_id=draft_paper.id,
                version_number=1,
                paper_json=_make_paper_json(_draft_paper_id),
                blueprint_version={},
                rules_version={},
                validation_summary={},
            )
            session.add(draft_version)
            await session.flush()

            # Second approved paper — used by the cross-paper multi-format test
            _paper2_id = str(uuid4())
            _version2_id = str(uuid4())
            paper2 = GeneratedPaper(
                id=_paper2_id,
                generation_job_id=job.id,
                title="Final Exam Paper",
                status="approved",
            )
            session.add(paper2)
            await session.flush()

            version2 = PaperVersion(
                id=_version2_id,
                generated_paper_id=paper2.id,
                version_number=1,
                paper_json=_make_paper_json(_version2_id),
                blueprint_version={},
                rules_version={},
                validation_summary={},
            )
            session.add(version2)
            await session.flush()
            paper2.current_version_id = version2.id
            await session.flush()

            # Record user IDs for token helpers
            _faculty_user_id = faculty_user.id
            _admin_user_id = admin_user.id
            _plain_user_id = plain_user.id

            await session.commit()

        yield
    finally:
        # --- cleanup ------------------------------------------------------------
        export_dir = Path("storage") / "exports"
        if export_dir.exists():
            shutil.rmtree(export_dir)

        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        # Restore the previous dependency override
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override

@pytest_asyncio.fixture
async def async_client() -> AsyncClient:
    """AsyncClient bound to the app with the test DB dependency override."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

# --- token helpers (sync — no DB access needed) -----------------------------

@pytest.fixture
def faculty_token() -> str:
    return security.create_access_token(_faculty_user_id, ["faculty"])

@pytest.fixture
def admin_token() -> str:
    return security.create_access_token(_admin_user_id, ["admin"])

@pytest.fixture
def plain_token() -> str:
    return security.create_access_token(_plain_user_id, [])

# --- paper id helpers --------------------------------------------------------

@pytest.fixture
def approved_paper_id() -> str:
    return _paper_id

@pytest.fixture
def approved_version_id() -> str:
    return _version_id

@pytest.fixture
def approved_paper2_id() -> str:
    return _paper2_id

@pytest.fixture
def draft_paper_id() -> str:
    return _draft_paper_id

# ---------------------------------------------------------------------------
# DB query helpers (async — run in the same event loop as the client)
# ---------------------------------------------------------------------------

async def _query_export_audits(paper_id: str) -> list[ExportAudit]:
    async with TestSession() as session:
        result = await session.execute(
            select(ExportAudit).where(ExportAudit.paper_id == paper_id)
        )
        return list(result.scalars().all())

async def _query_paper(paper_id: str) -> GeneratedPaper | None:
    async with TestSession() as session:
        return await session.get(GeneratedPaper, paper_id)

async def _query_paper(paper_id: str) -> GeneratedPaper | None:
    async with TestSession() as session:
        return await session.get(GeneratedPaper, paper_id)
# ---------------------------------------------------------------------------
# 1 + 4 — PDF export success + valid structure
# ---------------------------------------------------------------------------

async def test_export_pdf_success_and_valid_structure(
    async_client: AsyncClient,
    faculty_token: str,
    approved_paper_id: str,
) -> None:
    resp = await async_client.post(
        "/api/papers/export",
        json={"paper_id": approved_paper_id, "format": "pdf"},
        headers={"Authorization": f"Bearer {faculty_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "file_path" in data
    assert data["format"] == "pdf"

    pdf_path = Path(data["file_path"])
    assert pdf_path.exists(), f"PDF file not created: {pdf_path}"
    assert pdf_path.stat().st_size > 0

    with open(pdf_path, "rb") as f:
        raw = f.read()
    assert raw.startswith(b"%PDF"), "File does not start with the PDF header"

    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) >= 1, "PDF must contain at least one page"

# ---------------------------------------------------------------------------
# 2 + 3 — DOCX export success + exact question text
# ---------------------------------------------------------------------------

async def test_export_docx_contains_exact_question_text(
    async_client: AsyncClient,
    faculty_token: str,
    approved_paper_id: str,
) -> None:
    resp = await async_client.post(
        "/api/papers/export",
        json={"paper_id": approved_paper_id, "format": "docx"},
        headers={"Authorization": f"Bearer {faculty_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["format"] == "docx"

    docx_path = Path(data["file_path"])
    assert docx_path.exists(), f"DOCX file not created: {docx_path}"
    assert docx_path.stat().st_size > 0

    from docx import Document as DocxDocument

    document = DocxDocument(str(docx_path))
    all_text = "\n".join(p.text for p in document.paragraphs)

    for q_text in QUESTION_TEXTS.values():
        assert q_text in all_text, f"Question text missing from DOCX: {q_text!r}"

# ---------------------------------------------------------------------------
# 5 + 6 + 8 — ExportAudit / paper-status / AuditLog persistence
# ---------------------------------------------------------------------------

async def test_export_persists_audit_status_and_log(
    async_client: AsyncClient,
    faculty_token: str,
    approved_paper_id: str,
    approved_version_id: str,
) -> None:
    resp = await async_client.post(
        "/api/papers/export",
        json={"paper_id": approved_paper_id, "format": "pdf"},
        headers={"Authorization": f"Bearer {faculty_token}"},
    )
    assert resp.status_code == 200, resp.text

    # --- ExportAudit record -------------------------------------------------
    audits = await _query_export_audits(approved_paper_id)
    assert len(audits) == 1, f"Expected 1 audit record, got {len(audits)}"
    audit = audits[0]
    assert audit.paper_id == approved_paper_id
    assert audit.approved_version == approved_version_id
    assert audit.exported_by == _faculty_user_id, (
        f"exported_by should be the faculty user UUID, got {audit.exported_by!r}"
    )
    assert audit.format == ExportFormat.pdf

    # --- GeneratedPaper status is preserved ("approved") ----------------------
    # Exporting must not mutate an approved paper into a non-exportable state.
    paper = await _query_paper(approved_paper_id)
    assert paper is not None
    assert paper.status == "approved", f"Expected status 'approved', got {paper.status!r}"

# ---------------------------------------------------------------------------
# 9 — Unapproved (draft) paper → 400
# ---------------------------------------------------------------------------

async def test_export_unapproved_paper_rejected(
    async_client: AsyncClient,
    faculty_token: str,
    draft_paper_id: str,
) -> None:
    resp = await async_client.post(
        "/api/papers/export",
        json={"paper_id": draft_paper_id, "format": "pdf"},
        headers={"Authorization": f"Bearer {faculty_token}"},
    )
    assert resp.status_code == 400
    assert "not approved" in resp.json()["detail"].lower()

# ---------------------------------------------------------------------------
# 10 — Missing paper → 400
# ---------------------------------------------------------------------------

async def test_export_missing_paper_rejected(
    async_client: AsyncClient,
    faculty_token: str,
) -> None:
    resp = await async_client.post(
        "/api/papers/export",
        json={"paper_id": "does-not-exist", "format": "pdf"},
        headers={"Authorization": f"Bearer {faculty_token}"},
    )
    assert resp.status_code == 400

# ---------------------------------------------------------------------------
# 11 — User with no roles → 403
# ---------------------------------------------------------------------------

async def test_export_user_with_no_roles_rejected(
    async_client: AsyncClient,
    plain_token: str,
    approved_paper_id: str,
) -> None:
    resp = await async_client.post(
        "/api/papers/export",
        json={"paper_id": approved_paper_id, "format": "pdf"},
        headers={"Authorization": f"Bearer {plain_token}"},
    )
    assert resp.status_code == 403

# ---------------------------------------------------------------------------
# 12 — Missing auth token → 401
# ---------------------------------------------------------------------------

async def test_export_without_token_rejected(
    async_client: AsyncClient,
    approved_paper_id: str,
) -> None:
    resp = await async_client.post(
        "/api/papers/export",
        json={"paper_id": approved_paper_id, "format": "pdf"},
    )
    assert resp.status_code == 401

# ---------------------------------------------------------------------------
# 13 — Admin-role user can export
# ---------------------------------------------------------------------------

async def test_export_admin_can_export(
    async_client: AsyncClient,
    admin_token: str,
    approved_paper_id: str,
) -> None:
    resp = await async_client.post(
        "/api/papers/export",
        json={"paper_id": approved_paper_id, "format": "pdf"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text

    audits = await _query_export_audits(approved_paper_id)
    assert len(audits) == 1
    assert audits[0].exported_by == _admin_user_id

# ---------------------------------------------------------------------------
# 14 — Invalid format → 422 (Pydantic validation)
# ---------------------------------------------------------------------------

async def test_export_invalid_format_rejected(
    async_client: AsyncClient,
    faculty_token: str,
    approved_paper_id: str,
) -> None:
    resp = await async_client.post(
        "/api/papers/export",
        json={"paper_id": approved_paper_id, "format": "exe"},
        headers={"Authorization": f"Bearer {faculty_token}"},
    )
    assert resp.status_code == 422

# ---------------------------------------------------------------------------
# 15 — Response shape
# ---------------------------------------------------------------------------

async def test_export_response_shape(
    async_client: AsyncClient,
    faculty_token: str,
    approved_paper_id: str,
) -> None:
    resp = await async_client.post(
        "/api/papers/export",
        json={"paper_id": approved_paper_id, "format": "pdf"},
        headers={"Authorization": f"Bearer {faculty_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert set(data.keys()) == {"file_path", "format"}

# ---------------------------------------------------------------------------
# 16 — ExportAudit.timestamp is auto-populated
# ---------------------------------------------------------------------------

async def test_export_audit_timestamp_is_set(
    async_client: AsyncClient,
    faculty_token: str,
    approved_paper_id: str,
) -> None:
    resp = await async_client.post(
        "/api/papers/export",
        json={"paper_id": approved_paper_id, "format": "pdf"},
        headers={"Authorization": f"Bearer {faculty_token}"},
    )
    assert resp.status_code == 200, resp.text

    audits = await _query_export_audits(approved_paper_id)
    assert len(audits) == 1
    assert audits[0].timestamp is not None

# ---------------------------------------------------------------------------
# 17 — PDF then DOCX both work, producing two audit records
# ---------------------------------------------------------------------------

async def test_export_pdf_and_docx_sequential(
    async_client: AsyncClient,
    faculty_token: str,
    approved_paper_id: str,
    approved_paper2_id: str,
) -> None:
    pdf_resp = await async_client.post(
        "/api/papers/export",
        json={"paper_id": approved_paper_id, "format": "pdf"},
        headers={"Authorization": f"Bearer {faculty_token}"},
    )
    assert pdf_resp.status_code == 200, pdf_resp.text

    docx_resp = await async_client.post(
        "/api/papers/export",
        json={"paper_id": approved_paper2_id, "format": "docx"},
        headers={"Authorization": f"Bearer {faculty_token}"},
    )
    assert docx_resp.status_code == 200, docx_resp.text

    # Two audit records — one per paper/format
    audits = await _query_export_audits(approved_paper_id)
    assert len(audits) == 1
    assert audits[0].format == ExportFormat.pdf

    audits2 = await _query_export_audits(approved_paper2_id)
    assert len(audits2) == 1
    assert audits2[0].format == ExportFormat.docx

async def test_export_approved_paper_can_be_reexported(
    async_client: AsyncClient,
    faculty_token: str,
    approved_paper_id: str,
    approved_version_id: str,
) -> None:
    """An approved paper can be exported repeatedly.

    Each export writes a fresh ExportAudit row, reuses the exact same approved
    PaperVersion, and does NOT mutate the paper's approval status.
    """
    first = await async_client.post(
        "/api/papers/export",
        json={"paper_id": approved_paper_id, "format": "pdf"},
        headers={"Authorization": f"Bearer {faculty_token}"},
    )
    assert first.status_code == 200, first.text

    second = await async_client.post(
        "/api/papers/export",
        json={"paper_id": approved_paper_id, "format": "docx"},
        headers={"Authorization": f"Bearer {faculty_token}"},
    )
    assert second.status_code == 200, second.text

    # Two separate ExportAudit records — one per export
    audits = await _query_export_audits(approved_paper_id)
    assert len(audits) == 2, f"Expected 2 audit records, got {len(audits)}"
    formats = {a.format for a in audits}
    assert formats == {ExportFormat.pdf, ExportFormat.docx}
    # Both exports reference the same approved PaperVersion
    assert {a.approved_version for a in audits} == {approved_version_id}

    # Paper status is preserved — still approved / exportable
    paper = await _query_paper(approved_paper_id)
    assert paper is not None
    assert paper.status == "approved", f"Expected status 'approved', got {paper.status!r}"

