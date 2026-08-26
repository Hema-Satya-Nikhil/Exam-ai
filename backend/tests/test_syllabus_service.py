from app.services.syllabus_service import SyllabusService


def test_parse_text_detects_units_and_topics() -> None:
    text = """
    Unit 1
    Topic: Introduction to Mining
    Lesson: Data Cleaning

    Unit 2
    Topic: Clustering
    """

    result = SyllabusService().parse_text(text, "syllabus.pdf")

    assert [unit.unit_number for unit in result.units] == [1, 2]
    assert result.units[0].topics[0].topic_name == "Introduction to Mining"
    assert result.units[1].topics[0].topic_name == "Clustering"
