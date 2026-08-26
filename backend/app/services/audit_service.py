from __future__ import annotations

from app.models.audit import AuditLog


class AuditService:
    def build_entry(self, action: str, entity_type: str, entity_id: str | None, payload: dict) -> AuditLog:
        return AuditLog(action=action, entity_type=entity_type, entity_id=entity_id, payload=payload)
