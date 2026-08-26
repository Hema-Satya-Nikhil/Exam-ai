from typing import Dict, Any
import os
import hashlib
from datetime import datetime
from PyMuPDF import fitz  # PyMuPDF for PDF handling
from docx import Document  # python-docx for DOCX handling

class DocumentIngestionService:
    def __init__(self, file_storage: FileStorage):
        self.file_storage = file_storage
        self.mongo_repo = AcademicRepository()  # Assuming AcademicRepository is initialized

    def upload_document(self, file_path: str, user_id: str) -> Dict[str, Any]:
        try:
            # Step 1: Store file metadata via FileStorage
            file_id = self.file_storage.upload_file(file_path, user_id)
            metadata = self.file_storage.get_file_metadata(file_id)

            # Step 2: Extract content based on file type
            if metadata['file_type'] == 'pdf':
                text = self._extract_pdf(file_path)
            elif metadata['file_type'] == 'docx':
                text = self._extract_docx(file_path)
            else:  # txt
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()

            # Step 3: Validate content
            if not text.strip():
                raise ValueError('Document contains no extractable content')

            # Step 4: Store processed content in MongoDB
            self.mongo_repo.store_document(
                file_id=file_id,
                content=text,
                metadata=metadata,
                user_id=user_id
            )

            return {
                'status': 'success',
                'file_id': file_id,
                'content_length': len(text),
                'processed_at': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
                'file_id': file_id if 'file_id' in locals() else None
            }

    def _extract_pdf(self, path: str) -> str:
        doc = fitz.open(path)
        text = ''
        for page in doc:
            text += page.get_text()
        return text

    def _extract_docx(self, path: str) -> str:
        doc = Document(path)
        return '
'.join([para.text for para in doc.paragraphs])