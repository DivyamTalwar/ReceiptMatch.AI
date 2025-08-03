import uuid
import hashlib
from datetime import datetime
from typing import Any, Dict

class GeneralHelpers:    
    @staticmethod
    def generate_unique_id(prefix: str = "") -> str:
        unique_id = str(uuid.uuid4())
        return f"{prefix}_{unique_id}" if prefix else unique_id
    
    @staticmethod
    def hash_file(file_path: str) -> str:
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
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_')).strip()
        return f"{timestamp}_{safe_name}"
