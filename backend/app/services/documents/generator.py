from __future__ import annotations

from pathlib import Path

from app.services.documents.renderer import StructuredPaperRenderer


class DocumentGenerator:
    def __init__(self) -> None:
        self.renderer = StructuredPaperRenderer()

    def render_pdf(self, paper_json: dict, output_path: Path) -> Path:
        return self.renderer.render_pdf(paper_json, output_path)

    def render_docx(self, paper_json: dict, output_path: Path) -> Path:
        return self.renderer.render_docx(paper_json, output_path)
