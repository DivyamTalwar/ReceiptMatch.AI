import json
from llama_index.core import SimpleDirectoryReader
from models.receipt_llm_config import ReceiptExtractionLLM
from models.validation_models import ReceiptData
from pydantic import ValidationError
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class ReceiptPDFProcessor:
    def __init__(self):
        self.llm = ReceiptExtractionLLM()
        
    
    def process_receipt(self, pdf_path: str, bypass_cleaning: bool = False) -> dict:
        try:
            logger.info(f"Processing PDF: {pdf_path}")
            
            text_content = self._extract_text_with_fallbacks(pdf_path)
            
            logger.info(f"Extracted {len(text_content)} characters from PDF")
            
            if bypass_cleaning:
                logger.info("Bypassing text cleaning for manual upload")
                cleaned_text = text_content[:10000]
            else:
                logger.info("Using enhanced text cleaning for email processing")
                cleaned_text = self._clean_receipt_text(text_content)
            
            if not bypass_cleaning:
                if not cleaned_text or len(cleaned_text.strip()) < 10:
                    logger.warning(f"Insufficient text extracted from PDF: {len(cleaned_text)} characters (min: 10)")
                    return {'error': 'Insufficient text content in PDF', 'confidence': 0.0}

            logger.info(f"Processing with {len(cleaned_text)} characters of text")
            
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
            
            try:
                logger.info("Attempting LLM completion")
                if hasattr(self.llm, 'complete'):
                    response = self.llm.complete(prompt)
                else:
                    response = self.llm(prompt)
                
                try:
                    response_text = str(response.text) if hasattr(response, 'text') else str(response)
                    logger.info(f"LLM completion successful: {len(response_text)} characters")
                    logger.info(f"LLM response preview: {response_text[:200]}...")
                except Exception as text_error:
                    logger.error(f"Failed to extract response text: {text_error}")
                    response_text = ""
                    
            except Exception as llm_error:
                logger.error(f"LLM completion failed: {llm_error}")
                logger.info("Falling back to direct text analysis")
                response_text = ""
            
            if response_text.strip():
                logger.info("🔧 Using LLM response for extraction")
                extracted_data = self._manual_json_construction(response_text)
            else:
                logger.info("🔧 Using direct text analysis (no LLM response)")
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
                re.search(r'[a-zA-Z]', line)):
                meaningful_lines.append(line)
        
        cleaned_text = '\n'.join(meaningful_lines[:100])
        return cleaned_text

    def _extract_text_with_fallbacks(self, pdf_path: str) -> str:
        try:
            logger.info("🔧 Trying SimpleDirectoryReader")
            documents = SimpleDirectoryReader(input_files=[pdf_path]).load_data()
            if documents and len(documents) > 0:
                text = documents[0].text
                if text and len(text.strip()) > 100: 
                    logger.info(f"SimpleDirectoryReader success: {len(text)} characters")
                    return text
            logger.warning("SimpleDirectoryReader returned insufficient content")
        except Exception as e:
            logger.error(f"SimpleDirectoryReader failed: {e}")
        
        try:
            logger.info("🔧 Trying PyPDF2...")
            import PyPDF2
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                if len(text.strip()) > 100:
                    logger.info(f"✅ PyPDF2 success: {len(text)} characters")
                    return text
            logger.warning("❌ PyPDF2 returned insufficient content")
        except Exception as e:
            logger.error(f"❌ PyPDF2 failed: {e}")
        
        # Method 3: Try pdfplumber
        try:
            logger.info("🔧 Trying pdfplumber...")
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                if len(text.strip()) > 100:
                    logger.info(f"✅ pdfplumber success: {len(text)} characters")
                    return text
            logger.warning("❌ pdfplumber returned insufficient content")
        except Exception as e:
            logger.error(f"❌ pdfplumber failed: {e}")
        
        # Method 4: 🔥 OCR EXTRACTION (THE GAME CHANGER!)
        try:
            logger.info("🔧 Trying OCR extraction (Tesseract)...")
            import pytesseract
            from pdf2image import convert_from_path
            
            # Convert PDF to images
            images = convert_from_path(pdf_path)
            text = ""
            
            for i, image in enumerate(images):
                logger.info(f"🔧 Processing page {i+1} with OCR...")
                page_text = pytesseract.image_to_string(image)
                if page_text and len(page_text.strip()) > 10:
                    text += page_text + "\n"
            
            if len(text.strip()) > 100:
                logger.info(f"✅ OCR extraction success: {len(text)} characters")
                logger.info(f"OCR text preview: {text[:200]}")
                return text
            logger.warning("❌ OCR returned insufficient content")
        except Exception as e:
            logger.error(f"❌ OCR extraction failed: {e}")
            logger.info("💡 Install OCR dependencies: pip install pytesseract pdf2image")
        
        # Method 5: Enhanced binary extraction (your current working method)
        try:
            logger.info("🔧 Trying enhanced binary extraction...")
            with open(pdf_path, 'rb') as file:
                binary_content = file.read()
                # Enhanced patterns for readable text
                import re
                text_matches = re.findall(rb'[A-Za-z0-9\s\$\.\,\-\:\#]{8,}', binary_content)
                if text_matches:
                    text = ' '.join([match.decode('utf-8', errors='ignore') for match in text_matches])
                    # Clean up PDF metadata
                    text = re.sub(r'%PDF.*?endobj', '', text, flags=re.DOTALL)
                    text = re.sub(r'<<.*?>>', '', text)
                    text = re.sub(r'/\w+\s+\d+', '', text)
                    
                    if len(text.strip()) > 50:
                        logger.info(f"✅ Enhanced binary extraction success: {len(text)} characters")
                        return text
            logger.warning("❌ Enhanced binary extraction found insufficient content")
        except Exception as e:
            logger.error(f"❌ Enhanced binary extraction failed: {e}")
        
        # Final fallback
        logger.error("❌ All extraction methods failed - using minimal fallback")
        return "Receipt processing failed - manual review required"

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
        """ULTIMATE confidence calculation considering all fields."""
        if not extracted_data or 'error' in extracted_data:
            return 0.0

        # 🎯 WEIGHTED SCORING SYSTEM
        scores = {
            "date": 0.0,      # 25% weight
            "vendor": 0.0,    # 35% weight  
            "amount": 0.0,    # 35% weight
            "tax": 0.0,       # 3% weight
            "items": 0.0,     # 2% weight
        }
        
        weights = {
            "date": 0.25,
            "vendor": 0.35,
            "amount": 0.35,
            "tax": 0.03,
            "items": 0.02,
        }
        
        # Score date
        if extracted_data.get('date'):
            date_val = extracted_data['date']
            if isinstance(date_val, str) and len(date_val) >= 8:  # Reasonable date length
                if date_val != "2025-08-03":  # Not default
                    scores["date"] = 1.0
                else:
                    scores["date"] = 0.3  # Partial credit for default
        
        # Score vendor
        if extracted_data.get('vendor'):
            vendor = extracted_data['vendor']
            if isinstance(vendor, str):
                if vendor != "Unknown Store":
                    if len(vendor) > 3 and not vendor.startswith('PDF'):
                        scores["vendor"] = 1.0
                    else:
                        scores["vendor"] = 0.4  # Partial credit
                else:
                    scores["vendor"] = 0.1  # Minimal credit for default
        
        # Score amount
        if extracted_data.get('amount'):
            amount = extracted_data['amount']
            if isinstance(amount, (int, float)) and amount > 0:
                scores["amount"] = 1.0
            else:
                scores["amount"] = 0.1  # Minimal credit for zero
        
        # Score tax
        if extracted_data.get('tax') and isinstance(extracted_data['tax'], (int, float)):
            if extracted_data['tax'] > 0:
                scores["tax"] = 1.0
        
        # Score items
        if extracted_data.get('items') and isinstance(extracted_data['items'], list):
            if len(extracted_data['items']) > 0:
                scores["items"] = 1.0
        
        # Calculate weighted score
        total_score = sum(scores[field] * weights[field] for field in scores)
        
        logger.info(f"🎯 Confidence breakdown: {scores}")
        logger.info(f"🎯 Weighted total: {total_score:.3f}")
        
        return total_score

    def _manual_json_construction(self, text: str) -> dict:
        """ULTIMATE manual JSON construction with enhanced patterns."""
        import re
        from datetime import datetime
        
        logger.info("🔧 Using ULTIMATE manual JSON construction...")
        
        # 📊 DEBUG: Show what we're working with
        logger.info(f"🔍 Text length: {len(text)} characters")
        logger.info(f"🔍 Text preview: {text[:300]}")
        
        result = {
            "date": datetime.now().strftime('%Y-%m-%d'),  # Better default
            "vendor": "Unknown Store",
            "amount": 0.0,
            "tax": 0.0,
            "category": "retail",
            "items": [],
            "payment_method": "unknown"
        }
        
        # 🎯 ENHANCED DATE PATTERNS
        date_patterns = [
            r'\b(\d{4}-\d{2}-\d{2})\b',                    # 2025-01-15
            r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b',         # 1/15/2025
            r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2})\b',         # 1/15/25
            r'(\w{3,9}\s+\d{1,2},?\s+\d{4})',             # January 15, 2025
            r'Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', # Date: 1/15/25
            r'(\d{1,2}/\d{1,2}/\d{2,4})',                 # Flexible format
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
                            logger.info(f"✅ Date extracted: {result['date']}")
                            break
                        except:
                            continue
                    if result["date"] != datetime.now().strftime('%Y-%m-%d'):
                        break
                except:
                    result["date"] = date_str
                    break
        
        # 🎯 ENHANCED AMOUNT PATTERNS (More Aggressive)
        amount_patterns = [
            r'TOTAL[:\s]*\$?(\d+\.\d{2})',
            r'AMOUNT[:\s]*\$?(\d+\.\d{2})',
            r'SUBTOTAL[:\s]*\$?(\d+\.\d{2})',
            r'GRAND TOTAL[:\s]*\$?(\d+\.\d{2})',
            r'\$(\d+\.\d{2})\s*(?:total|amount|due)',
            r'\$(\d{1,4}\.\d{2})',                         # Any reasonable dollar amount
            r'(\d{1,4}\.\d{2})\s*(?:USD|usd|\$)',
            r'Total:\s*(\d+\.\d{2})',
            r'(\d+\.\d{2})\s*$',                           # Last decimal on line
        ]
        
        all_amounts = []
        for pattern in amount_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                try:
                    amount = float(match)
                    if 0.01 <= amount <= 10000:  # Reasonable range
                        all_amounts.append(amount)
                except:
                    continue
        
        if all_amounts:
            # Use the largest reasonable amount (likely the total)
            result["amount"] = max(all_amounts)
            logger.info(f"✅ Amount extracted: ${result['amount']}")
        
        # 🎯 ULTRA-SMART VENDOR PATTERNS
        vendor_patterns = [
            r'(?:^|\n)\s*([A-Z][A-Z\s&]{8,40})\s*(?:#|\n|Store)',  # Store names with numbers
            r'(?:^|\n)\s*(AMAZON\.COM|WALMART|SHELL|CVS|TARGET|MCDONALD)',  # Specific store names
            r'(?:^|\n)\s*([A-Z][A-Z\s&]{5,40})\s*(?:SUPERCENTER|STATION|PHARMACY)',  # With descriptors
        ]
        
        exclude_vendors = ['TAX', 'TOTAL', 'SUBTOTAL', 'PAYMENT', 'FUEL', 'USB', 'WIRELESS']
        
        vendor_candidates = []
        for pattern in vendor_patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            for match in matches:
                vendor = match.strip()
                if (len(vendor) > 2 and 
                    vendor not in ['PDF', 'Filter', 'FlateDecode', 'Length'] and
                    vendor.upper() not in exclude_vendors and
                    not vendor.startswith('%') and
                    not re.match(r'^\d+$', vendor)):
                    vendor_candidates.append(vendor)
        
        # Choose best vendor candidate
        if vendor_candidates:
            # Prefer shorter, more reasonable names
            best_vendor = min(vendor_candidates, key=len)
            if len(best_vendor) <= 50:
                result["vendor"] = best_vendor
                logger.info(f"✅ Vendor extracted: {result['vendor']}")
        
        # 🎯 FALLBACK VENDOR EXTRACTION
        if result["vendor"] == "Unknown Store":
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            for line in lines[:15]:  # Check first 15 lines
                # Skip obvious junk
                if (len(line) > 2 and len(line) < 50 and
                    not line.startswith(('%', '/', '<', '>')) and
                    not re.match(r'^\d+', line) and
                    not line.lower().startswith(('receipt', 'invoice', 'date', 'total', 'subtotal', 'obj')) and
                    re.search(r'[A-Za-z]', line)):
                    
                    result["vendor"] = line[:50]
                    logger.info(f"✅ Fallback vendor extracted: {result['vendor']}")
                    break
        
        # 🎯 ENHANCED TAX PATTERNS
        tax_patterns = [
            r'TAX[:\s]*\$?(\d+\.\d{2})',
            r'SALES TAX[:\s]*\$?(\d+\.\d{2})',
            r'Tax[:\s]+(\d+\.\d{2})',
            r'(\d+\.\d{2})\s*tax',
        ]
        
        for pattern in tax_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    tax_amount = float(match.group(1))
                    if 0 < tax_amount < result["amount"] * 0.2:  # Reasonable tax (< 20%)
                        result["tax"] = tax_amount
                        logger.info(f"✅ Tax extracted: ${result['tax']}")
                        break
                except:
                    continue
        
        # 🎯 EXTRACT ITEMS
        item_patterns = [
            r'(?:^|\n)\s*([A-Za-z][A-Za-z\s]{3,30})\s+\$?\d+\.\d{2}',  # Item name followed by price
            r'\d+\s+([A-Za-z][A-Za-z\s]{3,30})\s+\$?\d+\.\d{2}',      # Qty Item Price
        ]
        
        items = []
        for pattern in item_patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            for match in matches:
                item = match.strip()
                if len(item) > 3 and item not in result["vendor"]:
                    items.append(item)
        
        if items:
            result["items"] = items[:5]  # Limit to 5 items
            logger.info(f"✅ Items extracted: {result['items']}")
        
        result["category"] = self._categorize_transaction(result["vendor"], result["items"])
        logger.info(f"🎯 ULTIMATE extraction result: {result}")
        return result

    def _categorize_transaction(self, vendor, items):
        vendor_lower = vendor.lower()
        items_text = ' '.join(items).lower()
        
        if any(word in vendor_lower for word in ['pharmacy', 'cvs', 'walgreens']):
            return 'healthcare'
        elif any(word in vendor_lower for word in ['shell', 'gas', 'fuel', 'station']):
            return 'fuel'
        elif any(word in vendor_lower for word in ['walmart', 'grocery', 'market']):
            return 'grocery'
        elif any(word in vendor_lower for word in ['amazon', 'online']):
            return 'online'
        elif any(word in vendor_lower for word in ['pizza', 'restaurant', 'mcdonald']):
            return 'dining'
        else:
            return 'retail'
