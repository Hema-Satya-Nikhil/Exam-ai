"""Verify transaction-rollback test pattern with Supabase PostgreSQL."""
import asyncio
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core import security
from app.models.academic import Role, User


async def main():
    print("DATABASE_URL:", settings.database_url)
    engine = create_async_engine(settings.database_url, echo=False)

    async with engine.connect() as conn:
        trans = await conn.begin()
        factory = async_sessionmaker(
            bind=conn, expire_on_commit=False, class_=AsyncSession
        )

        async def get_test_db():
            async with factory() as session:
                async with session.begin_nested():
                    yield session

        # Simulate route: session, add, commit
        async with factory() as session:
            async with session.begin_nested():
                role = Role(name="testr_" + uuid4().hex[:8], description="test")
                user = User(
                    email="test_" + uuid4().hex[:8] + "@test.com",
                    full_name="Test User",
                    password_hash=security.hash_password("SecurePass1!"),
                    is_active=True,
                    roles=[role],
                )
                session.add_all([role, user])
                await session.commit()

                result = await session.execute(
                    text("SELECT COUNT(*) FROM users WHERE email LIKE 'test_%@test.com'")
                )
                print("Users in session after commit:", result.scalar())

        result = await conn.execute(
            text("SELECT COUNT(*) FROM users WHERE email LIKE 'test_%@test.com'")
        )
        print("Users visible in outer tx:", result.scalar())

        await trans.rollback()
        await conn.close()

        async with engine.connect() as conn2:
            result = await conn2.execute(
                text("SELECT COUNT(*) FROM users WHERE email LIKE 'test_%@test.com'")
            )
            leftover = result.scalar()
            print("Leftover after rollback:", leftover)
            assert leftover == 0, "Rollback failed - test data leaked!"

    await engine.dispose()
    print("OK: Transaction-rollback pattern works!")


asyncio.run(main())