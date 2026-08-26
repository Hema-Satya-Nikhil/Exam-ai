"""Seed the initial administrator and demo faculty accounts.

Run:  python seed_admin.py   (from the backend/ directory)

The initial administrator is driven entirely by environment variables
(``ADMIN_EMAIL`` / ``ADMIN_PASSWORD`` from ``.env``) so no credential is
hardcoded in source.  Seeding is idempotent:

* Roles are created only if missing (no duplicates).
* The admin user is created only if ``ADMIN_EMAIL`` does not already exist.
* If it already exists, the existing password is left untouched; we only ensure
  the ADMIN role is present and the account is active, and we report "EXISTS".
* Passwords are bcrypt-hashed via the existing hashing service and are never
  printed to stdout.
"""
import asyncio

from app.core.config import settings
from app.core.security import SecurityService
from app.db.session import async_session_maker
from app.models.academic import User
from app.services import admin_service


async def seed() -> None:
    security = SecurityService()
    async with async_session_maker() as session:
        roles = await admin_service.ensure_roles(session)

        admin_email = settings.admin_email.strip()
        admin_password = settings.admin_password

        if admin_email and admin_password:
            result = await admin_service.seed_admin(
                session,
                email=admin_email,
                password=admin_password,
                full_name="Initial Administrator",
            )
            print(f"ADMIN SEED STATUS: {'CREATED' if result.action == 'created' else 'EXISTS'}")
            print(f"ADMIN ROLE ASSIGNED: {'PASS' if result.role_assigned else 'FAIL'}")
            print(f"ADMIN ACCOUNT ACTIVE: {'PASS' if result.active else 'FAIL'}")
        else:
            print("ADMIN SEED STATUS: SKIPPED (ADMIN_EMAIL / ADMIN_PASSWORD not set)")

        # Legacy demo faculty account (kept for the review / E2E flow).
        if await admin_service.get_user_by_email(session, "faculty@examcraft.ai") is None:
            faculty_role = roles[admin_service.FACULTY_ROLE]
            session.add(
                User(
                    email="faculty@examcraft.ai",
                    full_name="Faculty User",
                    password_hash=security.hash_value("faculty123"),
                    is_active=True,
                    roles=[faculty_role],
                )
            )

        await session.commit()
        print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
