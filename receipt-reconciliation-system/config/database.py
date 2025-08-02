import os
from dotenv import load_dotenv
import gridfs
from pymongo import MongoClient

# Load environment variables from the root .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

class MongoConfig:
    """
    MongoDB Configuration Class
    """
    def __init__(self):
        self.MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
        self.DATABASE_NAME = os.getenv('MONGO_DATABASE', 'receipt_reconciliation')
        if not self.MONGO_URI:
            raise ValueError("MONGO_URI not found in environment variables. Please set it in your .env file.")

    def get_mongo_uri(self):
        """
        Returns the MongoDB connection URI.
        """
        return self.MONGO_URI

    def get_gridfs_connection(self):
        """Get GridFS connection for file storage"""
        client = MongoClient(self.MONGO_URI)
        db = client[self.DATABASE_NAME]
        return gridfs.GridFS(db)
