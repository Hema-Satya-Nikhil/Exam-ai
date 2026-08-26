from typing import Dict, List, Any
import os
from syllabus_parser.SyllabusParser import SyllabusParser

class UnitMaterialParser:
    def __init__(self, syllabus_parser: SyllabusParser):
        self.syllabus_parser = syllabus_parser
        self.materials = {}

    def parse_unit_materials(self, file_path: str, unit_id: int) -> Dict[str, Any]:
        try:
            # Extract text from file
            if file_path.lower().endswith('.pdf'):
                text = self._extract_pdf(file_path)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()

            # Parse materials based on unit
            self._parse_materials(text, unit_id)

            return {
                'unit_id': unit_id,
                'materials': self.materials.get(unit_id, [])}
        except Exception as e:
            return {
                'error': str(e),
                'unit_id': unit_id
            }

    def _extract_pdf(self, path: str) -> str:
        # Reuse PDF extraction logic from SyllabusParser
        import fitz
        doc = fitz.open(path)
        return ' '.join(page.get_text() for page in doc)

    def _parse_materials(self, text: str, unit_id: int) -> None:
        # Look for material sections under unit
        material_pattern = re.compile(r'\n\s*\-\s*(.*?)(?=\n\s*\-\s*|$)', re.DOTALL)
        for match in material_pattern.finditer(text):
            self.materials.setdefault(unit_id, []).append({
                'id': len(self.materials.get(unit_id, [])) + 1,
                'content': match.group(1).strip()
            })

    def get_unit_materials(self, unit_id: int) -> List[Dict[str, Any]]:
        return self.materials.get(unit_id, [])