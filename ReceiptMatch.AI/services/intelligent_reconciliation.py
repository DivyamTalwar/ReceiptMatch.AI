from models.reconciliation_embeddings import ReconciliationEmbeddings
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from typing import List, Dict

class IntelligentReconciliation:
    def __init__(self):
        self.embeddings = ReconciliationEmbeddings()
    
    def find_matches(self, receipts: List[Dict], bank_transactions: List[Dict]) -> List[Dict]:
        if not receipts or not bank_transactions:
            return []

        receipt_texts = [f"{r.get('vendor', '')} {r.get('amount', '')}" for r in receipts]
        bank_texts = [f"{b.get('description', '')} {b.get('amount', '')}" for b in bank_transactions]
        
        receipt_embeddings = self.embeddings.embed_transactions(receipt_texts)
        bank_embeddings = self.embeddings.embed_transactions(bank_texts)
        
        similarity_matrix = cosine_similarity(receipt_embeddings, bank_embeddings)
        
        matches = []
        for i, receipt in enumerate(receipts):
            if i < len(similarity_matrix):
                best_match_idx = np.argmax(similarity_matrix[i])
                confidence = similarity_matrix[i][best_match_idx]
                
                if confidence > 0.7:  
                    matches.append({
                        'receipt': receipt,
                        'bank_transaction': bank_transactions[best_match_idx],
                        'confidence': float(confidence),
                        'match_type': 'semantic'
                    })
        
        return matches
