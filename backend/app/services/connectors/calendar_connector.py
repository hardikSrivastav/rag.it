import asyncio
import aiohttp
from typing import Dict, List, Any, Optional, AsyncIterator
from datetime import datetime, timedelta
import json
from pathlib import Path
import os

from .base import BaseConnector, ConnectorConfig, SyncResult
from app.core.logging import get_logger

logger = get_logger(__name__)


class CalendarConnector(BaseConnector):
    """Connector for Google Calendar events"""
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.api_base = "https://www.googleapis.com/calendar/v3"
        self.session: Optional[aiohttp.ClientSession] = None
        self.access_token: Optional[str] = None
        self._sync_task: Optional[asyncio.Task] = None
        self._stop_sync = False
        
    @property
    def connector_type(self) -> str:
        return "calendar"
    
    async def authenticate(self) -> bool:
        """Authenticate with Google Calendar API using OAuth2"""
        try:
            # Try to get token from credentials first
            access_token = self.config.credentials.get("access_token")
            
            # If no token in credentials, get from OAuth service
            if not access_token:
                access_token = self._get_oauth_token()
            
            if not access_token:
                logger.error("Google Calendar OAuth token not found")
                return False
            
            # Test current token first
            if await self._test_token(access_token):
                logger.info("Google Calendar token is valid")
                return True
            
            # Token is invalid/expired - try to refresh
            logger.info("Google Calendar token expired/invalid, attempting refresh...")
            if await self._refresh_access_token():
                logger.info("Google Calendar token refreshed successfully")
                return True
            
            # Refresh failed
            logger.error("Google Calendar token refresh failed - manual re-authentication required")
            return False
                    
        except Exception as e:
            logger.error(f"Google Calendar authentication error: {e}")
            return False
    
    async def _test_token(self, token: str) -> bool:
        """Test if the current access token is valid"""
        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(f"{self.api_base}/users/me/calendarList") as response:
                    if response.status == 200:
                        logger.info("Google Calendar token is valid")
                        
                        # Update session with valid token
                        if self.session:
                            await self.session.close()
                        self.session = aiohttp.ClientSession(headers=headers)
                        self.access_token = token
                        return True
                    else:
                        logger.warning(f"Calendar token test failed: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"Calendar token test error: {e}")
            return False
    
    async def _refresh_access_token(self) -> bool:
        """Refresh expired access token using refresh token"""
        try:
            refresh_token = self.config.credentials.get("refresh_token")
            if not refresh_token:
                logger.error("No refresh token available for Google Calendar")
                return False
            
            client_id = self.config.credentials.get("client_id")
            client_secret = self.config.credentials.get("client_secret")
            
            if not client_id or not client_secret:
                logger.error("Client ID and secret required for token refresh")
                return False
            
            # Prepare refresh request
            refresh_data = {
                "client_id": client_id,
                "client_secret": client_secret,
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
                        
                        logger.info("Google Calendar access token refreshed successfully")
                        return True
                    else:
                        error_data = await response.text()
                        logger.error(f"Token refresh failed: {response.status} - {error_data}")
                        return False
                        
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """Test connection to Google Calendar API"""
        try:
            if not self.session:
                return await self.authenticate()
            
            # Test by getting calendar list
            async with self.session.get(f"{self.api_base}/users/me/calendarList") as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Google Calendar connection test failed: {e}")
            return False
    
    async def sync_data(self, incremental: bool = True) -> SyncResult:
        """Sync calendar events from Google Calendar"""
        start_time = datetime.utcnow()
        items_processed = 0
        items_added = 0
        items_failed = 0
        errors = []
        
        try:
            # Get calendar IDs to sync
            calendar_ids = self.config.settings.get("calendar_ids", ["primary"])
            
            # Calculate time range for sync
            sync_days_back = self.config.settings.get("sync_days_back", 30)
            sync_days_forward = self.config.settings.get("sync_days_forward", 90)
            
            time_min = datetime.utcnow() - timedelta(days=sync_days_back)
            time_max = datetime.utcnow() + timedelta(days=sync_days_forward)
            
            # If incremental, only sync recent events
            if incremental and self.config.last_sync:
                time_min = max(time_min, self.config.last_sync - timedelta(hours=1))
            
            for calendar_id in calendar_ids:
                try:
                    logger.info(f"Syncing calendar: {calendar_id}")
                    
                    # Get calendar events
                    async for event_data in self.get_calendar_events(
                        calendar_id, time_min, time_max
                    ):
                        items_processed += 1
                        
                        # Skip cancelled events unless configured otherwise
                        if event_data.get("status") == "cancelled" and not self.config.settings.get("include_cancelled", False):
                            continue
                        
                        # Process through RAG pipeline
                        if await self.process_item_through_rag(event_data, f"calendar_{calendar_id}"):
                            items_added += 1
                        else:
                            items_failed += 1
                        
                        # Respect rate limits
                        if items_processed % 20 == 0:
                            await asyncio.sleep(0.1)
                            
                except Exception as e:
                    error_msg = f"Failed to sync calendar {calendar_id}: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            return SyncResult(
                success=len(errors) == 0,
                items_processed=items_processed,
                items_added=items_added,
                items_updated=0,  # Calendar events are typically replaced
                items_failed=items_failed,
                errors=errors,
                duration_seconds=duration
            )
            
        except Exception as e:
            logger.error(f"Google Calendar sync failed: {e}")
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
        """Get calendar events"""
        calendar_ids = self.config.settings.get("calendar_ids", ["primary"])
        count = 0
        
        # Default time range
        time_min = datetime.utcnow() - timedelta(days=30)
        time_max = datetime.utcnow() + timedelta(days=90)
        
        for calendar_id in calendar_ids:
            if count >= limit:
                break
                
            async for event_data in self.get_calendar_events(calendar_id, time_min, time_max):
                if count >= limit:
                    break
                yield event_data
                count += 1
    
    async def get_calendar_events(self, calendar_id: str, time_min: datetime, time_max: datetime) -> AsyncIterator[Dict[str, Any]]:
        """Get events from a specific calendar"""
        try:
            page_token = None
            max_results = 250  # Google's max per request
            
            while True:
                # Build request parameters
                params = {
                    "timeMin": time_min.isoformat() + "Z",
                    "timeMax": time_max.isoformat() + "Z",
                    "singleEvents": "true",
                    "orderBy": "startTime",
                    "maxResults": max_results
                }
                
                if page_token:
                    params["pageToken"] = page_token
                
                # Make API request
                url = f"{self.api_base}/calendars/{calendar_id}/events"
                async with self.session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"Failed to get events from calendar {calendar_id}: {response.status}")
                        break
                    
                    data = await response.json()
                    events = data.get("items", [])
                    
                    for event in events:
                        # Add calendar context
                        event["calendar_id"] = calendar_id
                        yield event
                    
                    # Check for next page
                    page_token = data.get("nextPageToken")
                    if not page_token:
                        break
                        
        except Exception as e:
            logger.error(f"Error getting events from calendar {calendar_id}: {e}")
    
    def _extract_content(self, item_data: Dict[str, Any]) -> str:
        """Extract text content from calendar event data"""
        # Build comprehensive content from event data
        content_parts = []
        
        # Event title
        summary = item_data.get("summary", "")
        if summary:
            content_parts.append(f"# {summary}")
        
        # Event description
        description = item_data.get("description", "")
        if description:
            content_parts.append(f"## Description\n{description}")
        
        # Event timing
        start = item_data.get("start", {})
        end = item_data.get("end", {})
        
        start_time = self._parse_datetime(start)
        end_time = self._parse_datetime(end)
        
        if start_time and end_time:
            content_parts.append(f"## Timing\nStart: {start_time}\nEnd: {end_time}")
        
        # Location
        location = item_data.get("location", "")
        if location:
            content_parts.append(f"## Location\n{location}")
        
        # Attendees
        attendees = item_data.get("attendees", [])
        if attendees:
            attendee_list = []
            for attendee in attendees:
                email = attendee.get("email", "")
                name = attendee.get("displayName", email)
                status = attendee.get("responseStatus", "")
                attendee_list.append(f"- {name} ({status})")
            
            if attendee_list:
                content_parts.append(f"## Attendees\n" + "\n".join(attendee_list))
        
        # Meeting details
        if item_data.get("conferenceData"):
            content_parts.append("## Meeting Details\nOnline meeting scheduled")
        
        # Event status
        status = item_data.get("status", "")
        if status:
            content_parts.append(f"## Status\n{status}")
        
        return "\n\n".join(content_parts)
    
    def _extract_metadata(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from calendar event data"""
        start = item_data.get("start", {})
        end = item_data.get("end", {})
        
        metadata = {
            "event_id": item_data.get("id", ""),
            "calendar_id": item_data.get("calendar_id", ""),
            "summary": item_data.get("summary", ""),
            "status": item_data.get("status", ""),
            "location": item_data.get("location", ""),
            "creator": item_data.get("creator", {}).get("email", ""),
            "organizer": item_data.get("organizer", {}).get("email", ""),
            "start_time": self._parse_datetime(start),
            "end_time": self._parse_datetime(end),
            "all_day": start.get("date") is not None,  # All-day events use 'date' instead of 'dateTime'
            "attendee_count": len(item_data.get("attendees", [])),
            "has_attachments": len(item_data.get("attachments", [])) > 0,
            "has_conference": item_data.get("conferenceData") is not None,
            "event_type": item_data.get("eventType", "default"),
            "visibility": item_data.get("visibility", "default"),
            "indexed_at": datetime.utcnow().isoformat(),
            "event_url": item_data.get("htmlLink", "")
        }
        
        # Add attendee emails
        attendees = item_data.get("attendees", [])
        if attendees:
            metadata["attendee_emails"] = [att.get("email", "") for att in attendees if att.get("email")]
        
        return metadata
    
    def _parse_datetime(self, dt_data: Dict[str, Any]) -> Optional[str]:
        """Parse datetime from Google Calendar event data"""
        if not dt_data:
            return None
        
        # All-day events use 'date'
        if "date" in dt_data:
            return dt_data["date"]
        
        # Regular events use 'dateTime'
        if "dateTime" in dt_data:
            return dt_data["dateTime"]
        
        return None
    
    def _get_oauth_token(self) -> Optional[str]:
        """Get OAuth token from OAuth service"""
        try:
            # Import here to avoid circular imports
            from app.services.oauth_service import calendar_oauth_service
            return calendar_oauth_service.get_stored_token()
        except Exception as e:
            logger.error(f"Error getting Google Calendar OAuth token: {e}")
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
    
    async def start_background_sync(self):
        """Start background sync task"""
        if self._sync_task and not self._sync_task.done():
            logger.info("Background sync already running for Google Calendar")
            return
        
        self._stop_sync = False
        self._sync_task = asyncio.create_task(self._background_sync_loop())
        logger.info("Started background sync for Google Calendar")
    
    async def stop_background_sync(self):
        """Stop background sync task"""
        self._stop_sync = True
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped background sync for Google Calendar")
    
    async def _background_sync_loop(self):
        """Background sync loop that runs periodically"""
        sync_interval = self.config.settings.get("sync_interval_minutes", 30)
        max_retries = 3
        retry_delay = 60  # 1 minute
        
        logger.info(f"Starting Google Calendar background sync with {sync_interval} minute intervals")
        
        while not self._stop_sync:
            try:
                # Ensure we're authenticated
                if not await self.authenticate():
                    logger.error("Google Calendar authentication failed, retrying in 5 minutes")
                    await asyncio.sleep(300)  # Wait 5 minutes before retry
                    continue
                
                # Perform incremental sync
                logger.info("Starting Google Calendar background sync...")
                sync_result = await self.sync_data(incremental=True)
                
                if sync_result.success:
                    logger.info(f"Google Calendar sync completed: {sync_result.items_added} items added, "
                              f"{sync_result.items_processed} processed in {sync_result.duration_seconds:.1f}s")
                    
                    # Update last sync time
                    await self._update_last_sync_time()
                else:
                    logger.error(f"Google Calendar sync failed with {len(sync_result.errors)} errors: {sync_result.errors}")
                
                # Wait for next sync interval
                await asyncio.sleep(sync_interval * 60)
                
            except asyncio.CancelledError:
                logger.info("Google Calendar background sync cancelled")
                break
            except Exception as e:
                logger.error(f"Google Calendar background sync error: {e}")
                
                # Retry logic with exponential backoff
                for retry in range(max_retries):
                    if self._stop_sync:
                        break
                    
                    wait_time = retry_delay * (2 ** retry)  # Exponential backoff
                    logger.info(f"Retrying Google Calendar sync in {wait_time} seconds (attempt {retry + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    
                    try:
                        if await self.authenticate():
                            sync_result = await self.sync_data(incremental=True)
                            if sync_result.success:
                                logger.info("Google Calendar sync retry successful")
                                await self._update_last_sync_time()
                                break
                    except Exception as retry_error:
                        logger.error(f"Google Calendar sync retry {retry + 1} failed: {retry_error}")
                else:
                    # All retries failed, wait longer before next attempt
                    logger.error("All Google Calendar sync retries failed, waiting 10 minutes before next attempt")
                    await asyncio.sleep(600)
    
    async def _update_last_sync_time(self):
        """Update the last sync time in the database"""
        try:
            from app.core.database import get_db, ConnectorConfig
            
            db = next(get_db())
            try:
                connector = db.query(ConnectorConfig).filter(ConnectorConfig.name == self.config.name).first()
                if connector:
                    connector.last_sync = datetime.utcnow()
                    db.commit()
                    
                    # Update local config
                    self.config.last_sync = connector.last_sync
                    logger.debug(f"Updated last sync time for Google Calendar: {connector.last_sync}")
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error updating last sync time: {e}")
    
    async def close(self):
        """Close the connector and cleanup resources"""
        await self.stop_background_sync()
        if self.session:
            await self.session.close()
            self.session = None