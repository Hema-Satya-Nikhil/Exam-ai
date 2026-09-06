"""Seed one completed composite paper for the browser E2E (e2e/review.spec.ts).

Creates a subject, uploads + confirms the real OS syllabus (atomic topics),
then runs a full MID 1 composite generation (Part A 10x2, Part B 30 marks with
an OR pair) through the live backend API. Prints the paper id last so callers
(`npm run e2e:seed`) can forward it to Playwright as E2E_PAPER_ID.

Run from backend/ with the API live on :8000:
    ..\\.venv\\Scripts\\python.exe e2e_seed_paper.py
"""
from __future__ import annotations

import asyncio
import sys
import time
from uuid import uuid4

import httpx

API = "http://127.0.0.1:8000"
SUBJECT_CODE = f"OSE2E{uuid4().hex[:5].upper()}"

SYLLABUS_TEXT = """Operating Systems - Syllabus
UNIT I
Processes: Process Concept, Process scheduling, Operations on processes, Inter-process communication.
Threads and Concurrency: Multithreading models, Thread libraries.
UNIT II
CPU Scheduling: Scheduling criteria, Scheduling algorithms, Thread scheduling.
Deadlocks: System model, Deadlock characterization, Methods for handling deadlocks.
"""

TOPIC_U1 = ["Process Concept", "Process scheduling", "Operations on processes",
            "Inter-process communication", "Multithreading models", "Thread libraries"]
TOPIC_U2 = ["Scheduling criteria", "Scheduling algorithms", "Thread scheduling",
            "System model", "Deadlock characterization", "Methods for handling deadlocks"]


async def main() -> int:
    from sqlalchemy import select

    from app.db.session import async_session_maker
    from app.models.academic import Subject

    async with async_session_maker() as s:
        s.add(Subject(code=SUBJECT_CODE, name="Operating Systems",
                      department="CSE", is_active=True))
        await s.commit()
        subject_id = (await s.execute(
            select(Subject.id).where(Subject.code == SUBJECT_CODE))).scalar_one()

    async with httpx.AsyncClient(base_url=API, timeout=600) as c:
        r = await c.post("/api/auth/login", json={
            "email": "faculty@examcraft.ai", "password": "faculty123"})
        if r.status_code != 200:
            print(f"SEED FAILED: login {r.status_code} {r.text[:200]}")
            return 1
        c.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

        r = await c.post("/api/syllabi/parse", json={
            "subject_id": subject_id, "file_name": "os_syllabus.txt",
            "extracted_text": SYLLABUS_TEXT})
        parsed = r.json()
        units = [{"unit_number": u["unit_number"], "title": u.get("title"),
                  "topics": [t["topic_name"] if isinstance(t, dict) else t
                             for t in u["topics"]]} for u in parsed["units"]]
        r = await c.post("/api/syllabi/confirm", json={
            "subject_id": subject_id, "source_file_name": "os_syllabus.txt",
            "units": units})
        if r.status_code != 201:
            print(f"SEED FAILED: confirm {r.status_code} {r.text[:200]}")
            return 1

        exam_config = {
            "exam_type": "MID 1", "subject": SUBJECT_CODE, "selected_units": [1, 2],
            "part_a": {"question_count": 10, "marks_per_question": 2,
                       "total_marks": 20, "duration_minutes": 20,
                       "selected_units": [1, 2],
                       "bloom_distribution": {"by_level": {"L2": 5, "L3": 5}},
                       "allowed_question_types": ["short_answer", "recall"]},
            "part_b": {"total_marks": 30, "duration_minutes": 90,
                       "selected_units": [1, 2], "source_mode": "manual",
                       "groups": [
                           {"group_number": 1, "choice_group": None, "parts": [{
                               "question_number": 1, "part_label": "a", "marks": 10,
                               "unit": 1, "topic": TOPIC_U1[0], "bloom_level": "L3",
                               "question_type": "analytical"}]},
                           {"group_number": 2, "choice_group": "cg1", "parts": [{
                               "question_number": 2, "part_label": "a", "marks": 10,
                               "unit": 2, "topic": TOPIC_U2[1], "bloom_level": "L4",
                               "question_type": "analytical",
                               "choice_member": "2a"}]},
                           {"group_number": 3, "choice_group": "cg1", "parts": [{
                               "question_number": 3, "part_label": "a", "marks": 10,
                               "unit": 2, "topic": TOPIC_U2[4], "bloom_level": "L4",
                               "question_type": "analytical",
                               "choice_member": "3a"}]},
                           {"group_number": 4, "choice_group": None, "parts": [{
                               "question_number": 4, "part_label": "a", "marks": 10,
                               "unit": 1, "topic": TOPIC_U1[3], "bloom_level": "L4",
                               "question_type": "analytical"}]},
                       ],
                       "choice_groups": [{
                           "id": "cg1", "choice_type": "multi", "select_count": 1,
                           "members": [
                               {"key": "2a", "marks": 10, "unit": 2,
                                "topic": TOPIC_U2[1], "bloom_level": "L4",
                                "question_type": "analytical"},
                               {"key": "3a", "marks": 10, "unit": 2,
                                "topic": TOPIC_U2[4], "bloom_level": "L4",
                                "question_type": "analytical"}]}]},
        }
        r = await c.post("/api/exam-generation/jobs", json={"exam_config": exam_config})
        if r.status_code != 201:
            print(f"SEED FAILED: job create {r.status_code} {r.text[:200]}")
            return 1
        job_id = r.json()["job_id"]
        print(f"job {job_id} queued (total {r.json()['total_questions']})")

        deadline = time.time() + 1800
        st: dict = {}
        while time.time() < deadline:
            st = (await c.get(f"/api/exam-generation/jobs/{job_id}")).json()
            print(f"  [poll] {st['status']} {st['progress_percent']}% "
                  f"A:{st['part_a']['completed_questions']}/{st['part_a']['total_questions']} "
                  f"B:{st['part_b']['completed_questions']}/{st['part_b']['total_questions']}")
            if st["status"] in ("completed", "failed", "cancelled"):
                break
            await asyncio.sleep(15)

        if st.get("status") != "completed":
            print(f"SEED FAILED: job {st.get('status')} {st.get('error_message') or ''}")
            return 1

        print(f"E2E_PAPER_ID={st['paper_id']}")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
