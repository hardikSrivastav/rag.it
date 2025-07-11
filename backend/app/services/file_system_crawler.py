import os
import time
from pathlib import Path
from typing import Set, List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.core.database import (
    FileSystemNode, 
    MerkleSnapshot, 
    IndexingPolicy, 
    get_db
)
from app.services.merkle_tree import MerkleTree
from app.core.logging import get_logger

logger = get_logger(__name__)


class FileSystemCrawler:
    """
    File system crawler that builds and maintains Merkle trees,
    detects changes, and manages file indexing policies.
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.indexing_policies = self._load_indexing_policies()
        
    def _load_indexing_policies(self) -> List[IndexingPolicy]:
        """Load all indexing policies from database"""
        return self.db.query(IndexingPolicy).order_by(IndexingPolicy.priority.desc()).all()
    
    def _should_index_file(self, file_path: str, root_path: str = None) -> bool:
        """Check if file should be indexed based on policies and .itnore patterns"""
        path_obj = Path(file_path)
        
        # If root_path is provided, check if file would be skipped by MerkleTree
        if root_path:
            from app.services.merkle_tree import MerkleTree
            temp_tree = MerkleTree(root_path)
            if temp_tree._should_skip_path(path_obj):
                return False
        
        # Check against all policies (highest priority first)
        for policy in self.indexing_policies:
            if self._path_matches_policy(path_obj, policy):
                return policy.should_index
        
        # Default: don't index if no policy matches
        return False
    
    def _path_matches_policy(self, path: Path, policy: IndexingPolicy) -> bool:
        """Check if path matches a specific policy"""
        # Check path pattern
        if policy.path_pattern:
            if not path.match(policy.path_pattern):
                return False
        
        # Check file extensions
        if policy.file_extensions:
            if path.suffix.lower() not in [ext.lower() for ext in policy.file_extensions]:
                return False
        
        # Check file size
        if policy.max_file_size_mb and path.is_file():
            try:
                file_size_mb = path.stat().st_size / (1024 * 1024)
                if file_size_mb > policy.max_file_size_mb:
                    return False
            except (OSError, PermissionError):
                return False
        
        return True
    
    async def scan_directory(self, root_path: str, force_full_scan: bool = False) -> Dict:
        """
        Scan directory and detect changes using Merkle tree comparison.
        
        Args:
            root_path: Root directory to scan
            force_full_scan: If True, rebuild entire tree regardless of changes
            
        Returns:
            Dictionary with scan results and change statistics
        """
        start_time = time.time()
        root_path = Path(root_path).resolve()
        
        logger.info(f"Starting directory scan: {root_path}")
        
        # Build new Merkle tree
        new_tree = MerkleTree(str(root_path))
        await new_tree.build_tree()
        
        # Get previous tree from database
        previous_tree = self._get_previous_tree(str(root_path))
        
        # Detect changes
        if previous_tree and not force_full_scan:
            changed_files = new_tree.get_changed_files(previous_tree)
            logger.info(f"Found {len(changed_files)} changed files")
        else:
            changed_files = set(new_tree.get_all_files())
            logger.info(f"Full scan: {len(changed_files)} files to process")
        
        # Update database with new tree
        self._update_filesystem_nodes(new_tree, changed_files)
        
        # Create snapshot
        scan_duration = time.time() - start_time
        snapshot = self._create_snapshot(new_tree, scan_duration, len(changed_files))
        
        # Filter files that should be indexed
        files_to_index = self._filter_files_for_indexing(changed_files, str(root_path))
        
        result = {
            'scan_duration_seconds': scan_duration,
            'total_files': len(new_tree.get_all_files()),
            'total_directories': len([n for n in new_tree.nodes.values() if n.node_type == 'directory']),
            'changed_files': len(changed_files),
            'files_to_index': len(files_to_index),
            'root_hash': new_tree.root_hash,
            'snapshot_id': snapshot.id,
            'changed_file_paths': list(changed_files),
            'files_to_index_paths': list(files_to_index)
        }
        
        logger.info(f"Directory scan completed", **result)
        return result
    
    def _get_previous_tree(self, root_path: str) -> Optional[MerkleTree]:
        """Get the most recent Merkle tree for the given root path"""
        # Get latest snapshot
        latest_snapshot = (
            self.db.query(MerkleSnapshot)
            .filter(MerkleSnapshot.root_path == root_path)
            .order_by(MerkleSnapshot.created_at.desc())
            .first()
        )
        
        if not latest_snapshot:
            return None
        
        # Get all nodes for this root path
        nodes = (
            self.db.query(FileSystemNode)
            .filter(FileSystemNode.path.startswith(root_path))
            .all()
        )
        
        if not nodes:
            return None
        
        # Rebuild tree from database
        tree = MerkleTree(root_path)
        tree.root_hash = latest_snapshot.root_hash
        
        for node in nodes:
            from app.services.merkle_tree import FileNode
            file_node = FileNode(
                path=node.path,
                hash=node.hash,
                node_type=node.node_type,
                size=node.size,
                modified_time=node.modified_time,
                permissions=node.permissions,
                children_hashes=node.children_hashes
            )
            tree.nodes[node.path] = file_node
        
        return tree
    
    def _update_filesystem_nodes(self, tree: MerkleTree, changed_files: Set[str]):
        """Update filesystem nodes in database"""
        logger.info(f"Updating {len(tree.nodes)} filesystem nodes in database")
        
        # Get existing nodes
        existing_nodes = {
            node.path: node 
            for node in self.db.query(FileSystemNode).all()
        }
        
        # Update or create nodes
        for path, node in tree.nodes.items():
            should_index = self._should_index_file(path, str(tree.root_path)) if node.node_type == 'file' else False
            
            if path in existing_nodes:
                # Update existing node
                db_node = existing_nodes[path]
                db_node.hash = node.hash
                db_node.size = node.size
                db_node.modified_time = node.modified_time
                db_node.permissions = node.permissions
                db_node.children_hashes = node.children_hashes
                db_node.should_index = should_index
                db_node.updated_at = datetime.utcnow()
            else:
                # Create new node
                db_node = FileSystemNode(
                    path=path,
                    hash=node.hash,
                    node_type=node.node_type,
                    size=node.size,
                    modified_time=node.modified_time,
                    permissions=node.permissions,
                    parent_path=str(Path(path).parent) if path != tree.root_path else None,
                    children_hashes=node.children_hashes,
                    should_index=should_index
                )
                self.db.add(db_node)
        
        # Remove nodes that no longer exist
        current_paths = set(tree.nodes.keys())
        for path in existing_nodes:
            if path not in current_paths:
                self.db.delete(existing_nodes[path])
        
        self.db.commit()
    
    def _create_snapshot(self, tree: MerkleTree, scan_duration: float, changes_count: int) -> MerkleSnapshot:
        """Create a snapshot record of the scan"""
        stats = tree.get_stats()
        
        snapshot = MerkleSnapshot(
            root_path=str(tree.root_path),
            root_hash=tree.root_hash,
            total_files=stats['total_files'],
            total_directories=stats['total_directories'],
            total_size_bytes=stats['total_size_bytes'],
            scan_duration_seconds=scan_duration,
            changes_detected=changes_count
        )
        
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        
        return snapshot
    
    def _filter_files_for_indexing(self, file_paths: Set[str], root_path: str = None) -> Set[str]:
        """Filter files that should be indexed based on policies and .itnore patterns"""
        return {path for path in file_paths if self._should_index_file(path, root_path)}
    
    def get_files_to_index(self, limit: int = 100) -> List[FileSystemNode]:
        """Get files that should be indexed but haven't been recently"""
        return (
            self.db.query(FileSystemNode)
            .filter(
                and_(
                    FileSystemNode.node_type == 'file',
                    FileSystemNode.should_index == True,
                    or_(
                        FileSystemNode.last_indexed.is_(None),
                        FileSystemNode.updated_at > FileSystemNode.last_indexed
                    )
                )
            )
            .limit(limit)
            .all()
        )
    
    def mark_file_indexed(self, file_path: str):
        """Mark a file as having been indexed"""
        node = self.db.query(FileSystemNode).filter(FileSystemNode.path == file_path).first()
        if node:
            node.last_indexed = datetime.utcnow()
            self.db.commit()
    
    def get_indexing_stats(self) -> Dict:
        """Get statistics about file indexing"""
        total_files = self.db.query(FileSystemNode).filter(FileSystemNode.node_type == 'file').count()
        
        should_index = (
            self.db.query(FileSystemNode)
            .filter(
                and_(
                    FileSystemNode.node_type == 'file',
                    FileSystemNode.should_index == True
                )
            )
            .count()
        )
        
        indexed = (
            self.db.query(FileSystemNode)
            .filter(
                and_(
                    FileSystemNode.node_type == 'file',
                    FileSystemNode.should_index == True,
                    FileSystemNode.last_indexed.isnot(None)
                )
            )
            .count()
        )
        
        pending = (
            self.db.query(FileSystemNode)
            .filter(
                and_(
                    FileSystemNode.node_type == 'file',
                    FileSystemNode.should_index == True,
                    or_(
                        FileSystemNode.last_indexed.is_(None),
                        FileSystemNode.updated_at > FileSystemNode.last_indexed
                    )
                )
            )
            .count()
        )
        
        return {
            'total_files': total_files,
            'should_index': should_index,
            'indexed': indexed,
            'pending_indexing': pending,
            'index_coverage': round((indexed / should_index * 100) if should_index > 0 else 0, 2)
        }
    
    def create_default_policies(self):
        """Create default indexing policies"""
        default_policies = [
            {
                'name': 'text_files',
                'path_pattern': '**/*',
                'file_extensions': ['.txt', '.md', '.rst', '.doc', '.docx'],
                'max_file_size_mb': 50,
                'should_index': True,
                'priority': 100,
                'description': 'Index common text document formats'
            },
            {
                'name': 'code_files',
                'path_pattern': '**/*',
                'file_extensions': ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.cs', '.go', '.rs'],
                'max_file_size_mb': 10,
                'should_index': True,
                'priority': 90,
                'description': 'Index source code files'
            },
            {
                'name': 'pdfs',
                'path_pattern': '**/*',
                'file_extensions': ['.pdf'],
                'max_file_size_mb': 100,
                'should_index': True,
                'priority': 80,
                'description': 'Index PDF documents'
            },
            {
                'name': 'skip_binaries',
                'path_pattern': '**/*',
                'file_extensions': ['.exe', '.bin', '.dll', '.so', '.dylib', '.app'],
                'should_index': False,
                'priority': 200,
                'description': 'Skip binary executable files'
            },
            {
                'name': 'skip_media',
                'path_pattern': '**/*',
                'file_extensions': ['.mp4', '.avi', '.mov', '.mp3', '.wav', '.jpg', '.png', '.gif'],
                'should_index': False,
                'priority': 190,
                'description': 'Skip media files'
            }
        ]
        
        for policy_data in default_policies:
            existing = self.db.query(IndexingPolicy).filter(IndexingPolicy.name == policy_data['name']).first()
            if not existing:
                policy = IndexingPolicy(**policy_data)
                self.db.add(policy)
        
        self.db.commit()
        self.indexing_policies = self._load_indexing_policies()  # Reload policies