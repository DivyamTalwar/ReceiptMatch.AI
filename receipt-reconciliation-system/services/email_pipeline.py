import asyncio
from typing import List, Dict, Any
from .email_service import EmailServiceManager
from .pdf_processor import ReceiptPDFProcessor
from database.operations import add_receipt_transaction, add_processed_email, is_email_processed
from utils.helpers import GeneralHelpers
from config.settings import AppSettings
import os
from datetime import datetime 
from asyncio_throttle import Throttler
import logging

logger = logging.getLogger(__name__)

class EmailProcessingPipeline:
    def __init__(self, provider: str, email_address: str, password: str):
        self.email_service = EmailServiceManager()
        self.pdf_processor = ReceiptPDFProcessor()
        self.provider = provider
        self.email_address = email_address
        self.password = password
        self.download_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'receipts')
        
        os.makedirs(self.download_path, exist_ok=True)

    async def run(self) -> List[Dict[str, Any]]:
        processed_receipts = []
        
        try:
            logger.info("Connecting to email server...")
            connected = await self.email_service.connect(self.provider, self.email_address, self.password)
            if not connected:
                logger.error("Failed to connect to email server. Aborting pipeline.")
                return processed_receipts

            logger.info("Fetching emails with PDF attachments...")
            emails = await self.email_service.fetch_emails_with_pdf()
            logger.info(f"Found {len(emails)} emails with PDF attachments.")

            if not emails:
                logger.info("No emails with PDF attachments found.")
                return processed_receipts

            throttler = Throttler(AppSettings.MAX_EMAILS_PER_BATCH, 60.0)

            for email in emails:
                try:
                    email_id = email.get("id")
                    if not is_email_processed(email_id):
                        async with throttler:
                            result = await self.process_single_email(email)
                            if result:
                                processed_receipts.append(result)
                            add_processed_email(email_id)
                    else:
                        logger.info(f"Skipping already processed email with ID: {email_id}")
                except Exception as e:
                    logger.error(f"Error processing email {email.get('id', 'unknown')}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error in email processing pipeline: {e}")
        finally:
            try:
                await self.email_service.disconnect()
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
        
        logger.info(f"Pipeline completed. Processed {len(processed_receipts)} receipts.")
        return processed_receipts

    async def process_single_email(self, email: Dict[str, Any]) -> Dict[str, Any]:
        receipt_data = {}
        
        for attachment in email.get("attachments", []):
            try:
                filename = GeneralHelpers.safe_filename(attachment["filename"])
                filepath = os.path.join(self.download_path, filename)
                
                with open(filepath, "wb") as f:
                    f.write(attachment["data"])
                logger.info(f"Downloaded attachment: {filename}")
                
                extracted_data = self.pdf_processor.process_receipt(filepath)
                
                if "error" not in extracted_data:
                    transaction_id = GeneralHelpers.generate_unique_id("receipt")
                    receipt_data = {
                        "transaction_id": transaction_id,
                        "transaction_date": extracted_data.get("date"),
                        "vendor_name": extracted_data.get("vendor"),
                        "amount": extracted_data.get("amount"),
                        "tax_amount": extracted_data.get("tax"),
                        "category": extracted_data.get("category"),
                        "description": " ".join(extracted_data.get("items", [])),
                        "receipt_filename": filename,
                        "receipt_path": filepath,
                        "extraction_confidence": extracted_data.get("confidence"),
                        "processing_status": "processed",
                        "extracted_data": extracted_data
                    }
                    
                    if receipt_data.get("transaction_date"):
                        if isinstance(receipt_data["transaction_date"], str):
                            try:
                                receipt_data["transaction_date"] = datetime.strptime(receipt_data["transaction_date"], "%Y-%m-%d")
                            except:
                                receipt_data["transaction_date"] = datetime.now()
                    else:
                        receipt_data["transaction_date"] = datetime.now()
                    
                    add_receipt_transaction(receipt_data)
                    logger.info(f"Successfully processed and stored receipt: {filename}")
                else:
                    logger.error(f"Failed to process receipt: {filename}. Error: {extracted_data['error']}")

            except Exception as e:
                logger.error(f"Error processing attachment {attachment.get('filename', 'unknown')}: {e}")
                continue
        
        return receipt_data
