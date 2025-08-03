import magic
import os
from typing import Tuple, Optional
from config.settings import AppSettings

class FileValidator:    
    @staticmethod
    def validate_pdf(file_path: str) -> Tuple[bool, Optional[str]]:
        try:
            if not os.path.exists(file_path):
                return False, "File does not exist"
            
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            if file_size_mb > AppSettings.MAX_FILE_SIZE_MB:
                return False, f"File too large: {file_size_mb:.1f}MB (max {AppSettings.MAX_FILE_SIZE_MB}MB)"
            
            mime_type = magic.from_file(file_path, mime=True)
            if mime_type != 'application/pdf':
                return False, f"File is not a valid PDF (detected: {mime_type})"
            
            return True, None
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
