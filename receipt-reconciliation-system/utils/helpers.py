import uuid
import hashlib
from datetime import datetime
from typing import Any, Dict

class GeneralHelpers:
    """General utility functions"""
    
    @staticmethod
    def generate_unique_id(prefix: str = "") -> str:
        """Generate unique ID with optional prefix"""
        unique_id = str(uuid.uuid4())
        return f"{prefix}_{unique_id}" if prefix else unique_id
    
    @staticmethod
    def hash_file(file_path: str) -> str:
        """Generate file hash for duplicate detection"""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception:
            return ""
    
    @staticmethod
    def safe_filename(filename: str) -> str:
        """Create safe filename for storage"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_')).strip()
        return f"{timestamp}_{safe_name}"
