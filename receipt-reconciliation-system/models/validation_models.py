from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import date, datetime
import re

class ReceiptData(BaseModel):
    """
    Pydantic model for validating the structure and data types of extracted receipt data.
    """
    date: Optional[date] = None
    vendor: Optional[str] = None
    amount: Optional[float] = Field(None, alias='amount')
    tax: Optional[float] = None
    category: Optional[str] = None
    items: List[str] = []
    payment_method: Optional[str] = None

    @field_validator('date', mode='before')
    @classmethod
    def parse_date(cls, value):
        if isinstance(value, str):
            # Attempt to parse common date formats
            for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%b %d, %Y'):
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    pass
            # Fallback for dates with text or different formats
            match = re.search(r'(\d{4}-\d{2}-\d{2})|(\d{2}/\d{2}/\d{4})', value)
            if match:
                date_str = match.group(0)
                try:
                    return datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    return datetime.strptime(date_str, '%m/%d/%Y').date()
        return value

    @field_validator('amount', 'tax', mode='before')
    @classmethod
    def parse_float(cls, value):
        if isinstance(value, str):
            # Remove currency symbols, commas, and other non-numeric characters
            value = re.sub(r'[^\d.]', '', value)
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        return value
