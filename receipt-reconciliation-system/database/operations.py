from models.schema import ReceiptTransaction, BankTransaction, ReconciliationMatch, ProcessedEmail
from mongoengine.errors import NotUniqueError

def add_receipt_transaction(transaction_data):
    """
    Adds a new receipt transaction to the database.
    """
    try:
        transaction = ReceiptTransaction(**transaction_data)
        transaction.save()
        return transaction
    except NotUniqueError:
        print(f"Transaction with id {transaction_data.get('transaction_id')} already exists.")
        return None
    except Exception as e:
        print(f"An error occurred while adding receipt transaction: {e}")
        return None

def get_receipt_transaction(transaction_id):
    """
    Retrieves a receipt transaction by its ID.
    """
    try:
        return ReceiptTransaction.objects(transaction_id=transaction_id).first()
    except Exception as e:
        print(f"An error occurred while retrieving receipt transaction: {e}")
        return None

def get_all_receipt_transactions():
    """
    Retrieves all receipt transactions.
    """
    try:
        return ReceiptTransaction.objects()
    except Exception as e:
        print(f"An error occurred while retrieving all receipt transactions: {e}")
        return None

def add_bank_transaction(transaction_data):
    """
    Adds a new bank transaction to the database.
    """
    try:
        transaction = BankTransaction(**transaction_data)
        transaction.save()
        return transaction
    except NotUniqueError:
        print(f"Transaction with id {transaction_data.get('transaction_id')} already exists.")
        return None
    except Exception as e:
        print(f"An error occurred while adding bank transaction: {e}")
        return None

def get_bank_transaction(transaction_id):
    """
    Retrieves a bank transaction by its ID.
    """
    try:
        return BankTransaction.objects(transaction_id=transaction_id).first()
    except Exception as e:
        print(f"An error occurred while retrieving bank transaction: {e}")
        return None

def get_all_bank_transactions():
    """
    Retrieves all bank transactions.
    """
    try:
        return BankTransaction.objects()
    except Exception as e:
        print(f"An error occurred while retrieving all bank transactions: {e}")
        return None

def add_reconciliation_match(match_data):
    """
    Adds a new reconciliation match to the database.
    """
    try:
        match = ReconciliationMatch(**match_data)
        match.save()
        return match
    except NotUniqueError:
        print(f"Match with id {match_data.get('match_id')} already exists.")
        return None
    except Exception as e:
        print(f"An error occurred while adding reconciliation match: {e}")
        return None

def get_reconciliation_match(match_id):
    """
    Retrieves a reconciliation match by its ID.
    """
    try:
        return ReconciliationMatch.objects(match_id=match_id).first()
    except Exception as e:
        print(f"An error occurred while retrieving reconciliation match: {e}")
        return None

def get_all_reconciliation_matches():
    """
    Retrieves all reconciliation matches.
    """
    try:
        return ReconciliationMatch.objects()
    except Exception as e:
        print(f"An error occurred while retrieving all reconciliation matches: {e}")
        return None

def add_processed_email(message_id: str):
    """
    Adds a processed email message ID to the database.
    """
    try:
        processed_email = ProcessedEmail(message_id=message_id)
        processed_email.save()
        return True
    except NotUniqueError:
        # This is expected if the email has already been processed
        return False
    except Exception as e:
        print(f"An error occurred while adding processed email: {e}")
        return False

def is_email_processed(message_id: str) -> bool:
    """
    Checks if an email has already been processed.
    """
    try:
        return ProcessedEmail.objects(message_id=message_id).count() > 0
    except Exception as e:
        print(f"An error occurred while checking if email was processed: {e}")
        return False
