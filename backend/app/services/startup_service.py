import asyncio
import os
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.services.file_system_indexer import file_system_indexer
from app.services.file_watcher import file_watcher
from app.services.connectors.manager import connector_manager

logger = get_logger(__name__)


class StartupService:
    """Service to handle application startup tasks"""
    
    def __init__(self):
        self.startup_completed = False
        
    async def initialize(self):
        """Initialize the application services"""
        if self.startup_completed:
            return
            
        logger.info("Starting application initialization")
        
        try:
            # Initialize file system indexing
            await self._initialize_file_system_indexing()
            
            # Initialize connectors
            await self._initialize_connectors()
            
            self.startup_completed = True
            logger.info("Application initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Application initialization failed: {e}")
            raise
    
    async def _initialize_file_system_indexing(self):
        """Initialize file system indexing for the home directory"""
        try:
            logger.info("File system indexing initialization disabled for Docker container")
            logger.info("Use the API endpoints to manually start indexing")
            
            # In Docker, we'll skip automatic initialization
            # Users can manually start indexing via API calls
            
        except Exception as e:
            logger.error(f"Failed to initialize file system indexing: {e}")
            raise
    
    async def _run_initial_indexing(self, target_path: str):
        """Run initial indexing in the background"""
        try:
            logger.info(f"Starting initial file system scan: {target_path}")
            
            # Perform initial indexing
            result = await file_system_indexer.index_directory(target_path, force_full_scan=True)
            
            if result['success']:
                logger.info(f"Initial indexing completed successfully",
                           files_processed=result['indexing_results']['files_processed'],
                           files_succeeded=result['indexing_results']['files_succeeded'])
                
                # Start file watcher for continuous monitoring
                file_watcher.start_watching(target_path)
                logger.info(f"Started file watcher for: {target_path}")
                
                # Start background indexing task
                await file_system_indexer.start_background_indexing(target_path, scan_interval_seconds=300)
                logger.info(f"Started background indexing for: {target_path}")
                
            else:
                logger.error(f"Initial indexing failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Initial indexing failed: {e}")
    
    async def _initialize_connectors(self):
        """Initialize data connectors"""
        try:
            logger.info("Initializing data connectors")
            await connector_manager.initialize()
            
            # Start background syncs for enabled connectors
            await connector_manager.start_background_syncs()
            
            logger.info("Data connectors initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize connectors: {e}")
            # Don't raise - connectors are optional
    
    def get_status(self) -> dict:
        """Get startup service status"""
        return {
            "startup_completed": self.startup_completed,
            "indexer_status": file_system_indexer.get_indexing_status(),
            "watcher_status": file_watcher.get_status(),
            "connectors_status": connector_manager.get_all_connector_status()
        }


# Global startup service instance
startup_service = StartupService()