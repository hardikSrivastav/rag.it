from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, AsyncIterator
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import asyncio

from app.core.logging import get_logger

logger = get_logger(__name__)


class ConnectorStatus(Enum):
    """Connector status enumeration"""
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class ConnectorConfig:
    """Base configuration for connectors"""
    name: str
    enabled: bool = True
    sync_interval_minutes: int = 60  # Default 1 hour
    max_items_per_sync: int = 1000
    last_sync: Optional[datetime] = None
    credentials: Dict[str, Any] = None
    settings: Dict[str, Any] = None


@dataclass
class SyncResult:
    """Result of a connector sync operation"""
    success: bool
    items_processed: int
    items_added: int
    items_updated: int
    items_failed: int
    errors: List[str]
    duration_seconds: float
    next_sync_token: Optional[str] = None


class BaseConnector(ABC):
    """Abstract base class for all data connectors"""
    
    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.status = ConnectorStatus.IDLE
        self.last_error: Optional[str] = None
        self.sync_task: Optional[asyncio.Task] = None
        
    @property
    @abstractmethod
    def connector_type(self) -> str:
        """Return the connector type identifier"""
        pass
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the external service"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test connection to the external service"""
        pass
    
    @abstractmethod
    async def sync_data(self, incremental: bool = True) -> SyncResult:
        """Sync data from the external service"""
        pass
    
    @abstractmethod
    async def get_items(self, limit: int = 100, cursor: Optional[str] = None) -> AsyncIterator[Dict[str, Any]]:
        """Get items from the external service"""
        pass
    
    async def start_sync(self, incremental: bool = True) -> SyncResult:
        """Start a sync operation with error handling"""
        if self.status == ConnectorStatus.RUNNING:
            raise ValueError(f"Connector {self.config.name} is already running")
        
        self.status = ConnectorStatus.RUNNING
        self.last_error = None
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Starting sync for {self.connector_type} connector", 
                       connector=self.config.name, incremental=incremental)
            
            # Authenticate if needed
            if not await self.authenticate():
                raise Exception("Authentication failed")
            
            # Perform sync
            result = await self.sync_data(incremental)
            
            # Update config
            self.config.last_sync = datetime.utcnow()
            self.status = ConnectorStatus.IDLE
            
            logger.info(f"Sync completed for {self.connector_type} connector",
                       connector=self.config.name,
                       items_processed=result.items_processed,
                       duration=result.duration_seconds)
            
            return result
            
        except Exception as e:
            self.status = ConnectorStatus.ERROR
            self.last_error = str(e)
            
            logger.error(f"Sync failed for {self.connector_type} connector",
                        connector=self.config.name,
                        error=str(e))
            
            return SyncResult(
                success=False,
                items_processed=0,
                items_added=0,
                items_updated=0,
                items_failed=0,
                errors=[str(e)],
                duration_seconds=(datetime.utcnow() - start_time).total_seconds()
            )
    
    async def start_background_sync(self):
        """Start background sync task"""
        if self.sync_task and not self.sync_task.done():
            logger.warning(f"Background sync already running for {self.config.name}")
            return
        
        self.sync_task = asyncio.create_task(self._background_sync_loop())
        logger.info(f"Background sync started for {self.config.name}")
    
    def stop_background_sync(self):
        """Stop background sync task"""
        if self.sync_task and not self.sync_task.done():
            self.sync_task.cancel()
            logger.info(f"Background sync stopped for {self.config.name}")
    
    async def _background_sync_loop(self):
        """Background sync loop"""
        while True:
            try:
                if self.config.enabled and self.status != ConnectorStatus.ERROR:
                    await self.start_sync(incremental=True)
                
                # Wait for next sync
                await asyncio.sleep(self.config.sync_interval_minutes * 60)
                
            except asyncio.CancelledError:
                logger.info(f"Background sync cancelled for {self.config.name}")
                break
            except Exception as e:
                logger.error(f"Error in background sync for {self.config.name}: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    def get_status(self) -> Dict[str, Any]:
        """Get connector status"""
        return {
            "name": self.config.name,
            "type": self.connector_type,
            "status": self.status.value,
            "enabled": self.config.enabled,
            "last_sync": self.config.last_sync.isoformat() if self.config.last_sync else None,
            "last_error": self.last_error,
            "sync_interval_minutes": self.config.sync_interval_minutes,
            "has_background_task": self.sync_task is not None and not self.sync_task.done()
        }
    
    async def process_item_through_rag(self, item_data: Dict[str, Any], source_tool: str) -> bool:
        """Process an item through the RAG pipeline"""
        try:
            # Import here to avoid circular imports
            from app.services.rag_pipeline import rag_pipeline
            
            # Extract content and metadata
            content = self._extract_content(item_data)
            metadata = self._extract_metadata(item_data)
            metadata["source_tool"] = source_tool
            metadata["connector_type"] = self.connector_type
            
            # Ingest through RAG pipeline
            result = await rag_pipeline.ingest_text(content, metadata)
            
            logger.debug(f"Item processed through RAG",
                        connector=self.config.name,
                        document_id=result["document_id"])
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process item through RAG",
                        connector=self.config.name,
                        error=str(e))
            return False
    
    @abstractmethod
    def _extract_content(self, item_data: Dict[str, Any]) -> str:
        """Extract text content from item data"""
        pass
    
    @abstractmethod
    def _extract_metadata(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from item data"""
        pass