from pathlib import Path

from app.services.documents.generator import DocumentGenerator


def test_document_generator_writes_pdf_and_docx(tmp_path: Path) -> None:
    generator = DocumentGenerator()
    paper = {
        "institution_name": "AI-Based Question Paper Generation System",
        "department_name": "Department of Computer Science",
        "exam_name": "Mid 1",
        "subject_name": "Data Mining",
        "subject_code": "CSE-402",
        "duration_minutes": 180,
        "total_marks": 70,
        "instructions": ["Answer all questions."] ,
        "sections": [
            {
                "name": "Part A",
                "instructions": "Short answers",
                "questions": [
                    {"question_number": 1, "marks": 2, "question_text": "Define clustering."},
                    {"question_number": 2, "marks": 2, "question_text": "Explain classification."},
                ],
            }
        ],
    }

    pdf_path = generator.render_pdf(paper, tmp_path / "paper.pdf")
    docx_path = generator.render_docx(paper, tmp_path / "paper.docx")

    assert pdf_path.exists()
    assert docx_path.exists()
    assert pdf_path.stat().st_size > 0
    assert docx_path.stat().st_size > 0
