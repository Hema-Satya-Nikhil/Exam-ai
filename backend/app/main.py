from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging

# Activate the app's standard logging so provider attempt/success telemetry
# (sanitized: no keys, headers, prompts, or syllabus text) reaches stderr.
configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """On startup: resume generation jobs interrupted by a previous run.

    Skipped in the test environment (unit tests provide their own DB overrides
    and must not touch the production database).
    """
    if settings.app_env.lower() != "test":
        from app.services.generation_worker import resume_interrupted_jobs

        await resume_interrupted_jobs()
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)


def _cors_origins() -> list[str]:
    """Build the CORS allowed-origin list.

    Preserves the canonical local-dev origins plus any extra origins supplied
    through the environment (e.g. a LAN/device origin for local mobile testing).
    ``settings.cors_origins`` (alias CORS_ORIGINS) may hold a comma/space
    separated list of additional origins.
    """
    base = ["http://localhost:3000", "http://127.0.0.1:3000", "*"]
    extra = [
        o.strip()
        for o in (settings.cors_origins or "").replace(";", ",").split(",")
        if o.strip()
    ]
    return list(dict.fromkeys(base + extra))  # dedupe, preserve order

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}

