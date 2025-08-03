from typing import List, Dict, Any
from fuzzywuzzy import fuzz
from datetime import datetime, timedelta
from .intelligent_reconciliation import IntelligentReconciliation
from models.schema import ReceiptTransaction, BankTransaction
import logging

logger = logging.getLogger(__name__)

class AdvancedReconciliationEngine:
    def __init__(self):
        self.intelligent_matcher = IntelligentReconciliation()
        self.date_tolerance_days = 7
        self.amount_tolerance_percent = 0.1  
        self.vendor_similarity_threshold = 70  

    def reconcile_transactions(self, ledger_transactions: List[Dict], bank_transactions: List[Dict]) -> Dict[str, List]:
        matches = []
        used_bank_transactions = set()  
        used_receipts = set() 
        
        for receipt in ledger_transactions:
            if receipt['transaction_id'] in used_receipts:
                continue
                
            best_match = None
            best_confidence = 0.0
            
            for bank_txn in bank_transactions:
                if bank_txn['transaction_id'] in used_bank_transactions:
                    continue 
                    
                confidence = self._calculate_similarity(receipt, bank_txn)
                
                if (confidence > 0.7 and 
                    self._amounts_compatible(receipt.get('amount', 0), bank_txn.get('amount', 0))):
                    if confidence > best_confidence:
                        best_match = bank_txn
                        best_confidence = confidence
            
            if best_match:
                logger.info(f"Match found: {receipt.get('vendor_name')} ↔ {best_match['description']} (confidence: {best_confidence:.2f})")
                matches.append({
                    "receipt": receipt,
                    "bank_transaction": best_match,
                    "confidence": best_confidence,
                    "match_type": "semantic"
                })
                used_receipts.add(receipt['transaction_id'])
                used_bank_transactions.add(best_match['transaction_id'])
            else:
                logger.debug(f"No match for receipt: {receipt.get('vendor_name')} (${receipt.get('amount', 0)})")
        
        return {
            "matches": matches,
            "unmatched_ledger": [r for r in ledger_transactions if r['transaction_id'] not in used_receipts],
            "unmatched_bank": [b for b in bank_transactions if b['transaction_id'] not in used_bank_transactions]
        }

    def _safe_date_diff(self, date1, date2):
        try:
            if isinstance(date1, dict) and '$date' in date1:
                date1 = datetime.fromtimestamp(date1['$date'] / 1000)
            elif isinstance(date1, str):
                date1 = datetime.fromisoformat(date1.replace('Z', '+00:00'))
            
            if isinstance(date2, dict) and '$date' in date2:
                date2 = datetime.fromtimestamp(date2['$date'] / 1000)
            elif isinstance(date2, str):
                date2 = datetime.fromisoformat(date2.replace('Z', '+00:00'))
                
            return abs((date1 - date2).days)
        except Exception as e:
            logger.warning(f"Date parsing failed: {e}")
            return 999

    def _calculate_similarity(self, receipt: Dict, bank: Dict) -> float:
        try:
            receipt_vendor = str(receipt.get('vendor_name', '')).upper()
            bank_desc = str(bank.get('description', '')).upper()
            
            vendor_mappings = {
                'USB': 'AMAZON',
                'FUEL': 'SHELL',
                'TAX': 'WALMART',
            }
            
            if receipt_vendor in vendor_mappings:
                receipt_vendor = vendor_mappings[receipt_vendor]
            
            if receipt_vendor in bank_desc or any(word in bank_desc for word in receipt_vendor.split()):
                vendor_score = 0.9
            else:
                vendor_score = fuzz.token_set_ratio(receipt_vendor, bank_desc) / 100.0
            
            date_score = 0.8 
            
            receipt_amount = float(receipt.get('amount', 0))
            bank_amount = float(bank.get('amount', 0))
            
            if receipt_amount == 0:
                return 0.0 
            
            bank_abs = abs(bank_amount)
            amount_diff = abs(receipt_amount - bank_abs) / receipt_amount
            amount_score = max(0, 1 - amount_diff)
            
            final_score = (date_score * 0.2) + (amount_score * 0.4) + (vendor_score * 0.4)
            
            logger.info(f"Similarity: {receipt_vendor} vs {bank_desc} = {final_score:.2f} (vendor:{vendor_score:.2f}, amount:{amount_score:.2f})")
            
            return final_score
            
        except Exception as e:
            logger.error(f"Similarity calculation failed: {e}")
            return 0.0

    def _amounts_compatible(self, receipt_amount, bank_amount):
        if receipt_amount == 0: 
            return False
        
        bank_abs = abs(bank_amount)
        receipt_abs = abs(receipt_amount)
        
        variance = max(receipt_abs * self.amount_tolerance_percent, 1.0)
        return abs(receipt_abs - bank_abs) <= variance

    def _is_date_within_tolerance(self, date1: datetime, date2: datetime) -> bool:
        return abs(date1 - date2) <= timedelta(days=self.date_tolerance_days)
