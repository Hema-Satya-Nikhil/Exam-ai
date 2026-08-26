from pymongo import MongoClient

from app.core.config import settings

class MongoDBClient:
    def __init__(self):
        self.client = MongoClient(settings.mongodb_uri)
        self.db = self.client[settings.mongodb_database]

    def get_collection(self, collection_name):
        return self.db[collection_name]

    def health_check(self):
        try:
            self.db.command("ping")
            return True
        except:
            return False

# Initialize client
mongo_client = MongoDBClient()
