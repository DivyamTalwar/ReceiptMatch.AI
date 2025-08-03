from mongoengine import connect, disconnect
from mongoengine.connection import get_connection
from pymongo.errors import ConnectionFailure
from config.database import MongoConfig

def connect_to_db():
    try:
        get_connection()
    except Exception:
        mongo_config = MongoConfig()
        mongo_uri = mongo_config.get_mongo_uri()
        try:
            connect(host=mongo_uri)
            print("Successfully connected to MongoDB.")
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")
            raise

def disconnect_from_db():
    disconnect()
    print("Disconnected from MongoDB.")

def check_db_connection():
    try:
        connection = get_connection()
        db = connection.get_database()
        db.list_collection_names()
        return True
    except Exception as e:
        print(f"Database connection check failed: {e}")
        return False

