from typing import Dict, List, Any
from academic_repository import AcademicRepository
import os
import re
from PyMuPDF import fitz  # For PDF parsing
from docx import Document  # For DOCX parsing

class SyllabusParser:
    def __init__(self):
    self.academic_repo = AcademicRepository()
        self.topics = []

    def parse_syllabus(self, file_path: str) -> Dict[str, Any]:
        try:
            # Extract text based on file type
            if file_path.lower().endswith('.pdf'):
                text = self._extract_pdf(file_path)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()

            # Parse units
            self._parse_units(text)
            # Parse topics
            self._parse_topics(text)

            return {
                'units': self.units,
                'topics': self.topics,
                'file_path': file_path
            }
        except Exception as e:
            return {
                'error': str(e),
                'file_path': file_path
            }

    def _extract_pdf(self, path: str) -> str:
        doc = fitz.open(path)
        return ' '.join(page.get_text() for page in doc)

    def _parse_units(self, text: str) -> None:
        # Look for unit headers (e.g., 'Unit 1: Introduction')
        unit_pattern = re.compile(r'Unit \d+:\s*(.*?)(?=\n\n|$)', re.DOTALL)
        for match in unit_pattern.finditer(text):
            self.units.append({
                'id': len(self.units) + 1,
                'name': match.group(1).strip()
            })

    def _parse_topics(self, text: str) -> None:
        # Look for topic headers under units
        topic_pattern = re.compile(r'\n\s*\-\s*(.*?)(?=\n\s*\-\s*|$)', re.DOTALL)
        for match in topic_pattern.finditer(text):
            self.topics.append({
                'unit_id': len(self.units),  # Link to last unit
                'name': match.group(1).strip()
            })

    def get_structured_syllabus(self) -> Dict[str, Any]:
        return {
            'units': [{
                'id': u['id'],
                'name': u['name'],
                'topics': [t for t in self.topics if t['unit_id'] == u['id']]
            } for u in self.units]
        }}