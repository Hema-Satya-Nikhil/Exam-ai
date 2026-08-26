from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from mongoengine import Document, StringField, DateTimeField, ReferenceField, IntField

class ExportAuditModel(BaseModel):
    paper_id: str
    approved_version: str
    exported_by: str
    format: str
    timestamp: datetime = datetime.utcnow()

class ExportAudit(Document):
    paper_id = StringField(required=True)
    approved_version = StringField(required=True)
    exported_by = StringField(required=True)
    format = StringField(required=True)
    timestamp = DateTimeField(default=datetime.utcnow)

    def to_model(self) -> ExportAuditModel:
        return ExportAuditModel(**self.to_json())


class ExportAuditRepository:
    @staticmethod
    def save(audit: ExportAuditModel) -> ExportAudit:
        return ExportAudit(**audit.dict()).save()

    @staticmethod
    def get_by_paper_id(paper_id: str) -> list:
        return ExportAudit.objects(paper_id=paper_id)