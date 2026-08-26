from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings


@dataclass(slots=True)
class MongoConnectionSettings:
    uri: str = settings.mongodb_uri
    database: str = settings.mongodb_database


class MongoConnectionPlaceholder:
    def __init__(self) -> None:
        self.settings = MongoConnectionSettings()

    def describe(self) -> dict[str, str]:
        return {
            "uri": self.settings.uri,
            "database": self.settings.database,
            "status": "not connected",
        }
