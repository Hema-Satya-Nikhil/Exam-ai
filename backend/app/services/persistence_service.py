from __future__ import annotations

from dataclasses import dataclass

from app.db.session import async_session_maker
from app.repositories.generation_repository import GenerationRepository


@dataclass
class PersistenceService:
    async def create_generation_repository(self) -> GenerationRepository:
        session = async_session_maker()
        return GenerationRepository(session=session)
