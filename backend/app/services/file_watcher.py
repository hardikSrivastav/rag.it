import asyncio
import time
from pathlib import Path
from typing import Set, Dict, Optional, List
from datetime import datetime, timedelta

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = None
    FileSystemEvent = None

from app.core.logging import get_logger

logger = get_logger(__name__)


class FileChangeHandler(FileSystemEventHandler):
    """Handle file system change events"""
    
    def __init__(self, file_watcher: 'FileWatcher'):
        self.file_watcher = file_watcher
        
    def on_any_event(self, event: FileSystemEvent):
        """Handle any file system event"""
        if event.is_directory:
            return
            
        # Filter out temporary and system files
        if self._should_ignore_file(event.src_path):
            return
            
        # Add to pending changes
        self.file_watcher.add_pending_change(event.src_path, event.event_type)
        
    def _should_ignore_file(self, file_path: str) -> bool:
        """Check if file should be ignored"""
        path = Path(file_path)
        
        # Ignore temporary and system files
        ignore_patterns = {
            '.tmp', '.temp', '.swp', '.swo', '.DS_Store', 'Thumbs.db',
            '~', '.bak', '.backup', '.pyc', '.pyo', '__pycache__'
        }
        
        # Check if file name or extension matches ignore patterns
        if path.name.startswith('.') and path.name not in {'.env', '.gitignore', '.md'}:
            return True
            
        for pattern in ignore_patterns:
            if pattern in path.name or path.suffix == pattern:
                return True
                
        return False


class FileWatcher:
    """
    File system watcher that monitors changes and triggers reindexing.
    
    Uses a debouncing mechanism to batch changes and avoid excessive reindexing.
    """
    
    def __init__(self, debounce_seconds: int = 30):
        self.debounce_seconds = debounce_seconds
        self.pending_changes: Dict[str, Dict] = {}
        self.observer: Optional[Observer] = None
        self.watch_paths: Set[str] = set()
        self.last_processing_time = datetime.now()
        self.processing_task: Optional[asyncio.Task] = None
        
    def add_pending_change(self, file_path: str, event_type: str):
        """Add a file change to pending changes"""
        now = datetime.now()
        
        # Update or add pending change
        self.pending_changes[file_path] = {
            'event_type': event_type,
            'timestamp': now,
            'path': file_path
        }
        
        logger.debug(f"Added pending change: {file_path} ({event_type})")
        
        # Start processing task if not already running
        if not self.processing_task or self.processing_task.done():
            self.processing_task = asyncio.create_task(self._process_pending_changes())
    
    async def _process_pending_changes(self):
        """Process pending changes after debounce period"""
        while True:
            await asyncio.sleep(self.debounce_seconds)
            
            if not self.pending_changes:
                break
                
            # Check if any changes are recent (within debounce period)
            now = datetime.now()
            recent_changes = any(
                (now - change['timestamp']).total_seconds() < self.debounce_seconds
                for change in self.pending_changes.values()
            )
            
            if recent_changes:
                continue  # Wait longer for more changes
                
            # Process the changes
            changes_to_process = dict(self.pending_changes)
            self.pending_changes.clear()
            
            await self._handle_batch_changes(changes_to_process)
            break
    
    async def _handle_batch_changes(self, changes: Dict[str, Dict]):
        """Handle a batch of file changes"""
        if not changes:
            return
            
        logger.info(f"Processing {len(changes)} file changes")
        
        try:
            # Group changes by root directory
            root_dirs = self._group_changes_by_root(changes)
            
            # Process each root directory
            for root_dir, file_changes in root_dirs.items():
                await self._process_root_directory_changes(root_dir, file_changes)
                
        except Exception as e:
            logger.error(f"Error processing file changes: {e}")
    
    def _group_changes_by_root(self, changes: Dict[str, Dict]) -> Dict[str, List[Dict]]:
        """Group changes by their root directory"""
        root_groups = {}
        
        for file_path, change in changes.items():
            # Find the root directory being watched
            path = Path(file_path)
            root_dir = None
            
            for watch_path in self.watch_paths:
                if path.is_relative_to(watch_path):
                    root_dir = watch_path
                    break
            
            if root_dir:
                if root_dir not in root_groups:
                    root_groups[root_dir] = []
                root_groups[root_dir].append(change)
        
        return root_groups
    
    async def _process_root_directory_changes(self, root_dir: str, changes: List[Dict]):
        """Process changes for a specific root directory"""
        logger.info(f"Processing {len(changes)} changes in {root_dir}")
        
        try:
            # Import here to avoid circular imports
            from app.services.file_system_indexer import file_system_indexer
            
            # Trigger incremental indexing for the root directory
            result = await file_system_indexer.index_directory(root_dir, force_full_scan=False)
            
            if result['success']:
                files_indexed = result['indexing_results']['files_succeeded']
                logger.info(f"File watcher triggered indexing: {files_indexed} files updated")
            else:
                logger.error(f"File watcher indexing failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error in file watcher indexing for {root_dir}: {e}")
    
    def start_watching(self, path: str):
        """Start watching a directory for changes"""
        if not WATCHDOG_AVAILABLE:
            logger.warning("Watchdog not available, file watching disabled")
            return
            
        if not Path(path).exists():
            raise ValueError(f"Path does not exist: {path}")
            
        if not Path(path).is_dir():
            raise ValueError(f"Path is not a directory: {path}")
            
        if self.observer is None:
            self.observer = Observer()
            
        # Add to watch paths
        self.watch_paths.add(str(Path(path).resolve()))
        
        # Set up file change handler
        event_handler = FileChangeHandler(self)
        
        # Start watching
        self.observer.schedule(event_handler, path, recursive=True)
        
        if not self.observer.is_alive():
            self.observer.start()
            
        logger.info(f"Started watching directory: {path}")
    
    def stop_watching(self, path: str = None):
        """Stop watching a directory or all directories"""
        if path:
            self.watch_paths.discard(str(Path(path).resolve()))
        else:
            self.watch_paths.clear()
            
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            self.observer = None
            
        # Cancel processing task
        if self.processing_task and not self.processing_task.done():
            self.processing_task.cancel()
            
        logger.info(f"Stopped watching {'all directories' if not path else path}")
    
    def get_status(self) -> Dict:
        """Get current watcher status"""
        return {
            'is_active': self.observer and self.observer.is_alive(),
            'watched_paths': list(self.watch_paths),
            'pending_changes': len(self.pending_changes),
            'debounce_seconds': self.debounce_seconds,
            'last_processing_time': self.last_processing_time.isoformat(),
            'processing_active': self.processing_task and not self.processing_task.done()
        }
    
    def get_pending_changes(self) -> Dict[str, Dict]:
        """Get current pending changes"""
        return dict(self.pending_changes)
    
    def set_debounce_seconds(self, seconds: int):
        """Set debounce period"""
        if seconds < 1:
            raise ValueError("Debounce seconds must be at least 1")
        self.debounce_seconds = seconds
        logger.info(f"Set debounce period to {seconds} seconds")


# Global file watcher instance
file_watcher = FileWatcher()