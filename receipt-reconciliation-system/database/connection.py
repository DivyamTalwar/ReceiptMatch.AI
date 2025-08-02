from mongoengine import connect, disconnect
from mongoengine.connection import get_connection
from pymongo.errors import ConnectionFailure
from config.database import MongoConfig

def connect_to_db():
    """
    Connects to the MongoDB database using the URI from the config.
    If a connection already exists, it does nothing.
    """
    try:
        # Check if a connection already exists by trying to get it
        get_connection()
    except Exception:
        # If no connection exists, create a new one
        mongo_config = MongoConfig()
        mongo_uri = mongo_config.get_mongo_uri()
        try:
            connect(host=mongo_uri)
            print("Successfully connected to MongoDB.")
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")
            raise

def disconnect_from_db():
    """
    Disconnects from the MongoDB database.
    """
    disconnect()
    print("Disconnected from MongoDB.")

def check_db_connection():
    """
    Checks if the database connection is alive using MongoEngine's connection.
    """
    try:
        connection = get_connection()
        db = connection.get_database()
        # Simple collection count - no regex needed
        db.list_collection_names()
        return True
    except Exception as e:
        print(f"Database connection check failed: {e}")
        return False

