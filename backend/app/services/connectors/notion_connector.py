import asyncio
import aiohttp
from typing import Dict, List, Any, Optional, AsyncIterator
from datetime import datetime, timedelta
import json

from .base import BaseConnector, ConnectorConfig, SyncResult
from app.core.logging import get_logger

logger = get_logger(__name__)


class NotionConnector(BaseConnector):
    """Connector for Notion workspaces"""
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.api_base = "https://api.notion.com/v1"
        self.session: Optional[aiohttp.ClientSession] = None
        
    @property
    def connector_type(self) -> str:
        return "notion"
    
    async def authenticate(self) -> bool:
        """Authenticate with Notion API using internal integration"""
        try:
            # Try to get token from credentials first (for backward compatibility)
            token = self.config.credentials.get("token")
            
            # If no token in credentials, get from config file
            if not token:
                token = self._get_internal_integration_token()
            
            if not token:
                logger.error("Notion internal integration token not found")
                return False
            
            # Create session with auth headers
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28",
                "User-Agent": "RAG-System/1.0"
            }
            
            self.session = aiohttp.ClientSession(headers=headers)
            
            # Test authentication by getting bot info (internal integrations use /users/me for bot info)
            async with self.session.get(f"{self.api_base}/users/me") as response:
                if response.status == 200:
                    bot_data = await response.json()
                    logger.info(f"Authenticated with Notion internal integration: {bot_data.get('name', 'Unknown Bot')}")
                    return True
                else:
                    logger.error(f"Notion authentication failed: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Notion authentication error: {e}")
            return False
    
    def _get_internal_integration_token(self) -> Optional[str]:
        """Get internal integration token from config file"""
        try:
            import yaml
            import os
            
            config_path = os.path.join(os.path.dirname(__file__), "../../../config/oauth_config.yaml")
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                
                notion_config = config.get('providers', {}).get('notion', {})
                return notion_config.get('internal_integration_secret')
            
            return None
            
        except Exception as e:
            logger.error(f"Error reading Notion config: {e}")
            return None
    
    async def test_connection(self) -> bool:
        """Test connection to Notion API"""
        try:
            if not self.session:
                return await self.authenticate()
            
            async with self.session.get(f"{self.api_base}/users/me") as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Notion connection test failed: {e}")
            return False
    
    async def sync_data(self, incremental: bool = True) -> SyncResult:
        """Sync Notion pages and databases"""
        start_time = datetime.utcnow()
        items_processed = 0
        items_added = 0
        items_failed = 0
        errors = []
        
        try:
            # Get all accessible pages and databases
            async for item_data in self.get_all_content():
                items_processed += 1
                
                # Process through RAG pipeline
                if await self.process_item_through_rag(item_data, f"notion_{item_data.get('type', 'unknown')}"):
                    items_added += 1
                else:
                    items_failed += 1
                
                # Respect rate limits (Notion allows 3 requests per second)
                if items_processed % 3 == 0:
                    await asyncio.sleep(1)
            
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
            logger.error(f"Notion sync failed: {e}")
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
        """Get Notion content items"""
        count = 0
        async for item_data in self.get_all_content():
            if count >= limit:
                break
            yield item_data
            count += 1
    
    async def get_all_content(self) -> AsyncIterator[Dict[str, Any]]:
        """Get all accessible Notion content"""
        try:
            # First, search for all pages and databases
            search_payload = {
                "filter": {
                    "property": "object",
                    "value": "page"
                },
                "sort": {
                    "direction": "descending",
                    "timestamp": "last_edited_time"
                }
            }
            
            # Get pages
            async for page in self._paginated_search(search_payload):
                if self._should_index_page(page):
                    page_content = await self._get_page_content(page["id"])
                    if page_content:
                        yield {
                            "type": "page",
                            "id": page["id"],
                            "title": self._extract_title(page),
                            "content": page_content,
                            "url": page.get("url", ""),
                            "last_edited": page.get("last_edited_time", ""),
                            "created": page.get("created_time", ""),
                            "properties": page.get("properties", {}),
                            "raw_data": page
                        }
            
            # Get databases
            search_payload["filter"]["value"] = "database"
            async for database in self._paginated_search(search_payload):
                if self._should_index_database(database):
                    # Get database schema and some sample entries
                    db_content = await self._get_database_content(database["id"])
                    if db_content:
                        yield {
                            "type": "database",
                            "id": database["id"],
                            "title": self._extract_title(database),
                            "content": db_content,
                            "url": database.get("url", ""),
                            "last_edited": database.get("last_edited_time", ""),
                            "created": database.get("created_time", ""),
                            "properties": database.get("properties", {}),
                            "raw_data": database
                        }
                        
        except Exception as e:
            logger.error(f"Error getting Notion content: {e}")
    
    async def _paginated_search(self, payload: Dict) -> AsyncIterator[Dict]:
        """Handle paginated search results"""
        start_cursor = None
        
        while True:
            if start_cursor:
                payload["start_cursor"] = start_cursor
            
            async with self.session.post(f"{self.api_base}/search", json=payload) as response:
                if response.status != 200:
                    logger.error(f"Search failed: {response.status}")
                    break
                
                data = await response.json()
                
                for item in data.get("results", []):
                    yield item
                
                if not data.get("has_more", False):
                    break
                
                start_cursor = data.get("next_cursor")
    
    async def _get_page_content(self, page_id: str) -> Optional[str]:
        """Get full content of a Notion page"""
        try:
            # Get page blocks
            blocks_content = []
            start_cursor = None
            
            while True:
                url = f"{self.api_base}/blocks/{page_id}/children"
                params = {"page_size": 100}
                if start_cursor:
                    params["start_cursor"] = start_cursor
                
                async with self.session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"Failed to get page blocks: {response.status}")
                        break
                    
                    data = await response.json()
                    
                    for block in data.get("results", []):
                        block_text = self._extract_block_text(block)
                        if block_text:
                            blocks_content.append(block_text)
                    
                    if not data.get("has_more", False):
                        break
                    
                    start_cursor = data.get("next_cursor")
            
            return "\n\n".join(blocks_content) if blocks_content else None
            
        except Exception as e:
            logger.error(f"Error getting page content for {page_id}: {e}")
            return None
    
    async def _get_database_content(self, database_id: str) -> Optional[str]:
        """Get database schema and sample entries"""
        try:
            # Get database info
            async with self.session.get(f"{self.api_base}/databases/{database_id}") as response:
                if response.status != 200:
                    return None
                
                db_info = await response.json()
            
            # Get database entries (limited to avoid too much data)
            query_payload = {"page_size": 20}  # Limit to 20 entries
            
            async with self.session.post(f"{self.api_base}/databases/{database_id}/query", json=query_payload) as response:
                if response.status != 200:
                    return None
                
                entries_data = await response.json()
            
            # Format database content
            content_parts = []
            
            # Add database description
            title = self._extract_title(db_info)
            content_parts.append(f"Database: {title}")
            
            # Add properties schema
            properties = db_info.get("properties", {})
            if properties:
                content_parts.append("Properties:")
                for prop_name, prop_info in properties.items():
                    prop_type = prop_info.get("type", "unknown")
                    content_parts.append(f"  - {prop_name}: {prop_type}")
            
            # Add sample entries
            entries = entries_data.get("results", [])
            if entries:
                content_parts.append(f"\nSample entries ({len(entries)} shown):")
                for entry in entries[:10]:  # Show max 10 entries
                    entry_text = self._format_database_entry(entry, properties)
                    if entry_text:
                        content_parts.append(f"  • {entry_text}")
            
            return "\n".join(content_parts)
            
        except Exception as e:
            logger.error(f"Error getting database content for {database_id}: {e}")
            return None
    
    def _extract_block_text(self, block: Dict) -> Optional[str]:
        """Extract text content from a Notion block"""
        block_type = block.get("type")
        if not block_type:
            return None
        
        block_data = block.get(block_type, {})
        
        # Handle different block types
        if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item"]:
            rich_text = block_data.get("rich_text", [])
            return "".join([text.get("plain_text", "") for text in rich_text])
        
        elif block_type == "code":
            rich_text = block_data.get("rich_text", [])
            code_text = "".join([text.get("plain_text", "") for text in rich_text])
            language = block_data.get("language", "")
            return f"```{language}\n{code_text}\n```"
        
        elif block_type == "quote":
            rich_text = block_data.get("rich_text", [])
            return f"> {''.join([text.get('plain_text', '') for text in rich_text])}"
        
        elif block_type == "callout":
            rich_text = block_data.get("rich_text", [])
            return f"💡 {''.join([text.get('plain_text', '') for text in rich_text])}"
        
        elif block_type == "toggle":
            rich_text = block_data.get("rich_text", [])
            return f"▶ {''.join([text.get('plain_text', '') for text in rich_text])}"
        
        return None
    
    def _extract_title(self, item: Dict) -> str:
        """Extract title from a Notion page or database"""
        properties = item.get("properties", {})
        
        # Look for title property
        for prop_name, prop_data in properties.items():
            if prop_data.get("type") == "title":
                title_array = prop_data.get("title", [])
                return "".join([text.get("plain_text", "") for text in title_array])
        
        # Fallback to object title
        if "title" in item:
            title_array = item.get("title", [])
            return "".join([text.get("plain_text", "") for text in title_array])
        
        return "Untitled"
    
    def _format_database_entry(self, entry: Dict, properties_schema: Dict) -> Optional[str]:
        """Format a database entry for indexing"""
        entry_parts = []
        properties = entry.get("properties", {})
        
        for prop_name, prop_data in properties.items():
            prop_type = prop_data.get("type")
            value = self._extract_property_value(prop_data, prop_type)
            if value:
                entry_parts.append(f"{prop_name}: {value}")
        
        return " | ".join(entry_parts) if entry_parts else None
    
    def _extract_property_value(self, prop_data: Dict, prop_type: str) -> Optional[str]:
        """Extract value from a Notion property"""
        if prop_type == "title":
            title_array = prop_data.get("title", [])
            return "".join([text.get("plain_text", "") for text in title_array])
        
        elif prop_type == "rich_text":
            rich_text = prop_data.get("rich_text", [])
            return "".join([text.get("plain_text", "") for text in rich_text])
        
        elif prop_type == "number":
            return str(prop_data.get("number", ""))
        
        elif prop_type == "select":
            select_data = prop_data.get("select")
            return select_data.get("name", "") if select_data else ""
        
        elif prop_type == "multi_select":
            multi_select = prop_data.get("multi_select", [])
            return ", ".join([item.get("name", "") for item in multi_select])
        
        elif prop_type == "date":
            date_data = prop_data.get("date")
            if date_data:
                start = date_data.get("start", "")
                end = date_data.get("end", "")
                return f"{start} - {end}" if end else start
        
        elif prop_type == "checkbox":
            return str(prop_data.get("checkbox", False))
        
        elif prop_type == "url":
            return prop_data.get("url", "")
        
        elif prop_type == "email":
            return prop_data.get("email", "")
        
        elif prop_type == "phone_number":
            return prop_data.get("phone_number", "")
        
        return None
    
    def _should_index_page(self, page: Dict) -> bool:
        """Check if page should be indexed"""
        # Skip archived pages
        if page.get("archived", False):
            return False
        
        # Check if page has content
        title = self._extract_title(page)
        if not title or title.strip() == "":
            return False
        
        # Add any custom filtering logic here
        return True
    
    def _should_index_database(self, database: Dict) -> bool:
        """Check if database should be indexed"""
        # Skip archived databases
        if database.get("archived", False):
            return False
        
        # Check if database has a title
        title = self._extract_title(database)
        if not title or title.strip() == "":
            return False
        
        return True
    
    def _extract_content(self, item_data: Dict[str, Any]) -> str:
        """Extract text content from Notion item data"""
        content = item_data.get("content", "")
        title = item_data.get("title", "")
        item_type = item_data.get("type", "")
        
        # Add context header
        header = f"# Notion {item_type.title()}: {title}\n\n"
        return header + content
    
    def _extract_metadata(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from Notion item data"""
        return {
            "filename": f"{item_data.get('title', 'Untitled')}.md",
            "notion_id": item_data.get("id", ""),
            "notion_type": item_data.get("type", ""),
            "notion_url": item_data.get("url", ""),
            "last_edited": item_data.get("last_edited", ""),
            "created": item_data.get("created", ""),
            "properties": item_data.get("properties", {}),
            "indexed_at": datetime.utcnow().isoformat()
        }
    
    async def close(self):
        """Close the connector and cleanup resources"""
        if self.session:
            await self.session.close()
            self.session = None