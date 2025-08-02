from mongoengine import Document, StringField, DecimalField, DateTimeField, ListField, EmbeddedDocument, ReferenceField, DictField
from datetime import datetime

class ReceiptTransaction(Document):
    transaction_id = StringField(unique=True, required=True)
    transaction_date = DateTimeField(required=True)
    vendor_name = StringField(required=True, max_length=200)
    vendor_address = StringField(max_length=500)
    amount = DecimalField(required=True, min_value=0, precision=2)
    tax_amount = DecimalField(min_value=0, precision=2, default=0)
    category = StringField(required=True, max_length=100)
    subcategory = StringField(max_length=100)
    description = StringField(max_length=1000)
    receipt_filename = StringField(required=True)
    receipt_path = StringField(required=True)
    extraction_confidence = DecimalField(min_value=0, max_value=1, precision=2)
    extracted_data = DictField()  # Raw extracted data for debugging
    processing_status = StringField(choices=['pending', 'processed', 'error'], default='pending')
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    
    meta = {
        'collection': 'ledger_transactions',
        'indexes': [
            'transaction_date',
            'vendor_name',
            'amount',
            'category',
            ('vendor_name', 'transaction_date'),
            ('amount', 'transaction_date')
        ]
    }

class BankTransaction(Document):
    transaction_id = StringField(unique=True, required=True)
    transaction_date = DateTimeField(required=True)
    description = StringField(required=True, max_length=500)
    amount = DecimalField(required=True, precision=2)
    transaction_type = StringField(choices=['debit', 'credit'], required=True)
    account_number = StringField(required=True, max_length=20)
    reference_number = StringField(max_length=100)
    balance_after = DecimalField(precision=2)
    upload_batch_id = StringField(required=True)
    uploaded_at = DateTimeField(default=datetime.utcnow)
    
    meta = {
        'collection': 'bank_transactions',
        'indexes': [
            'transaction_date',
            'amount',
            'account_number',
            'upload_batch_id',
            ('amount', 'transaction_date'),
            ('description', 'transaction_date')
        ]
    }

class ReconciliationMatch(Document):
    match_id = StringField(unique=True, required=True)
    ledger_transaction = ReferenceField(ReceiptTransaction)
    bank_transaction = ReferenceField(BankTransaction)
    match_confidence = DecimalField(required=True, min_value=0, max_value=1, precision=2)
    match_type = StringField(choices=['automatic', 'manual', 'suggested'], required=True)
    match_criteria = DictField()  # Store matching logic details
    status = StringField(choices=['confirmed', 'pending', 'rejected'], default='pending')
    created_at = DateTimeField(default=datetime.utcnow)
    confirmed_by = StringField()  # User confirmation
    confirmed_at = DateTimeField()
    
    meta = {
        'collection': 'reconciliation_matches',
        'indexes': [
            'match_confidence',
            'match_type',
            'status',
            'created_at'
        ]
    }

class ProcessedEmail(Document):
    """
    Stores the message IDs of processed emails to prevent duplicates.
    """
    message_id = StringField(unique=True, required=True)
    processed_at = DateTimeField(default=datetime.utcnow)

    meta = {
        'collection': 'processed_emails',
        'indexes': [
            'message_id'
        ]
    }
