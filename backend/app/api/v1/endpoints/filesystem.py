from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from pydantic import BaseModel
from pathlib import Path

from app.core.database import get_db, IndexingPolicy
from app.core.logging import get_logger
from app.services.file_system_indexer import file_system_indexer
from app.services.file_watcher import file_watcher
from app.services.file_system_crawler import FileSystemCrawler

logger = get_logger(__name__)

router = APIRouter()


class IndexDirectoryRequest(BaseModel):
    path: str
    force_full_scan: bool = False


class StartWatchingRequest(BaseModel):
    path: str
    debounce_seconds: int = 30


class CreatePolicyRequest(BaseModel):
    name: str
    path_pattern: str
    file_extensions: Optional[List[str]] = None
    max_file_size_mb: Optional[int] = None
    should_index: bool = True
    priority: int = 0
    description: Optional[str] = None


class UpdatePolicyRequest(BaseModel):
    path_pattern: Optional[str] = None
    file_extensions: Optional[List[str]] = None
    max_file_size_mb: Optional[int] = None
    should_index: Optional[bool] = None
    priority: Optional[int] = None
    description: Optional[str] = None


@router.post("/index-directory")
async def index_directory(request: IndexDirectoryRequest):
    """Index a directory and detect changes using Merkle trees"""
    try:
        # Validate path
        if not Path(request.path).exists():
            raise HTTPException(status_code=400, detail=f"Path does not exist: {request.path}")
            
        if not Path(request.path).is_dir():
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {request.path}")
        
        logger.info(f"Starting directory indexing via API: {request.path}")
        
        # Start indexing
        result = await file_system_indexer.index_directory(
            request.path,
            force_full_scan=request.force_full_scan
        )
        
        return {
            "success": True,
            "message": f"Directory indexing completed",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Directory indexing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to index directory: {str(e)}")


@router.get("/indexing-status")
async def get_indexing_status():
    """Get current indexing status"""
    try:
        return file_system_indexer.get_indexing_status()
    except Exception as e:
        logger.error(f"Failed to get indexing status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get indexing status: {str(e)}")


@router.post("/start-watching")
async def start_watching(request: StartWatchingRequest):
    """Start watching a directory for changes"""
    try:
        # Validate path
        if not Path(request.path).exists():
            raise HTTPException(status_code=400, detail=f"Path does not exist: {request.path}")
            
        if not Path(request.path).is_dir():
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {request.path}")
        
        # Set debounce period
        file_watcher.set_debounce_seconds(request.debounce_seconds)
        
        # Start watching
        file_watcher.start_watching(request.path)
        
        return {
            "success": True,
            "message": f"Started watching directory: {request.path}",
            "debounce_seconds": request.debounce_seconds
        }
        
    except Exception as e:
        logger.error(f"Failed to start watching: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start watching: {str(e)}")


@router.post("/stop-watching")
async def stop_watching(path: Optional[str] = None):
    """Stop watching a directory or all directories"""
    try:
        file_watcher.stop_watching(path)
        
        return {
            "success": True,
            "message": f"Stopped watching {'all directories' if not path else path}"
        }
        
    except Exception as e:
        logger.error(f"Failed to stop watching: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop watching: {str(e)}")


@router.get("/watcher-status")
async def get_watcher_status():
    """Get file watcher status"""
    try:
        return file_watcher.get_status()
    except Exception as e:
        logger.error(f"Failed to get watcher status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get watcher status: {str(e)}")


@router.get("/pending-changes")
async def get_pending_changes():
    """Get pending file changes"""
    try:
        return {
            "pending_changes": file_watcher.get_pending_changes()
        }
    except Exception as e:
        logger.error(f"Failed to get pending changes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get pending changes: {str(e)}")


@router.get("/policies")
async def get_indexing_policies(db: Session = Depends(get_db)):
    """Get all indexing policies"""
    try:
        policies = db.query(IndexingPolicy).order_by(IndexingPolicy.priority.desc()).all()
        return {
            "policies": [
                {
                    "id": policy.id,
                    "name": policy.name,
                    "path_pattern": policy.path_pattern,
                    "file_extensions": policy.file_extensions,
                    "max_file_size_mb": policy.max_file_size_mb,
                    "should_index": policy.should_index,
                    "priority": policy.priority,
                    "description": policy.description,
                    "created_at": policy.created_at,
                    "updated_at": policy.updated_at
                }
                for policy in policies
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get indexing policies: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get indexing policies: {str(e)}")


@router.post("/policies")
async def create_indexing_policy(request: CreatePolicyRequest, db: Session = Depends(get_db)):
    """Create a new indexing policy"""
    try:
        # Check if policy name already exists
        existing = db.query(IndexingPolicy).filter(IndexingPolicy.name == request.name).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Policy with name '{request.name}' already exists")
        
        # Create new policy
        policy = IndexingPolicy(
            name=request.name,
            path_pattern=request.path_pattern,
            file_extensions=request.file_extensions,
            max_file_size_mb=request.max_file_size_mb,
            should_index=request.should_index,
            priority=request.priority,
            description=request.description
        )
        
        db.add(policy)
        db.commit()
        db.refresh(policy)
        
        return {
            "success": True,
            "message": f"Created indexing policy: {request.name}",
            "policy": {
                "id": policy.id,
                "name": policy.name,
                "path_pattern": policy.path_pattern,
                "file_extensions": policy.file_extensions,
                "max_file_size_mb": policy.max_file_size_mb,
                "should_index": policy.should_index,
                "priority": policy.priority,
                "description": policy.description
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create indexing policy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create indexing policy: {str(e)}")


@router.put("/policies/{policy_id}")
async def update_indexing_policy(
    policy_id: int, 
    request: UpdatePolicyRequest, 
    db: Session = Depends(get_db)
):
    """Update an existing indexing policy"""
    try:
        policy = db.query(IndexingPolicy).filter(IndexingPolicy.id == policy_id).first()
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")
        
        # Update fields
        if request.path_pattern is not None:
            policy.path_pattern = request.path_pattern
        if request.file_extensions is not None:
            policy.file_extensions = request.file_extensions
        if request.max_file_size_mb is not None:
            policy.max_file_size_mb = request.max_file_size_mb
        if request.should_index is not None:
            policy.should_index = request.should_index
        if request.priority is not None:
            policy.priority = request.priority
        if request.description is not None:
            policy.description = request.description
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Updated indexing policy: {policy.name}",
            "policy": {
                "id": policy.id,
                "name": policy.name,
                "path_pattern": policy.path_pattern,
                "file_extensions": policy.file_extensions,
                "max_file_size_mb": policy.max_file_size_mb,
                "should_index": policy.should_index,
                "priority": policy.priority,
                "description": policy.description
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update indexing policy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update indexing policy: {str(e)}")


@router.delete("/policies/{policy_id}")
async def delete_indexing_policy(policy_id: int, db: Session = Depends(get_db)):
    """Delete an indexing policy"""
    try:
        policy = db.query(IndexingPolicy).filter(IndexingPolicy.id == policy_id).first()
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")
        
        policy_name = policy.name
        db.delete(policy)
        db.commit()
        
        return {
            "success": True,
            "message": f"Deleted indexing policy: {policy_name}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete indexing policy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete indexing policy: {str(e)}")


@router.get("/stats")
async def get_filesystem_stats(db: Session = Depends(get_db)):
    """Get file system indexing statistics"""
    try:
        crawler = FileSystemCrawler(db)
        stats = crawler.get_indexing_stats()
        
        return {
            "stats": stats,
            "indexer_status": file_system_indexer.get_indexing_status(),
            "watcher_status": file_watcher.get_status()
        }
        
    except Exception as e:
        logger.error(f"Failed to get filesystem stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get filesystem stats: {str(e)}")


@router.post("/create-default-policies")
async def create_default_policies(db: Session = Depends(get_db)):
    """Create default indexing policies"""
    try:
        crawler = FileSystemCrawler(db)
        crawler.create_default_policies()
        
        return {
            "success": True,
            "message": "Default indexing policies created successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to create default policies: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create default policies: {str(e)}")


@router.post("/start-background-indexing")
async def start_background_indexing(
    path: str,
    scan_interval_seconds: int = 300
):
    """Start background indexing for a directory"""
    try:
        # Validate path
        if not Path(path).exists():
            raise HTTPException(status_code=400, detail=f"Path does not exist: {path}")
            
        if not Path(path).is_dir():
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {path}")
        
        await file_system_indexer.start_background_indexing(path, scan_interval_seconds)
        
        return {
            "success": True,
            "message": f"Started background indexing for {path}",
            "scan_interval_seconds": scan_interval_seconds
        }
        
    except Exception as e:
        logger.error(f"Failed to start background indexing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start background indexing: {str(e)}")


@router.post("/stop-background-indexing")
async def stop_background_indexing():
    """Stop background indexing"""
    try:
        file_system_indexer.stop_background_indexing()
        
        return {
            "success": True,
            "message": "Background indexing stopped"
        }
        
    except Exception as e:
        logger.error(f"Failed to stop background indexing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop background indexing: {str(e)}")


@router.get("/merkle-tree")
async def get_merkle_tree_visualization(
    root_path: Optional[str] = None,
    max_depth: int = 3,
    db: Session = Depends(get_db)
):
    """Get a visualization of the Merkle tree structure"""
    try:
        from app.core.database import FileSystemNode, MerkleSnapshot
        
        # Get the latest snapshot
        latest_snapshot = (
            db.query(MerkleSnapshot)
            .order_by(MerkleSnapshot.created_at.desc())
            .first()
        )
        
        if not latest_snapshot:
            return {
                "message": "No Merkle tree snapshots found",
                "tree": None
            }
        
        # Get nodes for the tree
        query = db.query(FileSystemNode)
        if root_path:
            query = query.filter(FileSystemNode.path.startswith(root_path))
        
        nodes = query.all()
        
        if not nodes:
            return {
                "message": "No nodes found for the specified path",
                "tree": None
            }
        
        # Build tree structure
        tree = _build_tree_structure(nodes, latest_snapshot.root_path, max_depth)
        
        return {
            "latest_snapshot": {
                "id": latest_snapshot.id,
                "root_path": latest_snapshot.root_path,
                "root_hash": latest_snapshot.root_hash,
                "total_files": latest_snapshot.total_files,
                "total_directories": latest_snapshot.total_directories,
                "created_at": latest_snapshot.created_at.isoformat(),
                "scan_duration": latest_snapshot.scan_duration_seconds
            },
            "tree": tree,
            "total_nodes": len(nodes)
        }
        
    except Exception as e:
        logger.error(f"Failed to get Merkle tree visualization: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Merkle tree visualization: {str(e)}")


def _build_tree_structure(nodes: List, root_path: str, max_depth: int) -> Dict:
    """Build a nested tree structure from flat node list"""
    from pathlib import Path
    
    # Create a mapping of path to node
    node_map = {node.path: node for node in nodes}
    
    # Find the root node
    root_node = node_map.get(root_path)
    if not root_node:
        return {}
    
    def build_node_tree(node_path: str, current_depth: int = 0) -> Dict:
        if current_depth > max_depth:
            return {"truncated": True}
        
        node = node_map.get(node_path)
        if not node:
            return {}
        
        node_info = {
            "path": node.path,
            "name": Path(node.path).name,
            "type": node.node_type,
            "hash": node.hash[:8] + "..." if len(node.hash) > 8 else node.hash,
            "size": node.size,
            "modified_time": node.modified_time,
            "should_index": node.should_index,
            "last_indexed": node.last_indexed.isoformat() if node.last_indexed else None
        }
        
        # Add children for directories
        if node.node_type == "directory":
            children = []
            for child_path in node_map:
                if (child_path != node_path and 
                    child_path.startswith(node_path) and 
                    child_path.count('/') == node_path.count('/') + 1):
                    child_tree = build_node_tree(child_path, current_depth + 1)
                    if child_tree:
                        children.append(child_tree)
            
            node_info["children"] = sorted(children, key=lambda x: (x.get("type", ""), x.get("name", "")))
            node_info["child_count"] = len(children)
        
        return node_info
    
    return build_node_tree(root_path)


@router.get("/merkle-snapshots")
async def get_merkle_snapshots(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get recent Merkle tree snapshots"""
    try:
        from app.core.database import MerkleSnapshot
        
        snapshots = (
            db.query(MerkleSnapshot)
            .order_by(MerkleSnapshot.created_at.desc())
            .limit(limit)
            .all()
        )
        
        return {
            "snapshots": [
                {
                    "id": snapshot.id,
                    "root_path": snapshot.root_path,
                    "root_hash": snapshot.root_hash,
                    "total_files": snapshot.total_files,
                    "total_directories": snapshot.total_directories,
                    "total_size_bytes": snapshot.total_size_bytes,
                    "total_size_mb": round(snapshot.total_size_bytes / (1024 * 1024), 2),
                    "scan_duration_seconds": snapshot.scan_duration_seconds,
                    "changes_detected": snapshot.changes_detected,
                    "files_indexed": snapshot.files_indexed,
                    "created_at": snapshot.created_at.isoformat()
                }
                for snapshot in snapshots
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get Merkle snapshots: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Merkle snapshots: {str(e)}")


@router.get("/node-details/{node_id}")
async def get_node_details(
    node_id: int,
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific node"""
    try:
        from app.core.database import FileSystemNode
        
        node = db.query(FileSystemNode).filter(FileSystemNode.id == node_id).first()
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        
        return {
            "id": node.id,
            "path": node.path,
            "hash": node.hash,
            "node_type": node.node_type,
            "size": node.size,
            "size_mb": round(node.size / (1024 * 1024), 2) if node.size > 0 else 0,
            "modified_time": node.modified_time,
            "permissions": oct(node.permissions) if node.permissions else None,
            "parent_path": node.parent_path,
            "children_hashes": node.children_hashes,
            "should_index": node.should_index,
            "last_indexed": node.last_indexed.isoformat() if node.last_indexed else None,
            "created_at": node.created_at.isoformat(),
            "updated_at": node.updated_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get node details: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get node details: {str(e)}")


class RemoveDirectoryIndexRequest(BaseModel):
    path: str
    remove_from_vector_store: bool = True


@router.delete("/remove-directory-index")
async def remove_directory_index(request: RemoveDirectoryIndexRequest, db: Session = Depends(get_db)):
    """Remove a directory index, its Merkle tree, and all associated data"""
    try:
        from app.core.database import FileSystemNode, MerkleSnapshot, Document, DocumentChunk
        from app.services.rag_pipeline import rag_pipeline
        
        directory_path = Path(request.path).resolve()
        path_str = str(directory_path)
        
        logger.info(f"Starting removal of directory index: {path_str}")
        
        # Get all documents that belong to this directory
        documents_to_remove = (
            db.query(Document)
            .filter(Document.file_path.like(f"{path_str}%"))
            .all()
        )
        
        removed_stats = {
            "documents_removed": 0,
            "chunks_removed": 0,
            "filesystem_nodes_removed": 0,
            "merkle_snapshots_removed": 0,
            "vector_store_cleanup": False
        }
        
        # Remove documents and their chunks from vector store and database
        if documents_to_remove:
            logger.info(f"Found {len(documents_to_remove)} documents to remove")
            
            for doc in documents_to_remove:
                try:
                    if request.remove_from_vector_store:
                        # Remove from vector store (Qdrant) and database
                        success = rag_pipeline.delete_document(doc.id)
                        if success:
                            logger.debug(f"Successfully removed document {doc.id} from vector store")
                        else:
                            logger.warning(f"Failed to remove document {doc.id} from vector store")
                    else:
                        # Only remove from database, keep vectors
                        chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
                        for chunk in chunks:
                            db.delete(chunk)
                        db.delete(doc)
                        
                    removed_stats["documents_removed"] += 1
                    
                except Exception as e:
                    logger.error(f"Failed to remove document {doc.id}: {e}")
            
            removed_stats["vector_store_cleanup"] = request.remove_from_vector_store
        
        # Remove filesystem nodes
        filesystem_nodes = (
            db.query(FileSystemNode)
            .filter(FileSystemNode.path.like(f"{path_str}%"))
            .all()
        )
        
        if filesystem_nodes:
            logger.info(f"Found {len(filesystem_nodes)} filesystem nodes to remove")
            
            for node in filesystem_nodes:
                db.delete(node)
                removed_stats["filesystem_nodes_removed"] += 1
        
        # Remove Merkle snapshots for this directory
        merkle_snapshots = (
            db.query(MerkleSnapshot)
            .filter(MerkleSnapshot.root_path == path_str)
            .all()
        )
        
        if merkle_snapshots:
            logger.info(f"Found {len(merkle_snapshots)} Merkle snapshots to remove")
            
            for snapshot in merkle_snapshots:
                db.delete(snapshot)
                removed_stats["merkle_snapshots_removed"] += 1
        
        # Commit all changes
        db.commit()
        
        logger.info("Directory index removal completed", **removed_stats)
        
        return {
            "success": True,
            "message": f"Successfully removed directory index for: {path_str}",
            "stats": removed_stats
        }
        
    except Exception as e:
        logger.error(f"Failed to remove directory index: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to remove directory index: {str(e)}")
