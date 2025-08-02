from typing import List, Dict, Any
from fuzzywuzzy import fuzz
from datetime import datetime, timedelta
from .intelligent_reconciliation import IntelligentReconciliation
from models.schema import ReceiptTransaction, BankTransaction

class AdvancedReconciliationEngine:
    """
    Implements an advanced, multi-layered transaction matching engine.
    """

    def __init__(self):
        self.intelligent_matcher = IntelligentReconciliation()
        self.date_tolerance_days = 7
        self.amount_tolerance_percent = 0.01  # 1%
        self.vendor_similarity_threshold = 80  # Fuzzy matching threshold

    def reconcile_transactions(self, ledger_transactions: List[Dict], bank_transactions: List[Dict]) -> Dict[str, List]:
        """
        Performs a multi-layered reconciliation of ledger and bank transactions.
        """
        unmatched_ledger = list(ledger_transactions)
        unmatched_bank = list(bank_transactions)
        matches = []

        # Layer 1: Exact Matching
        exact_matches, unmatched_ledger, unmatched_bank = self._find_exact_matches(unmatched_ledger, unmatched_bank)
        matches.extend(exact_matches)

        # Layer 2: Fuzzy Matching
        fuzzy_matches, unmatched_ledger, unmatched_bank = self._find_fuzzy_matches(unmatched_ledger, unmatched_bank)
        matches.extend(fuzzy_matches)

        # Layer 3: Semantic Matching
        semantic_matches = self.intelligent_matcher.find_matches(unmatched_ledger, unmatched_bank)
        matches.extend(semantic_matches)

        # Update remaining unmatched transactions after semantic matching
        matched_ledger_ids = {m['receipt']['transaction_id'] for m in semantic_matches}
        matched_bank_ids = {m['bank_transaction']['transaction_id'] for m in semantic_matches}
        unmatched_ledger = [tx for tx in unmatched_ledger if tx['transaction_id'] not in matched_ledger_ids]
        unmatched_bank = [tx for tx in unmatched_bank if tx['transaction_id'] not in matched_bank_ids]

        return {
            "matches": matches,
            "unmatched_ledger": unmatched_ledger,
            "unmatched_bank": unmatched_bank
        }

    def _find_exact_matches(self, ledger: List[Dict], bank: List[Dict]) -> (List[Dict], List[Dict], List[Dict]):
        """Finds exact matches based on amount and date."""
        matches = []
        unmatched_ledger = list(ledger)
        unmatched_bank = list(bank)

        for l_idx, l_tx in enumerate(unmatched_ledger):
            for b_idx, b_tx in enumerate(unmatched_bank):
                if (l_tx['amount'] == b_tx['amount'] and
                    self._is_date_within_tolerance(l_tx['transaction_date'], b_tx['transaction_date'])):
                    
                    matches.append({
                        'receipt': l_tx,
                        'bank_transaction': b_tx,
                        'confidence': 1.0,
                        'match_type': 'exact'
                    })
                    unmatched_ledger.pop(l_idx)
                    unmatched_bank.pop(b_idx)
                    break # Move to the next ledger transaction
        return matches, unmatched_ledger, unmatched_bank

    def _find_fuzzy_matches(self, ledger: List[Dict], bank: List[Dict]) -> (List[Dict], List[Dict], List[Dict]):
        """Finds fuzzy matches based on amount, date, and vendor name similarity."""
        matches = []
        unmatched_ledger = list(ledger)
        unmatched_bank = list(bank)

        for l_idx, l_tx in enumerate(unmatched_ledger):
            for b_idx, b_tx in enumerate(unmatched_bank):
                amount_diff = abs(l_tx['amount'] - b_tx['amount'])
                amount_tolerance = l_tx['amount'] * self.amount_tolerance_percent
                
                if (amount_diff <= amount_tolerance and
                    self._is_date_within_tolerance(l_tx['transaction_date'], b_tx['transaction_date']) and
                    fuzz.token_set_ratio(l_tx['vendor_name'], b_tx['description']) > self.vendor_similarity_threshold):
                    
                    confidence = 1 - (amount_diff / l_tx['amount'])
                    matches.append({
                        'receipt': l_tx,
                        'bank_transaction': b_tx,
                        'confidence': confidence,
                        'match_type': 'fuzzy'
                    })
                    unmatched_ledger.pop(l_idx)
                    unmatched_bank.pop(b_idx)
                    break
        return matches, unmatched_ledger, unmatched_bank

    def _is_date_within_tolerance(self, date1: datetime, date2: datetime) -> bool:
        """Checks if two dates are within the tolerance range."""
        return abs(date1 - date2) <= timedelta(days=self.date_tolerance_days)
