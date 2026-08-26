from app.schemas.academic import PaperBlueprint
from app.schemas.generation import GenerationJobCreate
from app.services.generation_service import GenerationService


def test_generation_service_tracks_job_lifecycle() -> None:
    service = GenerationService()
    payload = GenerationJobCreate(
        blueprint=PaperBlueprint(
            exam_type="Mid 1",
            subject="Data Mining",
            selected_units=[1, 2],
            total_marks=10,
            duration_minutes=60,
            sections=[],
            questions=[],
            source_mode="manual",
        )
    )

    job = service.create_job(payload)
    assert job.status == "queued"

    running = service.mark_job_running(job.id, "Generating Part A", 45)
    assert running is not None
    assert running.status == "running"
    assert running.current_step == "Generating Part A"

    completed = service.mark_job_completed(job.id)
    assert completed is not None
    assert completed.status == "completed"
    assert completed.progress_percent == 100
