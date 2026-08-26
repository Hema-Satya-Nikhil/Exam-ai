from typing import Dict, List, Any
import os
import re
from PyMuPDF import fitz  # For PDF parsing
from docx import Document  # For DOCX parsing

class ModelPaperAnalyzer:
    def __init__(self):
        self.sections = []
        self.marks_distribution = {}
        self.question_types = set()

    def analyze_model_paper(self, file_path: str) -> Dict[str, Any]:
        try:
            # Extract text based on file type
            if file_path.lower().endswith('.pdf'):
                text = self._extract_pdf(file_path)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()

            # Parse sections and marks
            self._parse_sections(text)
            self._parse_marks_distribution(text)
            self._parse_question_types(text)

            return {
                'sections': self.sections,
                'marks_distribution': self.marks_distribution,
                'question_types': list(self.question_types),
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

    def _parse_sections(self, text: str) -> None:
        # Look for section headers (e.g., 'Section 1: Theory')
        section_pattern = re.compile(r'Section \d+:\s*(.*?)(?=\n\n|$)', re.DOTALL)
        for match in section_pattern.finditer(text):
            self.sections.append({
                'id': len(self.sections) + 1,
                'name': match.group(1).strip()
            })

    def _parse_marks_distribution(self, text: str) -> None:
        # Look for marks allocation patterns (e.g., 'Theory: 40 marks')
        marks_pattern = re.compile(r'(\w+):\s*(\d+)\s*marks', re.IGNORECASE)
        for match in marks_pattern.finditer(text):
            self.marks_distribution[match.group(1).strip()] = int(match.group(2))

    def _parse_question_types(self, text: str) -> None:
        # Look for question type indicators (e.g., 'MCQ', 'Short Answer')
        qtype_pattern = re.compile(r'(\bMCQ\b|\bShort Answer\b|\bEssay\b)', re.IGNORECASE)
        for match in qtype_pattern.finditer(text):
            self.question_types.add(match.group(1).strip())