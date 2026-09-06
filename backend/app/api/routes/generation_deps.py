"""Shared guards for generation-job routes."""
from __future__ import annotations

from fastapi import HTTPException, status

from app.models.academic import User
from app.models.generation import GenerationJob


def ensure_job_access(job: GenerationJob, current_user: User) -> None:
    """Faculty ownership: only the creating user (or an admin) may view,
    resume, or cancel a generation job."""
    if current_user.has_role("admin"):
        return
    if job.created_by is not None and job.created_by != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this generation job.",
        )
