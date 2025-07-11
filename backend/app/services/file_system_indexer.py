import asyncio
import time
from typing import List, Dict, Set, Optional
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.database import get_db, FileSystemNode, Document
from app.services.file_system_crawler import FileSystemCrawler
# Import will be done dynamically to avoid circular imports
# from app.services.rag_pipeline import rag_pipeline
from app.core.logging import get_logger

logger = get_logger(__name__)


class FileSystemIndexer:
    """
    Manages the complete file system indexing process:
    1. Crawls file system using Merkle trees
    2. Detects changes
    3. Indexes changed files through RAG pipeline
    4. Maintains sync between file system and vector database
    """
    
    def __init__(self):
        self.is_running = False
        self.current_scan_task = None
        
    async def index_directory(self, root_path: str, force_full_scan: bool = False) -> Dict:
        """
        Index a directory and all its contents.
        
        Args:
            root_path: Root directory to index
            force_full_scan: If True, reindex everything regardless of changes
            
        Returns:
            Dictionary with indexing results
        """
        if self.is_running:
            raise ValueError("Indexing already in progress")
            
        self.is_running = True
        start_time = time.time()
        
        try:
            logger.info(f"Starting directory indexing: {root_path}")
            
            # Get database session
            with next(get_db()) as db:
                crawler = FileSystemCrawler(db)
                
                # Create default policies if none exist
                crawler.create_default_policies()
                
                # Scan directory and detect changes
                scan_result = await crawler.scan_directory(root_path, force_full_scan)
                
                # Get files that need indexing
                files_to_index = crawler.get_files_to_index(limit=1000)
                
                # Index files through RAG pipeline
                indexing_results = await self._index_files(files_to_index, crawler, db)
                
                # Update statistics
                stats = crawler.get_indexing_stats()
                
                total_duration = time.time() - start_time
                
                result = {
                    'success': True,
                    'total_duration_seconds': total_duration,
                    'scan_results': scan_result,
                    'indexing_results': indexing_results,
                    'stats': stats
                }
                
                logger.info("Directory indexing completed", **result)
                return result
                
        except Exception as e:
            logger.error(f"Directory indexing failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'total_duration_seconds': time.time() - start_time
            }
        finally:
            self.is_running = False
    
    async def _index_files(self, files: List[FileSystemNode], crawler: FileSystemCrawler, db: Session) -> Dict:
        """Index a list of files through the RAG pipeline"""
        if not files:
            return {'files_processed': 0, 'files_succeeded': 0, 'files_failed': 0, 'errors': []}
        
        logger.info(f"Starting to index {len(files)} files")
        
        files_processed = 0
        files_succeeded = 0
        files_failed = 0
        errors = []
        
        for file_node in files:
            try:
                # Check if file still exists and is readable
                file_path = Path(file_node.path)
                if not file_path.exists() or not file_path.is_file():
                    logger.warning(f"File no longer exists: {file_path}")
                    continue
                
                # Index through RAG pipeline
                await self._index_single_file(file_node, db)
                
                # Mark as indexed
                crawler.mark_file_indexed(file_node.path)
                
                files_succeeded += 1
                files_processed += 1
                
                logger.debug(f"Successfully indexed: {file_node.path}")
                
            except Exception as e:
                files_failed += 1
                files_processed += 1
                error_msg = f"Failed to index {file_node.path}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        result = {
            'files_processed': files_processed,
            'files_succeeded': files_succeeded,
            'files_failed': files_failed,
            'errors': errors
        }
        
        logger.info("File indexing batch completed", **result)
        return result
    
    async def _index_single_file(self, file_node: FileSystemNode, db: Session):
        """Index a single file through the RAG pipeline"""
        file_path = Path(file_node.path)
        
        # Check if this file is already in the documents table
        existing_doc = (
            db.query(Document)
            .filter(Document.file_path == str(file_path))
            .first()
        )
        
        # Import here to avoid circular imports
        from app.services.rag_pipeline import rag_pipeline
        
        if existing_doc:
            # Delete existing document and its chunks first
            rag_pipeline.delete_document(existing_doc.id)
        
        # Use RAG pipeline to ingest the file
        metadata = {
            'modified_time': file_node.modified_time,
            'permissions': file_node.permissions,
            'file_system_hash': file_node.hash
        }
        
        result = await rag_pipeline.ingest_file(
            str(file_path), 
            source_tool="file_system_indexer",
            metadata=metadata
        )
    
    def _get_content_type(self, file_path: Path) -> str:
        """Get content type based on file extension"""
        extension = file_path.suffix.lower()
        
        content_type_map = {
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.rst': 'text/x-rst',
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.py': 'text/x-python',
            '.js': 'text/javascript',
            '.ts': 'text/typescript',
            '.java': 'text/x-java',
            '.cpp': 'text/x-c++src',
            '.c': 'text/x-csrc',
            '.h': 'text/x-chdr',
            '.cs': 'text/x-csharp',
            '.go': 'text/x-go',
            '.rs': 'text/x-rust'
        }
        
        return content_type_map.get(extension, 'application/octet-stream')
    
    def get_indexing_status(self) -> Dict:
        """Get current indexing status"""
        with next(get_db()) as db:
            crawler = FileSystemCrawler(db)
            stats = crawler.get_indexing_stats()
            
            return {
                'is_running': self.is_running,
                'stats': stats,
                'has_scan_task': self.current_scan_task is not None
            }
    
    async def continuous_indexing(self, root_path: str, scan_interval_seconds: int = 300):
        """
        Run continuous indexing with periodic scans.
        
        Args:
            root_path: Root directory to monitor
            scan_interval_seconds: How often to scan for changes (default: 5 minutes)
        """
        logger.info(f"Starting continuous indexing for {root_path} (interval: {scan_interval_seconds}s)")
        
        while True:
            try:
                # Perform incremental scan and indexing
                result = await self.index_directory(root_path, force_full_scan=False)
                
                if result['success']:
                    files_indexed = result['indexing_results']['files_succeeded']
                    if files_indexed > 0:
                        logger.info(f"Continuous indexing: indexed {files_indexed} files")
                else:
                    logger.error(f"Continuous indexing failed: {result.get('error', 'Unknown error')}")
                
                # Wait before next scan
                await asyncio.sleep(scan_interval_seconds)
                
            except asyncio.CancelledError:
                logger.info("Continuous indexing cancelled")
                break
            except Exception as e:
                logger.error(f"Error in continuous indexing: {e}")
                await asyncio.sleep(scan_interval_seconds)
    
    async def start_background_indexing(self, root_path: str, scan_interval_seconds: int = 300):
        """Start background indexing task"""
        if self.current_scan_task and not self.current_scan_task.done():
            logger.warning("Background indexing already running")
            return
        
        self.current_scan_task = asyncio.create_task(
            self.continuous_indexing(root_path, scan_interval_seconds)
        )
        
        logger.info(f"Background indexing started for {root_path}")
    
    def stop_background_indexing(self):
        """Stop background indexing task"""
        if self.current_scan_task and not self.current_scan_task.done():
            self.current_scan_task.cancel()
            logger.info("Background indexing stopped")


# Global indexer instance
file_system_indexer = FileSystemIndexer()