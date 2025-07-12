#!/usr/bin/env python3
"""
Script to add Notion connector using internal integration
"""
import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.connectors.manager import connector_manager
from app.core.logging import get_logger

logger = get_logger(__name__)

async def add_notion_connector():
    """Add Notion connector with internal integration"""
    try:
        # Connector configuration
        connector_name = "notion-internal"
        connector_type = "notion"
        
        # No credentials needed - will use config file
        credentials = {}
        
        # Basic settings
        settings = {
            "sync_interval_minutes": 60,  # Sync every hour
            "max_items_per_sync": 1000
        }
        
        # Add the connector
        await connector_manager.add_connector(
            name=connector_name,
            connector_type=connector_type,
            credentials=credentials,
            settings=settings,
            enabled=True
        )
        
        print(f"✅ Successfully added Notion connector: {connector_name}")
        
        # Test the connection
        status = connector_manager.get_connector_status(connector_name)
        if status:
            print(f"📊 Connector status: {status}")
        
        # Trigger initial sync
        print("🔄 Starting initial sync...")
        result = await connector_manager.sync_connector(connector_name, incremental=False)
        
        if result.success:
            print(f"✅ Initial sync completed successfully!")
            print(f"   - Items processed: {result.items_processed}")
            print(f"   - Items added: {result.items_added}")
            print(f"   - Duration: {result.duration_seconds:.2f} seconds")
        else:
            print(f"❌ Initial sync failed:")
            for error in result.errors:
                print(f"   - {error}")
        
    except Exception as e:
        print(f"❌ Error adding Notion connector: {e}")
        logger.error(f"Error adding Notion connector: {e}")

if __name__ == "__main__":
    asyncio.run(add_notion_connector())