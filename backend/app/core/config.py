from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Derive the project root from this file's location:
# backend/app/core/config.py -> backend/app/core -> backend/app -> backend -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI Question Paper Generator"
    app_version: str = "0.1.0"
    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/question_paper_generator", alias="DATABASE_URL")
    mongodb_uri: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URI")
    mongodb_database: str = Field(default="question_paper_generator", alias="MONGODB_DATABASE")
    nvidia_api_key: str = Field(default="", alias="NVIDIA_API_KEY")
    nvidia_base_url: str = Field(default="https://integrate.api.nvidia.com/v1", alias="NVIDIA_BASE_URL")
    nvidia_model: str = Field(default="", alias="NVIDIA_MODEL")
    secret_key: str = Field(default="change-me", alias="SECRET_KEY")
    admin_email: str = Field(default="", alias="ADMIN_EMAIL")
    admin_password: str = Field(default="", alias="ADMIN_PASSWORD")
    jwt_refresh_expire_days: int = Field(default=7, alias="JWT_REFRESH_EXPIRE_DAYS")
    max_upload_size: int = Field(default=52428800, alias="MAX_UPLOAD_SIZE")
    llm_timeout: int = Field(default=90, alias="LLM_TIMEOUT")
    llm_max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")
    llm_stub: bool = Field(default=False, alias="LLM_STUB")
    generation_concurrency: int = Field(default=1, alias="GENERATION_CONCURRENCY")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()