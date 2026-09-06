"""Seed the deterministic password-reset E2E test user (e2e/password-reset.spec.ts).

Idempotently upserts an ACTIVE faculty account used ONLY by the browser E2E:

    email:    test.faculty@example.test
    password: taken from E2E_RESET_PASSWORD (test-only default below)

This follows the existing project convention (e2e_seed_paper.py) of seeding
deterministic E2E fixtures into the database the local backend uses. The
password is not a real credential and is never committed to production config.
The account is re-upserted on every run so the round-trip starts from a known
password regardless of previous test runs.

Run from backend/:
    ..\\\\.venv\\\\Scripts\\\\python.exe e2e_seed_reset_user.py
"""
from __future__ import annotations

import asyncio
import os

from app.core import security
from app.db.session import async_session_maker
from app.models.academic import Role, User
from app.services.admin_service import get_or_create_role

TEST_EMAIL = "e2e.reset.faculty@test.com"
TEST_PASSWORD = os.environ.get("E2E_RESET_PASSWORD", "E2eResetPass1!")


async def main() -> int:
    async with async_session_maker() as session:
        faculty_role = await get_or_create_role(session, "faculty", "Faculty member")

        from sqlalchemy import select

        result = await session.execute(select(User).where(User.email == TEST_EMAIL))
        user = result.scalars().first()
        if user is None:
            user = User(
                email=TEST_EMAIL,
                full_name="E2E Reset Faculty",
                password_hash=security.hash_password(TEST_PASSWORD),
                is_active=True,
                roles=[faculty_role],
            )
            session.add(user)
        else:
            # Deterministic starting state for every run.
            user.password_hash = security.hash_password(TEST_PASSWORD)
            user.is_active = True
            if faculty_role not in user.roles:
                user.roles = list(user.roles) + [faculty_role]
        await session.commit()

    print(f"E2E_RESET_USER_READY: {TEST_EMAIL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
