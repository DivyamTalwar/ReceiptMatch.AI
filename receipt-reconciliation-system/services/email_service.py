import os
import email
import asyncio
from email.header import decode_header
from typing import Dict, List, Any, Optional
import aioimaplib
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailServiceManager:
    """
    Manages email integration for multiple providers to fetch and process receipt attachments.
    Supports free email providers using standard IMAP protocols asynchronously.
    """

    def __init__(self):
        """
        Initializes the EmailServiceManager with configurations for supported providers.
        """
        self.supported_providers: Dict[str, Dict[str, Any]] = {
            'gmail': {'imap_server': 'imap.gmail.com', 'imap_port': 993},
            'outlook': {'imap_server': 'outlook.office365.com', 'imap_port': 993},
            'yahoo': {'imap_server': 'imap.mail.yahoo.com', 'imap_port': 993}
        }
        self.connection: Optional[aioimaplib.IMAP4_SSL] = None
        self.is_connected = False

    async def _check_connection(self) -> bool:
        """Check if connection is still alive and valid."""
        if not self.connection or not self.is_connected:
            return False
        
        try:
            # Try a simple NOOP command to check connection
            await self.connection.noop()
            return True
        except Exception as e:
            logger.warning(f"Connection check failed: {e}")
            self.is_connected = False
            self.connection = None
            return False

    @retry(
        stop=stop_after_attempt(3), 
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, OSError, aioimaplib.AioImapException))
    )
    async def connect(self, provider: str, email_address: str, password: str) -> bool:
        """
        Asynchronously connects to the specified email provider using IMAP with retry logic.
        """
        if provider not in self.supported_providers:
            logger.error(f"Provider '{provider}' is not supported.")
            return False

        # Clean up existing connection
        if self.connection:
            try:
                await self.disconnect()
            except:
                pass

        config = self.supported_providers[provider]
        try:
            logger.info(f"Attempting to connect to {provider}...")
            self.connection = aioimaplib.IMAP4_SSL(host=config['imap_server'], port=config['imap_port'])
            await self.connection.wait_hello_from_server()
            
            login_result = await self.connection.login(email_address, password)
            if login_result.result != 'OK':
                raise ConnectionError(f"Login failed: {login_result.result}")
            
            # Test connection with a simple command
            await self.connection.noop()
            await asyncio.sleep(1)  # Add a small delay to ensure the connection is fully established
            
            self.is_connected = True
            logger.info(f"Successfully connected to {provider}.")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to {provider}: {e}")
            self.is_connected = False
            self.connection = None
            raise  # Reraise exception to trigger tenacity's retry mechanism

    async def disconnect(self):
        """
        Asynchronously disconnects from the IMAP server.
        """
        if self.connection:
            try:
                await self.connection.logout()
                logger.info("Disconnected from email server.")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            finally:
                self.connection = None
                self.is_connected = False

    async def list_folders(self) -> List[str]:
        """
        Lists all folders in the mailbox.
        """
        if not await self._check_connection():
            raise ConnectionError("Not connected to email server or connection lost")

        try:
            response = await self.connection.list()
            folders = []
            for item in response.lines:
                if isinstance(item, bytes):
                    item = item.decode()
                parts = item.split('"')
                if len(parts) >= 4:
                    folders.append(parts[3])
            return folders
        except Exception as e:
            logger.error(f"Error listing folders: {e}")
            return []

    @retry(
        stop=stop_after_attempt(3), 
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ConnectionError, OSError, aioimaplib.AioImapException))
    )
    async def fetch_emails_with_pdf(self, folder: str = 'INBOX', search_criteria: str = 'UNSEEN') -> List[Dict[str, Any]]:
        """
        Asynchronously fetches emails from a specified folder that contain PDF attachments, with retry logic.
        """
        # Check connection before proceeding
        if not await self._check_connection():
            raise ConnectionError("Not connected to email server or connection lost")

        try:
            logger.info(f"Selecting folder: {folder}")
            select_result = await self.connection.select(folder)
            if select_result.result != 'OK':
                raise ConnectionError(f"Failed to select folder {folder}: {select_result.result}")

            logger.info(f"Searching for emails with criteria: {search_criteria}")
            search_result = await self.connection.search(search_criteria)
            if search_result.result != 'OK':
                logger.warning(f"Search returned: {search_result.result}")
                return []

            # Handle empty search results
            if not search_result.lines or not search_result.lines[0]:
                logger.info("No emails found matching criteria.")
                return []

            # Parse email IDs
            email_ids_str = search_result.lines[0]
            if isinstance(email_ids_str, bytes):
                email_ids_str = email_ids_str.decode()
            
            email_ids = email_ids_str.split() if email_ids_str.strip() else []
            logger.info(f"Found {len(email_ids)} emails to process")

            fetched_emails = []

            for email_id in email_ids:
                try:
                    logger.info(f"Fetching email ID: {email_id}")
                    fetch_result = await self.connection.fetch(email_id, '(RFC822)')
                    
                    if fetch_result.result == 'OK' and fetch_result.lines:
                        # Parse the email message
                        raw_email = fetch_result.lines[1] if len(fetch_result.lines) > 1 else fetch_result.lines[0]
                        if isinstance(raw_email, str):
                            raw_email = raw_email.encode()
                        
                        msg = email.message_from_bytes(raw_email)
                        
                        # Decode subject
                        subject = "No Subject"
                        if msg.get("Subject"):
                            subject_header = decode_header(msg["Subject"])[0]
                            if isinstance(subject_header[0], bytes):
                                subject = subject_header[0].decode(subject_header[1] if subject_header[1] else "utf-8")
                            else:
                                subject = subject_header[0]

                        email_details = {
                            "id": email_id if isinstance(email_id, str) else email_id.decode(),
                            "subject": subject,
                            "from": msg.get("From", "Unknown"),
                            "date": msg.get("Date", "Unknown"),
                            "attachments": []
                        }

                        # Process multipart messages for PDF attachments
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_disposition = str(part.get("Content-Disposition", ""))
                                content_type = part.get_content_type()
                                
                                if "attachment" in content_disposition and content_type == "application/pdf":
                                    filename = part.get_filename()
                                    if filename:
                                        payload = part.get_payload(decode=True)
                                        if payload:
                                            email_details["attachments"].append({
                                                "filename": filename,
                                                "data": payload
                                            })
                                            logger.info(f"Found PDF attachment: {filename}")
                        
                        # Only include emails with PDF attachments
                        if email_details["attachments"]:
                            fetched_emails.append(email_details)
                            logger.info(f"Added email with {len(email_details['attachments'])} PDF attachments")
                    
                except Exception as e:
                    logger.error(f"Error processing email ID {email_id}: {e}")
                    continue

            logger.info(f"Successfully fetched {len(fetched_emails)} emails with PDF attachments")
            return fetched_emails

        except Exception as e:
            logger.error(f"Error in fetch_emails_with_pdf: {e}")
            # Reset connection state on error
            self.is_connected = False
            raise  # Reraise to trigger tenacity

    async def download_attachments(self, emails: List[Dict[str, Any]], download_path: str):
        """
        Asynchronously downloads PDF attachments from fetched emails to a specified directory.
        """
        if not os.path.exists(download_path):
            os.makedirs(download_path)

        for email_details in emails:
            for attachment in email_details["attachments"]:
                filename = attachment["filename"]
                filepath = os.path.join(download_path, filename)
                try:
                    with open(filepath, "wb") as f:
                        f.write(attachment["data"])
                    logger.info(f"Successfully downloaded '{filename}' to '{download_path}'.")
                except Exception as e:
                    logger.error(f"Error downloading attachment '{filename}': {e}")
