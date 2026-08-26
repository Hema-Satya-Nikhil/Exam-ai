from pathlib import Path

from app.services.documents.paper_renderer import PaperRenderer


def test_paper_renderer_exports_files(tmp_path: Path) -> None:
    renderer = PaperRenderer()
    paper_json = {
        "paper_id": "paper-1",
        "institution_name": "AI-Based Question Paper Generation System",
        "department_name": "Department of Computer Science",
        "exam_name": "Mid 1",
        "subject_name": "Data Mining",
        "subject_code": "CSE-402",
        "duration_minutes": 180,
        "total_marks": 70,
        "instructions": ["Answer all questions."],
        "sections": [
            {
                "name": "Part A",
                "instructions": "Short answers",
                "questions": [
                    {"question_number": 1, "marks": 2, "question_text": "Define clustering."},
                ],
            }
        ],
    }

    pdf_path = renderer.export(paper_json, tmp_path, "pdf")
    docx_path = renderer.export(paper_json, tmp_path, "docx")

    assert pdf_path.exists()
    assert docx_path.exists()
