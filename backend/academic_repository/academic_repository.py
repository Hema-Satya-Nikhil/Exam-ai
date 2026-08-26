from typing import Dict, List, Any
from pymongo import MongoClient
from datetime import datetime

class AcademicRepository:
    def __init__(self, db_name: str = 'exam_craft'):
        self.client = MongoClient('mongodb://localhost:27017/')
        self.db = self.client[db_name]
        self.collections = {
            'subjects': self.db['subjects'],
            'syllabi': self.db['syllabi'],
            'unit_materials': self.db['unit_materials'],
            'model_papers': self.db['model_papers']
        }

    def store_syllabus(self, syllabus_data: Dict[str, Any]) -> str:
        result = self.collections['syllabi'].insert_one(syllabus_data)
        return str(result.inserted_id)

    def store_unit_materials(self, unit_materials: List[Dict[str, Any]]) -> None:
        for material in unit_materials:
            self.collections['unit_materials'].insert_one(material)

    def store_model_paper(self, model_paper_data: Dict[str, Any]) -> str:
        result = self.collections['model_papers'].insert_one(model_paper_data)
        return str(result.inserted_id)

    def get_syllabus(self, syllabus_id: str) -> Dict[str, Any]:
        return self.collections['syllabi'].find_one({'_id': syllabus_id})

    def get_unit_materials(self, unit_id: int) -> List[Dict[str, Any]]: 
        return list(self.collections['unit_materials'].find({'unit_id': unit_id}))