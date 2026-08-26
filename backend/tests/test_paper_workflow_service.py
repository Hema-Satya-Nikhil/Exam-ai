from app.schemas.paper_workflow import PaperDraftCreate, PaperLockRequest, PaperQuestionUpdate
from app.services.paper_workflow_service import PaperWorkflowService


def test_paper_workflow_lifecycle() -> None:
    service = PaperWorkflowService()
    draft = service.create_draft(PaperDraftCreate(title="Mid 1", paper_json={"questions": [{"question_number": 1, "question_text": "Define clustering."}]}))

    assert draft.status == "draft"

    updated = service.update_question(draft.id, PaperQuestionUpdate(question_number=1, question_text="Define clustering and explain its purpose."))
    assert updated is not None
    assert updated.paper_json["questions"][0]["question_text"] == "Define clustering and explain its purpose."

    locked = service.lock_question(draft.id, PaperLockRequest(question_number=1))
    assert locked is not None
    assert 1 in locked.locked_question_numbers

    approval = service.approve_paper(draft.id, "faculty-1", "Approved")
    assert approval is not None
    assert approval.status == "approved"
    assert approval.approved_by == "faculty-1"

    exported = service.mark_exported(draft.id)
    assert exported is not None
    assert exported.status == "exported"
