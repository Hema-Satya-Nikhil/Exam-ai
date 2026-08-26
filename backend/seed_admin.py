import asyncio
from app.db.session import async_session_maker
from app.models.academic import User, Role, user_roles
from app.core.security import SecurityService
from sqlalchemy.future import select

async def seed():
    security = SecurityService()
    async with async_session_maker() as session:
        # Create roles
        for role_name in ["admin", "faculty"]:
            result = await session.execute(select(Role).where(Role.name == role_name))
            if not result.scalars().first():
                session.add(Role(name=role_name, description=f"{role_name.capitalize()} role"))
        await session.commit()

        # Create admin user
        result = await session.execute(select(User).where(User.email == "admin@examcraft.ai"))
        admin = result.scalars().first()
        if not admin:
            admin_role = (await session.execute(select(Role).where(Role.name == "admin"))).scalars().first()
            admin = User(
                email="admin@examcraft.ai",
                full_name="System Admin",
                password_hash=security.hash_value("admin123"),
                is_active=True,
                roles=[admin_role]
            )
            session.add(admin)

        # Create faculty user
        result = await session.execute(select(User).where(User.email == "faculty@examcraft.ai"))
        faculty = result.scalars().first()
        if not faculty:
            faculty_role = (await session.execute(select(Role).where(Role.name == "faculty"))).scalars().first()
            faculty = User(
                email="faculty@examcraft.ai",
                full_name="Faculty User",
                password_hash=security.hash_value("faculty123"),
                is_active=True,
                roles=[faculty_role]
            )
            session.add(faculty)
            
        await session.commit()
        print("Database seeded with admin and faculty users.")

if __name__ == "__main__":
    asyncio.run(seed())
