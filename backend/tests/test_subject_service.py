from app.schemas.subject import SubjectCreate, SubjectUpdate
from app.services.subject_service import SubjectService


def test_subject_service_create_update_delete() -> None:
    service = SubjectService()
    created = service.create_subject(SubjectCreate(code="MAT-101", name="Mathematics", department="Maths"))

    assert created.code == "MAT-101"
    assert service.get_subject(created.id) is not None

    updated = service.update_subject(created.id, SubjectUpdate(name="Advanced Mathematics", is_active=False))
    assert updated is not None
    assert updated.name == "Advanced Mathematics"
    assert updated.is_active is False

    assert service.delete_subject(created.id) is True
    assert service.get_subject(created.id) is None
