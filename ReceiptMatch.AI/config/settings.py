import os
from typing import Dict, Any

class AppSettings:
    MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', '25'))
    ALLOWED_PDF_EXTENSIONS = ['.pdf']
    
    MAX_EMAILS_PER_BATCH = int(os.getenv('MAX_EMAILS_PER_BATCH', '10'))
    MAX_CONCURRENT_PROCESSING = int(os.getenv('MAX_CONCURRENT_PROCESSING', '3'))
    
    LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', '4096'))
    LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.1'))
    
    ENABLE_FILE_VALIDATION = os.getenv('ENABLE_FILE_VALIDATION', 'true').lower() == 'true'
    ENABLE_RATE_LIMITING = True
    
    @classmethod
    def get_all_settings(cls) -> Dict[str, Any]:
        return {
            'max_file_size_mb': cls.MAX_FILE_SIZE_MB,
            'allowed_extensions': cls.ALLOWED_PDF_EXTENSIONS,
            'max_emails_per_batch': cls.MAX_EMAILS_PER_BATCH,
            'max_concurrent_processing': cls.MAX_CONCURRENT_PROCESSING,
            'llm_max_tokens': cls.LLM_MAX_TOKENS,
            'llm_temperature': cls.LLM_TEMPERATURE,
        }
