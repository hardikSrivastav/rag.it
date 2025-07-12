import asyncio
from typing import Dict, List, Optional, Type
from datetime import datetime
from sqlalchemy.orm import Session

from .base import BaseConnector, ConnectorConfig as BaseConnectorConfig, SyncResult
from .github_connector import GitHubConnector
from .notion_connector import NotionConnector
from .gmail_connector import GmailConnector
from app.core.database import get_db, ConnectorConfig, ConnectorSyncLog
from app.core.logging import get_logger

logger = get_logger(__name__)


class ConnectorManager:
    """Manages all data connectors"""
    
    def __init__(self):
        self.connectors: Dict[str, BaseConnector] = {}
        self.connector_classes: Dict[str, Type[BaseConnector]] = {
            "github": GitHubConnector,
            "notion": NotionConnector,
            "gmail": GmailConnector,
            # Add other connectors as they're implemented
        }
    
    async def initialize(self):
        """Initialize all configured connectors"""
        db = next(get_db())
        try:
            # Load all connector configurations
            configs = db.query(ConnectorConfig).filter(ConnectorConfig.enabled == True).all()
            
            for config in configs:
                try:
                    await self.create_connector(config)
                except Exception as e:
                    logger.error(f"Failed to initialize connector {config.name}: {e}")
            
            logger.info(f"Initialized {len(self.connectors)} connectors")
            
        finally:
            db.close()
    
    async def create_connector(self, config: ConnectorConfig) -> BaseConnector:
        """Create a connector instance from database config"""
        connector_class = self.connector_classes.get(config.connector_type)
        if not connector_class:
            raise ValueError(f"Unknown connector type: {config.connector_type}")
        
        # Convert database config to connector config
        base_config = BaseConnectorConfig(
            name=config.name,
            enabled=config.enabled,
            sync_interval_minutes=config.sync_interval_minutes,
            max_items_per_sync=config.max_items_per_sync,
            last_sync=config.last_sync,
            credentials=config.credentials or {},
            settings=config.settings or {}
        )
        
        # Create connector instance
        connector = connector_class(base_config)
        
        # Test connection
        if await connector.test_connection():
            self.connectors[config.name] = connector
            logger.info(f"Created connector: {config.name} ({config.connector_type})")
        else:
            logger.error(f"Failed to connect to {config.name}")
            raise Exception(f"Connection test failed for {config.name}")
        
        return connector
    
    async def add_connector(self, name: str, connector_type: str, credentials: Dict, 
                           settings: Dict, enabled: bool = True) -> str:
        """Add a new connector configuration"""
        db = next(get_db())
        try:
            # Check if connector already exists
            existing = db.query(ConnectorConfig).filter(ConnectorConfig.name == name).first()
            if existing:
                raise ValueError(f"Connector with name '{name}' already exists")
            
            # Create database config
            config = ConnectorConfig(
                name=name,
                connector_type=connector_type,
                enabled=enabled,
                credentials=credentials,
                settings=settings
            )
            
            db.add(config)
            db.commit()
            db.refresh(config)
            
            # Create connector instance if enabled
            if enabled:
                await self.create_connector(config)
            
            logger.info(f"Added connector: {name} ({connector_type})")
            return name
            
        finally:
            db.close()
    
    async def remove_connector(self, name: str) -> bool:
        """Remove a connector"""
        db = next(get_db())
        try:
            # Stop connector if running
            if name in self.connectors:
                connector = self.connectors[name]
                connector.stop_background_sync()
                if hasattr(connector, 'close'):
                    await connector.close()
                del self.connectors[name]
            
            # Remove from database
            config = db.query(ConnectorConfig).filter(ConnectorConfig.name == name).first()
            if config:
                db.delete(config)
                db.commit()
                logger.info(f"Removed connector: {name}")
                return True
            
            return False
            
        finally:
            db.close()
    
    async def sync_connector(self, name: str, incremental: bool = True) -> SyncResult:
        """Manually trigger sync for a connector"""
        if name not in self.connectors:
            raise ValueError(f"Connector '{name}' not found")
        
        connector = self.connectors[name]
        
        # Log sync start
        db = next(get_db())
        try:
            sync_log = ConnectorSyncLog(
                connector_name=name,
                sync_type="incremental" if incremental else "full",
                status="running",
                started_at=datetime.utcnow()
            )
            db.add(sync_log)
            db.commit()
            db.refresh(sync_log)
            
            # Perform sync
            result = await connector.start_sync(incremental)
            
            # Update sync log
            sync_log.status = "success" if result.success else "error"
            sync_log.items_processed = result.items_processed
            sync_log.items_added = result.items_added
            sync_log.items_updated = result.items_updated
            sync_log.items_failed = result.items_failed
            sync_log.duration_seconds = result.duration_seconds
            sync_log.completed_at = datetime.utcnow()
            
            if not result.success:
                sync_log.error_message = "; ".join(result.errors)
            
            # Update connector config
            config = db.query(ConnectorConfig).filter(ConnectorConfig.name == name).first()
            if config:
                config.last_sync = datetime.utcnow()
                config.last_sync_status = sync_log.status
            
            db.commit()
            
            return result
            
        finally:
            db.close()
    
    async def sync_all_connectors(self, incremental: bool = True) -> Dict[str, SyncResult]:
        """Sync all enabled connectors"""
        results = {}
        
        for name, connector in self.connectors.items():
            if connector.config.enabled:
                try:
                    result = await self.sync_connector(name, incremental)
                    results[name] = result
                except Exception as e:
                    logger.error(f"Failed to sync connector {name}: {e}")
                    results[name] = SyncResult(
                        success=False,
                        items_processed=0,
                        items_added=0,
                        items_updated=0,
                        items_failed=0,
                        errors=[str(e)],
                        duration_seconds=0
                    )
        
        return results
    
    async def start_background_syncs(self):
        """Start background sync for all enabled connectors"""
        for name, connector in self.connectors.items():
            if connector.config.enabled:
                try:
                    await connector.start_background_sync()
                    logger.info(f"Started background sync for {name}")
                except Exception as e:
                    logger.error(f"Failed to start background sync for {name}: {e}")
    
    def stop_background_syncs(self):
        """Stop background sync for all connectors"""
        for name, connector in self.connectors.items():
            try:
                connector.stop_background_sync()
                logger.info(f"Stopped background sync for {name}")
            except Exception as e:
                logger.error(f"Failed to stop background sync for {name}: {e}")
    
    def get_connector_status(self, name: str) -> Optional[Dict]:
        """Get status of a specific connector"""
        if name not in self.connectors:
            return None
        
        return self.connectors[name].get_status()
    
    def get_all_connector_status(self) -> Dict[str, Dict]:
        """Get status of all connectors"""
        return {name: connector.get_status() for name, connector in self.connectors.items()}
    
    def get_sync_history(self, connector_name: str, limit: int = 10) -> List[Dict]:
        """Get sync history for a connector"""
        db = next(get_db())
        try:
            logs = (db.query(ConnectorSyncLog)
                   .filter(ConnectorSyncLog.connector_name == connector_name)
                   .order_by(ConnectorSyncLog.started_at.desc())
                   .limit(limit)
                   .all())
            
            return [{
                "id": log.id,
                "sync_type": log.sync_type,
                "status": log.status,
                "items_processed": log.items_processed,
                "items_added": log.items_added,
                "items_updated": log.items_updated,
                "items_failed": log.items_failed,
                "duration_seconds": log.duration_seconds,
                "error_message": log.error_message,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "completed_at": log.completed_at.isoformat() if log.completed_at else None
            } for log in logs]
            
        finally:
            db.close()
    
    async def cleanup(self):
        """Cleanup all connectors"""
        self.stop_background_syncs()
        
        for name, connector in self.connectors.items():
            try:
                if hasattr(connector, 'close'):
                    await connector.close()
            except Exception as e:
                logger.error(f"Error closing connector {name}: {e}")
        
        self.connectors.clear()


# Global connector manager instance
connector_manager = ConnectorManager()