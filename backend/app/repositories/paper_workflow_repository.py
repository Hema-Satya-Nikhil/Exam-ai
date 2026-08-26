from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.generation import GeneratedPaper, GeneratedQuestion, PaperVersion


@dataclass
class PaperWorkflowRepository:
    session: AsyncSession

    async def get_paper(self, paper_id: str) -> GeneratedPaper | None:
        return await self.session.get(GeneratedPaper, paper_id)

    async def get_latest_version(self, paper_id: str) -> PaperVersion | None:
        result = await self.session.execute(
            select(PaperVersion)
            .where(PaperVersion.generated_paper_id == paper_id)
            .order_by(PaperVersion.version_number.desc())
        )
        return result.scalars().first()

    async def list_papers(self) -> Sequence[GeneratedPaper]:
        result = await self.session.execute(select(GeneratedPaper).order_by(GeneratedPaper.id.desc()))
        return result.scalars().all()

    async def update_paper_status(self, paper_id: str, status: str) -> GeneratedPaper | None:
        paper = await self.get_paper(paper_id)
        if paper:
            paper.status = status
            await self.session.flush()
        return paper

    async def update_paper_version_json(self, paper_id: str, new_paper_json: dict) -> PaperVersion | None:
        latest = await self.get_latest_version(paper_id)
        if latest:
            latest.paper_json = new_paper_json
            await self.session.flush()
            return latest

        # Create version 1 if no version exists yet
        version = PaperVersion(
            generated_paper_id=paper_id,
            version_number=1,
            paper_json=new_paper_json,
            blueprint_version={},
            rules_version={},
            validation_summary={},
        )
        self.session.add(version)
        await self.session.flush()

        paper = await self.get_paper(paper_id)
        if paper:
            paper.current_version_id = version.id
            await self.session.flush()

        return version

    async def log_action(self, action: str, entity_type: str, entity_id: str | None = None, payload: dict | None = None, actor_id: str | None = None) -> AuditLog:
        log = AuditLog(
            actor_user_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload or {},
        )
        self.session.add(log)
        await self.session.flush()
        return log
