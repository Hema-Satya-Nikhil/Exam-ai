from app.services.model_paper_service import ModelPaperService


def test_analyze_model_paper_extracts_key_fields() -> None:
    text = """
    DATA MINING QUESTION PAPER
    Duration: 180 minutes
    10 Marks

    Part A
    1. Define clustering.
    2. Explain evaluation.
    """

    result = ModelPaperService().analyze(text)

    assert result.duration_minutes == 180
    assert result.total_marks == 10
    assert any(section.name == "Part A" for section in result.sections)
    assert any(finding.field == "question_numbering" for finding in result.findings)
