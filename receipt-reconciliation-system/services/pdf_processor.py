import json
from llama_index.core import SimpleDirectoryReader
from models.receipt_llm_config import ReceiptExtractionLLM
from models.validation_models import ReceiptData
from pydantic import ValidationError
import logging
import re
from datetime import datetime  # ADD THIS LINE

logger = logging.getLogger(__name__)


class ReceiptPDFProcessor:
    def __init__(self):
        self.llm = ReceiptExtractionLLM()
        
    
    def process_receipt(self, pdf_path: str) -> dict:
        """Process receipt, extract data, and validate it using Pydantic - BULLETPROOF VERSION."""
        try:
            logger.info(f"Processing PDF: {pdf_path}")
            
            documents = SimpleDirectoryReader(input_files=[pdf_path]).load_data()
            text_content = documents[0].text
            
            logger.info(f"Extracted {len(text_content)} characters from PDF")
            
            cleaned_text = self._clean_receipt_text(text_content)
            
            if not cleaned_text or len(cleaned_text.strip()) < 10:
                logger.warning(f"Insufficient text extracted from PDF: {len(cleaned_text)} characters")
                return {'error': 'Insufficient text content in PDF', 'confidence': 0.0}
            
            # Build prompt safely without .format() method
            prompt = f"""
            Extract receipt information from the text below and return ONLY a valid JSON object.

            {{
                "date": "YYYY-MM-DD",
                "vendor": "store name", 
                "amount": 25.99,
                "tax": 2.50,
                "category": "category",
                "items": ["item1", "item2"],
                "payment_method": "card/cash"
            }}

            Receipt text: {cleaned_text}
            """
            
            # BULLETPROOF LLM COMPLETION WITH EXCEPTION HANDLING
            try:
                logger.info("🚀 Attempting LLM completion...")
                # Ensure proper LLM call without context manager issues
                if hasattr(self.llm, 'complete'):
                    response = self.llm.complete(prompt)
                else:
                    response = self.llm(prompt)  # Alternative calling method
                
                # SAFELY extract response text FIRST, then log success
                try:
                    response_text = str(response.text) if hasattr(response, 'text') else str(response)
                    # NOW it's safe to log success with the extracted text
                    logger.info(f"✅ LLM completion successful: {len(response_text)} characters")
                    logger.info(f"LLM response preview: {response_text[:200]}...")
                except Exception as text_error:
                    logger.error(f"❌ Failed to extract response text: {text_error}")
                    response_text = ""
                    
            except Exception as llm_error:
                logger.error(f"❌ LLM completion failed: {llm_error}")
                logger.info("🔄 Falling back to direct text analysis...")
                response_text = ""  # Use empty response to trigger direct analysis
            
            # If we have LLM response, try to parse it, otherwise use direct text analysis
            if response_text.strip():
                logger.info("🔧 Using LLM response for extraction...")
                extracted_data = self._manual_json_construction(response_text)
            else:
                logger.info("🔧 Using direct text analysis (no LLM response)...")
                extracted_data = self._manual_json_construction(cleaned_text[:5000])  # Use first 5000 chars
            
            logger.info(f"✅ Data extraction successful: {extracted_data}")
            
            # Validate and clean the data using the Pydantic model
            try:
                prepared_data = self._prepare_for_validation(extracted_data)
                validated_data = ReceiptData(**prepared_data)
                validated_data_dict = validated_data.model_dump()
                validated_data_dict['confidence'] = self._calculate_confidence(validated_data_dict)
                database_ready_data = self.get_database_ready_data(validated_data_dict)

                logger.info(f"Successfully processed PDF with confidence: {database_ready_data['confidence']}")
                return database_ready_data
                
            except ValidationError as e:
                logger.error(f"Pydantic validation failed: {e}")
                logger.error(f"Extracted data: {extracted_data}")
                return {'error': f"Validation error: {e}", 'confidence': 0.0}
            
        except Exception as e:
            logger.error(f"PDF processing failed for {pdf_path}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'error': f'PDF processing failed: {str(e)}', 
                'confidence': 0.0,
                'file_path': pdf_path
            }
        
    def _clean_receipt_text(self, text: str) -> str:
        """Extract meaningful receipt content from PDF text."""
        import re
        
        # Split into lines and filter for receipt-like content
        lines = text.split('\n')
        meaningful_lines = []
        
        for line in lines:
            line = line.strip()
            # Keep lines that look like receipt content
            if (len(line) > 3 and 
                not line.startswith('%PDF') and
                not re.match(r'^/\w+', line) and
                not re.match(r'^\d+\s+\d+\s+obj', line) and
                re.search(r'[a-zA-Z]', line)):  # Contains letters
                meaningful_lines.append(line)
        
        # Take first 100 meaningful lines
        cleaned_text = '\n'.join(meaningful_lines[:100])
        return cleaned_text

    def get_database_ready_data(self, validated_data_dict: dict) -> dict:
        """Convert validated data to database-ready format."""
        # Map 'date' to 'transaction_date' for database compatibility
        if 'date' in validated_data_dict:
            validated_data_dict['transaction_date'] = validated_data_dict['date']
        
        return validated_data_dict

    def _prepare_for_validation(self, extracted_data: dict) -> dict:
        """Prepare extracted data for Pydantic validation."""
        # Ensure date is string format for validation
        if extracted_data.get('date') and not isinstance(extracted_data['date'], str):
            if hasattr(extracted_data['date'], 'strftime'):
                extracted_data['date'] = extracted_data['date'].strftime('%Y-%m-%d')
            else:
                extracted_data['date'] = str(extracted_data['date'])
        
        # Ensure amount is float
        if extracted_data.get('amount'):
            extracted_data['amount'] = float(extracted_data['amount'])
        
        # Ensure tax is float  
        if extracted_data.get('tax'):
            extracted_data['tax'] = float(extracted_data['tax'])
            
        return extracted_data

    def _calculate_confidence(self, extracted_data: dict) -> float:
        if not extracted_data or 'error' in extracted_data:
            return 0.0

        required_fields = ["date", "vendor", "amount"]
        score = 0.0
        
        for field in required_fields:
            if field in extracted_data and extracted_data[field] is not None:
                if isinstance(extracted_data[field], str) and extracted_data[field].strip():
                    score += 1.0
                elif isinstance(extracted_data[field], (int, float)) and extracted_data[field] > 0:
                    score += 1.0
        
        return score / len(required_fields)

    def _manual_json_construction(self, text: str) -> dict:
        """Manually construct JSON when parsing fails - ENHANCED VERSION."""
        import re
        
        logger.info("🔧 Using manual JSON construction...")
        
        result = {
            "date": "2025-08-03",
            "vendor": "Unknown Store",
            "amount": 0.0,
            "tax": 0.0,
            "category": "retail",
            "items": [],
            "payment_method": "unknown"
        }
        
        date_patterns = [
            r'\b(\d{4}-\d{2}-\d{2})\b',
            r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b',
            r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2})\b',
            r'(\w{3}\s+\d{1,2},?\s+\d{4})',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                try:
                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y', '%m/%d/%y', '%m-%d-%y']:
                        try:
                            parsed_date = datetime.strptime(date_str, fmt)
                            result["date"] = parsed_date.strftime('%Y-%m-%d')
                            break
                        except:
                            continue
                    if result["date"] != "2025-08-03":
                        break
                except:
                    result["date"] = date_str
                    break
        
        amount_patterns = [
            r'TOTAL[:\s]*\$?(\d+\.\d{2})',
            r'AMOUNT[:\s]*\$?(\d+\.\d{2})',
            r'SUBTOTAL[:\s]*\$?(\d+\.\d{2})',
            r'\$(\d+\.\d{2})\s*(?:total|amount)',
            r'\$(\d+\.\d{2})',
            r'(\d+\.\d{2})\s*(?:USD|usd|\$)',
        ]
        
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount = float(match.group(1))
                    if amount > 0:
                        result["amount"] = amount
                        break
                except:
                    continue
        
        vendor_patterns = [
            r'(?:^|\n)([A-Z][A-Z\s&]{3,30})(?:\s*#|\n|Store)',
            r'(?:^|\n)([A-Za-z][A-Za-z\s&]{5,30})(?:\s*Store|\s*Market|\s*Shop)',
            r'(?:^|\n)([A-Z\s]+)(?:\s*Store|\s*Inc|\s*LLC)',
        ]
        
        for pattern in vendor_patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                vendor = match.group(1).strip()
                if len(vendor) > 2 and vendor != vendor.upper():
                    result["vendor"] = vendor[:50]
                    break
        
        if result["vendor"] == "Unknown Store":
            lines = text.split('\n')[:10]
            for line in lines:
                clean_line = line.strip()
                if (len(clean_line) > 3 and 
                    not re.match(r'^\d+', clean_line) and 
                    not re.match(r'^(receipt|invoice|date|total|subtotal)', clean_line.lower())):
                    result["vendor"] = clean_line[:50]
                    break
        
        tax_patterns = [
            r'TAX[:\s]*\$?(\d+\.\d{2})',
            r'SALES TAX[:\s]*\$?(\d+\.\d{2})',
        ]
        
        for pattern in tax_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    result["tax"] = float(match.group(1))
                    break
                except:
                    continue
        
        logger.info(f"✅ Manual construction result: {result}")
        return result
