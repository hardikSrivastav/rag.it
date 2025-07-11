import hashlib
import os
import json
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
import asyncio
import aiofiles
import stat
import fnmatch

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FileNode:
    """Represents a file or directory in the Merkle tree"""
    path: str
    hash: str
    node_type: str  # 'file' or 'directory'
    size: int
    modified_time: float
    permissions: int
    parent_hash: Optional[str] = None
    children_hashes: Optional[List[str]] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FileNode':
        """Create from dictionary"""
        return cls(**data)


class MerkleTree:
    """
    Merkle tree implementation for efficient file system change detection.
    
    Each file is a leaf node with hash computed from content + metadata.
    Each directory is an internal node with hash computed from children hashes.
    """
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path).resolve()
        self.nodes: Dict[str, FileNode] = {}
        self.root_hash: Optional[str] = None
        self._ignore_patterns: Optional[Set[str]] = None
        
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute hash for a file based on content and metadata"""
        try:
            # Get file stats
            stat_info = file_path.stat()
            
            # Create hash from content + metadata
            hasher = hashlib.sha256()
            
            # Add file content
            if file_path.is_file() and stat_info.st_size > 0:
                try:
                    with open(file_path, 'rb') as f:
                        # Read file in chunks to handle large files
                        while chunk := f.read(8192):
                            hasher.update(chunk)
                except (PermissionError, OSError) as e:
                    logger.warning(f"Cannot read file {file_path}: {e}")
                    # Use file path + metadata if can't read content
                    hasher.update(str(file_path).encode())
            
            # Add metadata
            metadata = {
                'path': str(file_path),
                'size': stat_info.st_size,
                'modified_time': stat_info.st_mtime,
                'permissions': stat_info.st_mode
            }
            hasher.update(json.dumps(metadata, sort_keys=True).encode())
            
            return hasher.hexdigest()
            
        except (OSError, PermissionError) as e:
            logger.warning(f"Cannot access file {file_path}: {e}")
            # Fallback to path-based hash
            return hashlib.sha256(str(file_path).encode()).hexdigest()
    
    def _compute_directory_hash(self, children_hashes: List[str]) -> str:
        """Compute hash for a directory based on children hashes"""
        # Sort children hashes for consistent ordering
        sorted_hashes = sorted(children_hashes)
        combined = ''.join(sorted_hashes)
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def _load_ignore_patterns(self) -> Set[str]:
        """Load ignore patterns from .itnore file in the root directory"""
        if self._ignore_patterns is not None:
            return self._ignore_patterns
        
        ignore_file = self.root_path / '.itnore'
        patterns = set()
        
        if ignore_file.exists():
            try:
                with open(ignore_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and comments
                        if line and not line.startswith('#'):
                            patterns.add(line)
                logger.info(f"Loaded {len(patterns)} ignore patterns from {ignore_file}")
            except (OSError, PermissionError) as e:
                logger.warning(f"Cannot read .itnore file {ignore_file}: {e}")
        
        self._ignore_patterns = patterns
        return patterns
    
    def _matches_ignore_pattern(self, path: Path) -> bool:
        """Check if path matches any ignore pattern from .itnore file"""
        ignore_patterns = self._load_ignore_patterns()
        
        if not ignore_patterns:
            return False
        
        # Get relative path from root for pattern matching
        try:
            relative_path = path.relative_to(self.root_path)
            path_str = str(relative_path)
            
            # Check each pattern
            for pattern in ignore_patterns:
                # Handle directory patterns (ending with /)
                if pattern.endswith('/'):
                    dir_pattern = pattern.rstrip('/')
                    # Match if any part of the path matches the directory pattern
                    if any(fnmatch.fnmatch(part, dir_pattern) for part in relative_path.parts):
                        return True
                    # Also check if the full path matches
                    if fnmatch.fnmatch(path_str, dir_pattern):
                        return True
                else:
                    # File pattern - check filename and full path
                    if fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(path_str, pattern):
                        return True
                    # Also check if any parent directory matches
                    if any(fnmatch.fnmatch(part, pattern) for part in relative_path.parts[:-1]):
                        return True
            
            return False
            
        except ValueError:
            # Path is not relative to root_path, don't ignore
            return False
    
    def _should_skip_path(self, path: Path) -> bool:
        """Check if path should be skipped during traversal"""
        # First check if path matches itnore patterns
        if self._matches_ignore_pattern(path):
            return True
        
        # Built-in skip patterns
        skip_patterns = {
            '.git', '.svn', '.hg',  # Version control
            '__pycache__', '.pyc',  # Python cache
            'node_modules',  # Node.js
            '.DS_Store',  # macOS
            'Thumbs.db',  # Windows
            '.Trash',  # Trash folders
            '.cache', '.tmp', '.temp',  # Cache/temp folders
        }
        
        # Skip if any part of path matches skip patterns
        for part in path.parts:
            if part in skip_patterns or (part.startswith('.') and part != '..'):
                return True
        
        # Skip if permission denied
        try:
            path.stat()
            return False
        except (PermissionError, OSError):
            return True
    
    async def build_tree(self) -> str:
        """Build the complete Merkle tree from root path"""
        logger.info(f"Building Merkle tree for {self.root_path}")
        
        try:
            self.root_hash = await self._build_node(self.root_path)
            logger.info(f"Merkle tree built successfully. Root hash: {self.root_hash}")
            return self.root_hash
        except Exception as e:
            logger.error(f"Failed to build Merkle tree: {e}")
            raise
    
    async def _build_node(self, path: Path) -> str:
        """Recursively build a node and its children"""
        if self._should_skip_path(path):
            return ""
        
        try:
            stat_info = path.stat()
            
            if path.is_file():
                # File node
                file_hash = self._compute_file_hash(path)
                node = FileNode(
                    path=str(path),
                    hash=file_hash,
                    node_type='file',
                    size=stat_info.st_size,
                    modified_time=stat_info.st_mtime,
                    permissions=stat_info.st_mode
                )
                self.nodes[str(path)] = node
                return file_hash
                
            elif path.is_dir():
                # Directory node
                children_hashes = []
                
                try:
                    # Get all children
                    for child_path in path.iterdir():
                        child_hash = await self._build_node(child_path)
                        if child_hash:  # Only add non-empty hashes
                            children_hashes.append(child_hash)
                except (PermissionError, OSError) as e:
                    logger.warning(f"Cannot access directory {path}: {e}")
                
                # Compute directory hash
                dir_hash = self._compute_directory_hash(children_hashes)
                node = FileNode(
                    path=str(path),
                    hash=dir_hash,
                    node_type='directory',
                    size=len(children_hashes),
                    modified_time=stat_info.st_mtime,
                    permissions=stat_info.st_mode,
                    children_hashes=children_hashes
                )
                self.nodes[str(path)] = node
                return dir_hash
                
        except (OSError, PermissionError) as e:
            logger.warning(f"Cannot process path {path}: {e}")
            return ""
        
        return ""
    
    def get_changed_files(self, other_tree: 'MerkleTree') -> Set[str]:
        """Compare with another tree and return paths of changed files"""
        changed_files = set()
        
        # Find files that are new, modified, or deleted
        all_paths = set(self.nodes.keys()) | set(other_tree.nodes.keys())
        
        for path in all_paths:
            self_node = self.nodes.get(path)
            other_node = other_tree.nodes.get(path)
            
            if self_node is None:
                # File deleted
                if other_node and other_node.node_type == 'file':
                    changed_files.add(path)
            elif other_node is None:
                # File added
                if self_node.node_type == 'file':
                    changed_files.add(path)
            elif self_node.hash != other_node.hash:
                # File modified
                if self_node.node_type == 'file':
                    changed_files.add(path)
        
        return changed_files
    
    def get_all_files(self) -> List[str]:
        """Get all file paths in the tree"""
        return [path for path, node in self.nodes.items() if node.node_type == 'file']
    
    def to_json(self) -> str:
        """Serialize tree to JSON"""
        data = {
            'root_path': str(self.root_path),
            'root_hash': self.root_hash,
            'nodes': {path: node.to_dict() for path, node in self.nodes.items()}
        }
        return json.dumps(data, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'MerkleTree':
        """Deserialize tree from JSON"""
        data = json.loads(json_str)
        tree = cls(data['root_path'])
        tree.root_hash = data['root_hash']
        tree.nodes = {path: FileNode.from_dict(node_data) 
                     for path, node_data in data['nodes'].items()}
        return tree
    
    def get_stats(self) -> Dict:
        """Get statistics about the tree"""
        files = [node for node in self.nodes.values() if node.node_type == 'file']
        directories = [node for node in self.nodes.values() if node.node_type == 'directory']
        
        total_size = sum(node.size for node in files)
        
        return {
            'total_files': len(files),
            'total_directories': len(directories),
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'root_hash': self.root_hash,
            'root_path': str(self.root_path)
        }