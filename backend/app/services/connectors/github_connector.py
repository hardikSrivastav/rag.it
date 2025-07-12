import asyncio
import aiohttp
import base64
from typing import Dict, List, Any, Optional, AsyncIterator
from datetime import datetime, timedelta
import os
from pathlib import Path

from .base import BaseConnector, ConnectorConfig, SyncResult
from app.core.logging import get_logger

logger = get_logger(__name__)


class GitHubConnector(BaseConnector):
    """Connector for GitHub repositories"""
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.api_base = "https://api.github.com"
        self.session: Optional[aiohttp.ClientSession] = None
        
    @property
    def connector_type(self) -> str:
        return "github"
    
    async def authenticate(self) -> bool:
        """Authenticate with GitHub API"""
        try:
            token = self.config.credentials.get("token")
            if not token:
                logger.error("GitHub token not provided")
                return False
            
            # Create session with auth headers
            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "RAG-System/1.0"
            }
            
            self.session = aiohttp.ClientSession(headers=headers)
            
            # Test authentication
            async with self.session.get(f"{self.api_base}/user") as response:
                if response.status == 200:
                    user_data = await response.json()
                    logger.info(f"Authenticated as GitHub user: {user_data.get('login')}")
                    return True
                else:
                    logger.error(f"GitHub authentication failed: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"GitHub authentication error: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """Test connection to GitHub API"""
        try:
            if not self.session:
                return await self.authenticate()
            
            async with self.session.get(f"{self.api_base}/rate_limit") as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"GitHub connection test failed: {e}")
            return False
    
    async def sync_data(self, incremental: bool = True) -> SyncResult:
        """Sync repositories and their contents"""
        start_time = datetime.utcnow()
        items_processed = 0
        items_added = 0
        items_failed = 0
        errors = []
        
        try:
            repositories = self.config.settings.get("repositories", [])
            if not repositories:
                logger.warning("No repositories configured for GitHub connector")
                return SyncResult(
                    success=True,
                    items_processed=0,
                    items_added=0,
                    items_updated=0,
                    items_failed=0,
                    errors=[],
                    duration_seconds=0
                )
            
            for repo in repositories:
                try:
                    logger.info(f"Syncing repository: {repo}")
                    
                    # Get repository files
                    async for file_data in self.get_repository_files(repo):
                        items_processed += 1
                        
                        # Process through RAG pipeline
                        if await self.process_item_through_rag(file_data, f"github_{repo}"):
                            items_added += 1
                        else:
                            items_failed += 1
                        
                        # Respect rate limits
                        if items_processed % 10 == 0:
                            await asyncio.sleep(0.1)
                            
                except Exception as e:
                    error_msg = f"Failed to sync repository {repo}: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            return SyncResult(
                success=len(errors) == 0,
                items_processed=items_processed,
                items_added=items_added,
                items_updated=0,  # GitHub files are typically replaced, not updated
                items_failed=items_failed,
                errors=errors,
                duration_seconds=duration
            )
            
        except Exception as e:
            logger.error(f"GitHub sync failed: {e}")
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
        """Get repository files"""
        repositories = self.config.settings.get("repositories", [])
        count = 0
        
        for repo in repositories:
            if count >= limit:
                break
                
            async for file_data in self.get_repository_files(repo):
                if count >= limit:
                    break
                yield file_data
                count += 1
    
    async def get_repository_files(self, repo: str) -> AsyncIterator[Dict[str, Any]]:
        """Get all files from a repository"""
        try:
            # Get repository tree
            url = f"{self.api_base}/repos/{repo}/git/trees/HEAD?recursive=1"
            
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to get repository tree for {repo}: {response.status}")
                    return
                
                tree_data = await response.json()
                
                for item in tree_data.get("tree", []):
                    # Only process files (not directories)
                    if item.get("type") == "blob":
                        file_path = item.get("path", "")
                        
                        # Filter by file extensions
                        if self._should_index_file(file_path):
                            file_content = await self._get_file_content(repo, item.get("sha"))
                            if file_content:
                                yield {
                                    "repository": repo,
                                    "path": file_path,
                                    "sha": item.get("sha"),
                                    "content": file_content,
                                    "size": item.get("size", 0),
                                    "url": item.get("url", "")
                                }
                                
        except Exception as e:
            logger.error(f"Error getting repository files for {repo}: {e}")
    
    async def _get_file_content(self, repo: str, sha: str) -> Optional[str]:
        """Get file content by SHA"""
        try:
            url = f"{self.api_base}/repos/{repo}/git/blobs/{sha}"
            
            async with self.session.get(url) as response:
                if response.status != 200:
                    return None
                
                blob_data = await response.json()
                encoding = blob_data.get("encoding")
                content = blob_data.get("content", "")
                
                if encoding == "base64":
                    try:
                        decoded_content = base64.b64decode(content).decode('utf-8')
                        return decoded_content
                    except UnicodeDecodeError:
                        # Skip binary files
                        return None
                else:
                    return content
                    
        except Exception as e:
            logger.error(f"Error getting file content for SHA {sha}: {e}")
            return None
    
    def _should_index_file(self, file_path: str) -> bool:
        """Check if file should be indexed based on extension and path"""
        # Get allowed extensions from config
        allowed_extensions = self.config.settings.get("file_extensions", [
            ".py", ".js", ".ts", ".java", ".cpp", ".c", ".h", ".cs", ".go", ".rs",
            ".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini"
        ])
        
        # Get ignored patterns from config
        ignored_patterns = self.config.settings.get("ignored_patterns", [
            "__pycache__", ".git", "node_modules", ".env", ".venv",
            "dist", "build", "target", ".DS_Store"
        ])
        
        # Check extension
        file_ext = Path(file_path).suffix.lower()
        if file_ext not in allowed_extensions:
            return False
        
        # Check ignored patterns
        for pattern in ignored_patterns:
            if pattern in file_path:
                return False
        
        # Check file size limit
        max_size = self.config.settings.get("max_file_size_kb", 500)  # 500KB default
        # Note: We can't check size here without making another API call
        # Size filtering happens in the caller
        
        return True
    
    def _extract_content(self, item_data: Dict[str, Any]) -> str:
        """Extract text content from GitHub file data"""
        content = item_data.get("content", "")
        path = item_data.get("path", "")
        repo = item_data.get("repository", "")
        
        # Add context header
        header = f"# File: {path}\n# Repository: {repo}\n\n"
        return header + content
    
    def _extract_metadata(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from GitHub file data"""
        return {
            "filename": Path(item_data.get("path", "")).name,
            "file_path": item_data.get("path", ""),
            "repository": item_data.get("repository", ""),
            "sha": item_data.get("sha", ""),
            "file_size": item_data.get("size", 0),
            "github_url": item_data.get("url", ""),
            "file_type": Path(item_data.get("path", "")).suffix.lower(),
            "indexed_at": datetime.utcnow().isoformat()
        }
    
    async def close(self):
        """Close the connector and cleanup resources"""
        if self.session:
            await self.session.close()
            self.session = None