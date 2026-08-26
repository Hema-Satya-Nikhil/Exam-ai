from __future__ import annotations

from pathlib import Path

from app.services.documents.generator import DocumentGenerator


class PaperRenderer:
    def __init__(self) -> None:
        self.generator = DocumentGenerator()

    def export(self, paper_json: dict, output_dir: Path, format_name: str) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"paper.{format_name}"
        if format_name == "pdf":
            return self.generator.render_pdf(paper_json, output_path)
        return self.generator.render_docx(paper_json, output_path)
