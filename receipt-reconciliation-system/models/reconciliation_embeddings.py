import os
import re
from typing import List
from .embedding import CustomEmbedding

class ReconciliationEmbeddings(CustomEmbedding):
    """Optimized embeddings for transaction matching"""
    
    def __init__(self):
        super().__init__(
            api_url=os.getenv("EMBEDDING_API_URL"),
            api_key=os.getenv("MODELS_API_KEY"),
            model="usf1-embed"
        )
        # Smaller batch size for real-time processing
        self.embed_batch_size = 16
        self.max_text_length = 500  # Shorter for transaction descriptions
    
    def embed_transactions(self, transactions: List[str]) -> List[List[float]]:
        """Specialized method for transaction embedding"""
        # Preprocess transaction text for better matching
        processed = [self._preprocess_transaction(tx) for tx in transactions]
        return self._embed(processed)
    
    def _preprocess_transaction(self, transaction_text: str) -> str:
        """Clean and normalize transaction text for better matching"""
        # Remove common noise words, normalize amounts, etc.
        text = re.sub(r'[^\w\s.-]', ' ', transaction_text.lower())
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:self.max_text_length]
