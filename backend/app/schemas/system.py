from pydantic import BaseModel


class SystemSettingRead(BaseModel):
    key: str
    value: dict
