import asyncio
import aiohttp
import base64
import email
from typing import Dict, List, Any, Optional, AsyncIterator
from datetime import datetime, timedelta
import json

from .base import BaseConnector, ConnectorConfig, SyncResult
from app.core.logging import get_logger

logger = get_logger(__name__)


class GmailConnector(BaseConnector):
    """Connector for Gmail emails"""
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.api_base = "https://gmail.googleapis.com/gmail/v1"
        self.session: Optional[aiohttp.ClientSession] = None
        
    @property
    def connector_type(self) -> str:
        return "gmail"
    
    async def authenticate(self) -> bool:
        """Authenticate with Gmail API using OAuth token with automatic refresh"""
        try:
            # Try to get token from credentials first
            token = self.config.credentials.get("access_token")
            
            # If no token in credentials, get from OAuth service
            if not token:
                token = self._get_oauth_token()
            
            if not token:
                logger.error("Gmail OAuth token not found")
                return False
            
            # Test current token first
            if await self._test_token(token):
                logger.info("Gmail token is valid")
                return True
            
            # Token is invalid/expired - try to refresh
            logger.info("Gmail token expired/invalid, attempting refresh...")
            if await self._refresh_access_token():
                logger.info("Gmail token refreshed successfully")
                return True
            
            # Refresh failed
            logger.error("Gmail token refresh failed - manual re-authentication required")
            return False
                    
        except Exception as e:
            logger.error(f"Gmail authentication error: {e}")
            return False
    
    async def _test_token(self, token: str) -> bool:
        """Test if the current token is valid"""
        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "RAG-System/1.0"
            }
            
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(f"{self.api_base}/users/me/profile") as response:
                    if response.status == 200:
                        profile_data = await response.json()
                        logger.info(f"Token valid for Gmail: {profile_data.get('emailAddress', 'Unknown')}")
                        
                        # Update session with valid token
                        if self.session:
                            await self.session.close()
                        self.session = aiohttp.ClientSession(headers=headers)
                        return True
                    else:
                        logger.warning(f"Token test failed: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Token test error: {e}")
            return False
    
    async def _refresh_access_token(self) -> bool:
        """Refresh expired access token using refresh token"""
        try:
            refresh_token = self.config.credentials.get("refresh_token")
            if not refresh_token:
                logger.error("No refresh token available for Gmail")
                return False
            
            # Get OAuth config
            oauth_config = self._get_oauth_config()
            if not oauth_config:
                logger.error("OAuth config not available")
                return False
            
            # Prepare refresh request
            refresh_data = {
                "client_id": oauth_config["client_id"],
                "client_secret": oauth_config["client_secret"],
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            }
            
            # Call Google's token refresh endpoint
            async with aiohttp.ClientSession() as session:
                async with session.post("https://oauth2.googleapis.com/token", data=refresh_data) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        new_access_token = token_data["access_token"]
                        
                        # Update connector credentials in database
                        await self._update_connector_credentials({"access_token": new_access_token})
                        
                        # Update local config
                        self.config.credentials["access_token"] = new_access_token
                        
                        logger.info("Gmail access token refreshed successfully")
                        return True
                    else:
                        error_data = await response.text()
                        logger.error(f"Token refresh failed: {response.status} - {error_data}")
                        return False
                        
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return False
    
    def _get_oauth_config(self) -> Optional[Dict[str, str]]:
        """Get OAuth configuration for Gmail"""
        try:
            import yaml
            import os
            
            config_path = os.path.join(os.path.dirname(__file__), "../../../config/oauth_config.yaml")
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                
                gmail_config = config.get('providers', {}).get('gmail', {})
                return {
                    "client_id": gmail_config.get('client_id'),
                    "client_secret": gmail_config.get('client_secret')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error reading OAuth config: {e}")
            return None
    
    async def _update_connector_credentials(self, new_credentials: Dict[str, str]) -> bool:
        """Update connector credentials in database"""
        try:
            from app.core.database import get_db, ConnectorConfig
            
            db = next(get_db())
            try:
                connector = db.query(ConnectorConfig).filter(ConnectorConfig.name == self.config.name).first()
                if connector:
                    # Merge new credentials with existing ones
                    updated_credentials = connector.credentials.copy() if connector.credentials else {}
                    updated_credentials.update(new_credentials)
                    
                    connector.credentials = updated_credentials
                    db.commit()
                    
                    logger.info(f"Updated credentials for connector: {self.config.name}")
                    return True
                else:
                    logger.error(f"Connector {self.config.name} not found in database")
                    return False
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error updating connector credentials: {e}")
            return False
    
    def _get_oauth_token(self) -> Optional[str]:
        """Get OAuth token from OAuth service"""
        try:
            # Import here to avoid circular imports
            from app.services.oauth_service import gmail_oauth_service
            return gmail_oauth_service.get_stored_token()
        except Exception as e:
            logger.error(f"Error getting Gmail OAuth token: {e}")
            return None
    
    async def test_connection(self) -> bool:
        """Test connection to Gmail API"""
        try:
            if not self.session:
                return await self.authenticate()
            
            async with self.session.get(f"{self.api_base}/users/me/profile") as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Gmail connection test failed: {e}")
            return False
    
    async def sync_data(self, incremental: bool = True) -> SyncResult:
        """Sync Gmail emails"""
        start_time = datetime.utcnow()
        items_processed = 0
        items_added = 0
        items_failed = 0
        errors = []
        
        try:
            # Get sync settings
            settings = self.config.settings or {}
            max_emails = settings.get("max_emails_per_sync", 100)
            days_back = settings.get("days_back", 30)
            include_sent = settings.get("include_sent", True)
            include_drafts = settings.get("include_drafts", False)
            
            # Build query for emails
            query_parts = []
            
            # Date filter
            if incremental and self.config.last_sync:
                # Get emails since last sync
                last_sync_date = self.config.last_sync.strftime("%Y/%m/%d")
                query_parts.append(f"after:{last_sync_date}")
            else:
                # Get emails from last N days
                cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y/%m/%d")
                query_parts.append(f"after:{cutoff_date}")
            
            # Include different email types
            email_queries = []
            
            # Inbox emails
            inbox_query = " ".join(query_parts + ["in:inbox"])
            email_queries.append(("inbox", inbox_query))
            
            # Sent emails
            if include_sent:
                sent_query = " ".join(query_parts + ["in:sent"])
                email_queries.append(("sent", sent_query))
            
            # Draft emails
            if include_drafts:
                draft_query = " ".join(query_parts + ["in:drafts"])
                email_queries.append(("drafts", draft_query))
            
            # Process each email type
            for email_type, query in email_queries:
                logger.info(f"Processing {email_type} emails with query: {query}")
                
                async for email_data in self.get_emails(query, max_emails // len(email_queries)):
                    items_processed += 1
                    
                    # Add email type to metadata
                    email_data["email_type"] = email_type
                    
                    # Process through RAG pipeline
                    if await self.process_item_through_rag(email_data, f"gmail_{email_type}"):
                        items_added += 1
                    else:
                        items_failed += 1
                    
                    # Respect rate limits (Gmail allows 250 quota units per user per second)
                    if items_processed % 10 == 0:
                        await asyncio.sleep(0.1)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            return SyncResult(
                success=len(errors) == 0,
                items_processed=items_processed,
                items_added=items_added,
                items_updated=0,
                items_failed=items_failed,
                errors=errors,
                duration_seconds=duration
            )
            
        except Exception as e:
            logger.error(f"Gmail sync failed: {e}")
            return SyncResult(
                success=False,
                items_processed=items_processed,
                items_added=items_added,
                items_updated=0,
                items_failed=items_failed,
                errors=errors + [str(e)],
                duration_seconds=(datetime.utcnow() - start_time).total_seconds()
            )
    
    async def get_items(self, limit: int = 100, cursor: Optional[str] = None) -> AsyncIterator[Dict[str, Any]]:
        """Get Gmail email items"""
        count = 0
        query = "in:inbox OR in:sent"  # Default query
        
        async for email_data in self.get_emails(query, limit):
            if count >= limit:
                break
            yield email_data
            count += 1
    
    async def get_emails(self, query: str, max_results: int = 100) -> AsyncIterator[Dict[str, Any]]:
        """Get emails matching the query"""
        try:
            # Search for messages
            page_token = None
            processed = 0
            
            while processed < max_results:
                # Build search parameters
                params = {
                    "q": query,
                    "maxResults": min(500, max_results - processed)  # Gmail max is 500
                }
                
                if page_token:
                    params["pageToken"] = page_token
                
                # Search for message IDs
                async with self.session.get(f"{self.api_base}/users/me/messages", params=params) as response:
                    if response.status != 200:
                        logger.error(f"Failed to search emails: {response.status}")
                        break
                    
                    search_data = await response.json()
                    messages = search_data.get("messages", [])
                    
                    if not messages:
                        break
                    
                    # Get full message details for each message
                    for message_info in messages:
                        if processed >= max_results:
                            break
                        
                        message_id = message_info["id"]
                        email_data = await self._get_email_details(message_id)
                        
                        if email_data:
                            yield email_data
                            processed += 1
                    
                    # Check for next page
                    page_token = search_data.get("nextPageToken")
                    if not page_token:
                        break
                        
        except Exception as e:
            logger.error(f"Error getting emails: {e}")
    
    async def _get_email_details(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get full details for a specific email"""
        try:
            params = {"format": "full"}
            
            async with self.session.get(f"{self.api_base}/users/me/messages/{message_id}", params=params) as response:
                if response.status != 200:
                    logger.error(f"Failed to get email details for {message_id}: {response.status}")
                    return None
                
                message_data = await response.json()
                
                # Extract email information
                payload = message_data.get("payload", {})
                headers = payload.get("headers", [])
                
                # Extract headers
                header_dict = {h["name"].lower(): h["value"] for h in headers}
                
                subject = header_dict.get("subject", "No Subject")
                from_email = header_dict.get("from", "Unknown Sender")
                to_email = header_dict.get("to", "Unknown Recipient")
                date_str = header_dict.get("date", "")
                
                # Parse date
                email_date = self._parse_email_date(date_str)
                
                # Extract body content
                body_content = self._extract_email_body(payload)
                
                # Extract attachments info
                attachments = self._extract_attachment_info(payload)
                
                return {
                    "id": message_id,
                    "thread_id": message_data.get("threadId", ""),
                    "subject": subject,
                    "from": from_email,
                    "to": to_email,
                    "date": email_date,
                    "body": body_content,
                    "snippet": message_data.get("snippet", ""),
                    "labels": message_data.get("labelIds", []),
                    "attachments": attachments,
                    "size_estimate": message_data.get("sizeEstimate", 0),
                    "raw_headers": header_dict,
                    "internal_date": message_data.get("internalDate", "")
                }
                
        except Exception as e:
            logger.error(f"Error getting email details for {message_id}: {e}")
            return None
    
    def _extract_email_body(self, payload: Dict) -> str:
        """Extract text content from email payload"""
        body_parts = []
        
        def extract_parts(part):
            mime_type = part.get("mimeType", "")
            
            if mime_type == "text/plain":
                body_data = part.get("body", {}).get("data", "")
                if body_data:
                    # Decode base64url
                    decoded = base64.urlsafe_b64decode(body_data + "===").decode("utf-8", errors="ignore")
                    body_parts.append(decoded)
            
            elif mime_type == "text/html":
                body_data = part.get("body", {}).get("data", "")
                if body_data:
                    # Decode base64url and strip HTML (basic)
                    decoded = base64.urlsafe_b64decode(body_data + "===").decode("utf-8", errors="ignore")
                    # Simple HTML stripping (could be improved with BeautifulSoup)
                    import re
                    text = re.sub(r'<[^>]+>', '', decoded)
                    text = re.sub(r'\s+', ' ', text).strip()
                    body_parts.append(text)
            
            elif mime_type.startswith("multipart/"):
                # Recursively process multipart
                for subpart in part.get("parts", []):
                    extract_parts(subpart)
        
        extract_parts(payload)
        
        return "\n\n".join(body_parts) if body_parts else ""
    
    def _extract_attachment_info(self, payload: Dict) -> List[Dict]:
        """Extract attachment information"""
        attachments = []
        
        def extract_attachments(part):
            filename = part.get("filename", "")
            if filename:
                attachments.append({
                    "filename": filename,
                    "mime_type": part.get("mimeType", ""),
                    "size": part.get("body", {}).get("size", 0),
                    "attachment_id": part.get("body", {}).get("attachmentId", "")
                })
            
            # Check subparts
            for subpart in part.get("parts", []):
                extract_attachments(subpart)
        
        extract_attachments(payload)
        return attachments
    
    def _parse_email_date(self, date_str: str) -> str:
        """Parse email date string to ISO format"""
        try:
            if not date_str:
                return datetime.utcnow().isoformat()
            
            # Parse email date (RFC 2822 format)
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            return dt.isoformat()
            
        except Exception as e:
            logger.warning(f"Failed to parse email date '{date_str}': {e}")
            return datetime.utcnow().isoformat()
    
    def _extract_content(self, item_data: Dict[str, Any]) -> str:
        """Extract text content from email data"""
        subject = item_data.get("subject", "No Subject")
        from_email = item_data.get("from", "Unknown Sender")
        to_email = item_data.get("to", "Unknown Recipient")
        date = item_data.get("date", "")
        body = item_data.get("body", "")
        email_type = item_data.get("email_type", "email")
        
        # Format email content
        content_parts = [
            f"# Email ({email_type.title()}): {subject}",
            f"**From:** {from_email}",
            f"**To:** {to_email}",
            f"**Date:** {date}",
            "",
            "## Content:",
            body
        ]
        
        # Add attachment info if present
        attachments = item_data.get("attachments", [])
        if attachments:
            content_parts.extend([
                "",
                "## Attachments:",
                "\n".join([f"- {att['filename']} ({att['mime_type']})" for att in attachments])
            ])
        
        return "\n".join(content_parts)
    
    def _extract_metadata(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from email data"""
        return {
            "filename": f"{item_data.get('subject', 'No Subject')}.eml",
            "gmail_id": item_data.get("id", ""),
            "gmail_thread_id": item_data.get("thread_id", ""),
            "email_type": item_data.get("email_type", "email"),
            "from_email": item_data.get("from", ""),
            "to_email": item_data.get("to", ""),
            "email_date": item_data.get("date", ""),
            "subject": item_data.get("subject", ""),
            "labels": item_data.get("labels", []),
            "has_attachments": len(item_data.get("attachments", [])) > 0,
            "attachment_count": len(item_data.get("attachments", [])),
            "size_estimate": item_data.get("size_estimate", 0),
            "indexed_at": datetime.utcnow().isoformat()
        }
    
    async def close(self):
        """Close the connector and cleanup resources"""
        if self.session:
            await self.session.close()
            self.session = None