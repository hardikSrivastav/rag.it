import asyncio
import uuid
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.core.database import (
    get_db, Document, DocumentChunk, 
    DeletionLog, DeletionBackup
)
from app.core.vector_store import vector_store
from app.core.logging import get_logger
from app.schemas.ingest import (
    DeleteRequest, DeletePreviewResponse, DeleteResponse,
    DeletePreviewItem, DeletionBackupMetadata, DeletionType
)

logger = get_logger(__name__)


class DeletionService:
    """Service for safely deleting indexed sources with granular control"""
    
    def __init__(self):
        self.confirmation_tokens = {}  # In-memory token storage
        self.token_expiry_minutes = 10  # Tokens expire after 10 minutes
    
    async def preview_deletion(self, request: DeleteRequest) -> DeletePreviewResponse:
        """Preview what would be deleted without actually deleting"""
        try:
            db = next(get_db())
            
            # Build query based on deletion type and filters
            documents_query = self._build_deletion_query(db, request)
            documents = documents_query.all()
            
            # Calculate totals
            total_documents = len(documents)
            total_chunks = sum(doc.chunk_count for doc in documents)
            
            # Get chunk details for vector deletion estimation
            chunk_ids = []
            if documents:
                doc_ids = [doc.id for doc in documents]
                chunks = db.query(DocumentChunk).filter(
                    DocumentChunk.document_id.in_(doc_ids)
                ).all()
                chunk_ids = [chunk.vector_id for chunk in chunks if chunk.vector_id]
            
            # Create preview items
            preview_items = []
            for doc in documents:
                preview_items.append(DeletePreviewItem(
                    document_id=doc.id,
                    filename=doc.filename,
                    source_tool=doc.source_tool,
                    chunk_count=doc.chunk_count,
                    file_size=doc.file_size,
                    metadata=doc.metadata_json or {}
                ))
            
            # Generate confirmation token
            confirmation_token = str(uuid.uuid4())
            self.confirmation_tokens[confirmation_token] = {
                "request": request,
                "expires_at": datetime.utcnow() + timedelta(minutes=self.token_expiry_minutes),
                "preview_data": {
                    "document_ids": [doc.id for doc in documents],
                    "chunk_vector_ids": chunk_ids
                }
            }
            
            # Generate safety warnings
            safety_warnings = self._generate_safety_warnings(request, total_documents, total_chunks)
            
            db.close()
            
            return DeletePreviewResponse(
                success=True,
                message=f"Preview: {total_documents} documents and {total_chunks} chunks would be deleted",
                deletion_type=request.deletion_type,
                target_filters=request.target_filters,
                items_to_delete=preview_items,
                total_documents=total_documents,
                total_chunks=total_chunks,
                estimated_vector_deletions=len(chunk_ids),
                confirmation_token=confirmation_token,
                safety_warnings=safety_warnings
            )
            
        except Exception as e:
            logger.error("Failed to preview deletion", error=str(e))
            return DeletePreviewResponse(
                success=False,
                message=f"Failed to preview deletion: {str(e)}",
                deletion_type=request.deletion_type,
                target_filters=request.target_filters,
                items_to_delete=[],
                total_documents=0,
                total_chunks=0,
                estimated_vector_deletions=0,
                confirmation_token="",
                safety_warnings=[]
            )
    
    async def execute_deletion(self, request: DeleteRequest) -> DeleteResponse:
        """Execute actual deletion with safety checks"""
        start_time = datetime.utcnow()
        
        try:
            # Validate confirmation token
            if not request.force_delete and request.dry_run:
                return DeleteResponse(
                    success=False,
                    message="Cannot execute deletion in dry_run mode. Set dry_run=False and provide confirmation_token.",
                    deletion_type=request.deletion_type,
                    target_filters=request.target_filters,
                    documents_deleted=0,
                    chunks_deleted=0,
                    vectors_deleted=0,
                    backup_id=None,
                    duration_seconds=0,
                    errors=["Dry run mode enabled"]
                )
            
            if not request.force_delete:
                token_data = self.confirmation_tokens.get(request.confirmation_token)
                if not token_data:
                    return DeleteResponse(
                        success=False,
                        message="Invalid or expired confirmation token",
                        deletion_type=request.deletion_type,
                        target_filters=request.target_filters,
                        documents_deleted=0,
                        chunks_deleted=0,
                        vectors_deleted=0,
                        backup_id=None,
                        duration_seconds=0,
                        errors=["Invalid confirmation token"]
                    )
                
                if datetime.utcnow() > token_data["expires_at"]:
                    del self.confirmation_tokens[request.confirmation_token]
                    return DeleteResponse(
                        success=False,
                        message="Confirmation token has expired",
                        deletion_type=request.deletion_type,
                        target_filters=request.target_filters,
                        documents_deleted=0,
                        chunks_deleted=0,
                        vectors_deleted=0,
                        backup_id=None,
                        duration_seconds=0,
                        errors=["Token expired"]
                    )
            
            db = next(get_db())
            backup_id = None
            errors = []
            
            try:
                # Get documents to delete
                documents_query = self._build_deletion_query(db, request)
                documents = documents_query.all()
                
                if not documents:
                    return DeleteResponse(
                        success=True,
                        message="No documents found matching the criteria",
                        deletion_type=request.deletion_type,
                        target_filters=request.target_filters,
                        documents_deleted=0,
                        chunks_deleted=0,
                        vectors_deleted=0,
                        backup_id=None,
                        duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                        errors=[]
                    )
                
                # Create backup if requested
                if request.backup_before_delete:
                    backup_id = await self._create_backup(db, documents, request)
                
                # Get chunks to delete
                doc_ids = [doc.id for doc in documents]
                chunks = db.query(DocumentChunk).filter(
                    DocumentChunk.document_id.in_(doc_ids)
                ).all()
                
                # Delete from vector store first
                vector_ids = [chunk.vector_id for chunk in chunks if chunk.vector_id]
                vectors_deleted = 0
                if vector_ids:
                    try:
                        success = vector_store.delete_vectors(vector_ids)
                        if success:
                            vectors_deleted = len(vector_ids)
                        else:
                            errors.append("Failed to delete some vectors from vector store")
                    except Exception as e:
                        errors.append(f"Vector store deletion error: {str(e)}")
                
                # Delete chunks from database
                chunks_deleted = 0
                for chunk in chunks:
                    try:
                        db.delete(chunk)
                        chunks_deleted += 1
                    except Exception as e:
                        errors.append(f"Failed to delete chunk {chunk.id}: {str(e)}")
                
                # Delete documents from database
                documents_deleted = 0
                for doc in documents:
                    try:
                        db.delete(doc)
                        documents_deleted += 1
                    except Exception as e:
                        errors.append(f"Failed to delete document {doc.id}: {str(e)}")
                
                # Log the deletion
                deletion_log = DeletionLog(
                    deletion_type=request.deletion_type.value,
                    target_filters=request.target_filters,
                    documents_deleted=documents_deleted,
                    chunks_deleted=chunks_deleted,
                    vectors_deleted=vectors_deleted,
                    backup_id=backup_id,
                    executed_by="system",  # Could be enhanced with user tracking
                    executed_at=datetime.utcnow()
                )
                db.add(deletion_log)
                
                # Commit all changes
                db.commit()
                
                # Clean up confirmation token
                if request.confirmation_token in self.confirmation_tokens:
                    del self.confirmation_tokens[request.confirmation_token]
                
                duration = (datetime.utcnow() - start_time).total_seconds()
                
                logger.info("Deletion completed successfully",
                           deletion_type=request.deletion_type.value,
                           documents_deleted=documents_deleted,
                           chunks_deleted=chunks_deleted,
                           vectors_deleted=vectors_deleted,
                           duration=duration)
                
                return DeleteResponse(
                    success=len(errors) == 0,
                    message=f"Successfully deleted {documents_deleted} documents and {chunks_deleted} chunks",
                    deletion_type=request.deletion_type,
                    target_filters=request.target_filters,
                    documents_deleted=documents_deleted,
                    chunks_deleted=chunks_deleted,
                    vectors_deleted=vectors_deleted,
                    backup_id=backup_id,
                    duration_seconds=duration,
                    errors=errors
                )
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error("Deletion execution failed", error=str(e))
            return DeleteResponse(
                success=False,
                message=f"Deletion failed: {str(e)}",
                deletion_type=request.deletion_type,
                target_filters=request.target_filters,
                documents_deleted=0,
                chunks_deleted=0,
                vectors_deleted=0,
                backup_id=None,
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                errors=[str(e)]
            )
    
    def _build_deletion_query(self, db: Session, request: DeleteRequest):
        """Build SQLAlchemy query based on deletion request"""
        query = db.query(Document)
        filters = request.target_filters
        
        # Apply filters based on deletion type
        if request.deletion_type == DeletionType.SOURCE:
            if "source_tool" in filters:
                query = query.filter(Document.source_tool == filters["source_tool"])
        
        elif request.deletion_type == DeletionType.REPOSITORY:
            if "source_tool" in filters:
                query = query.filter(Document.source_tool == filters["source_tool"])
            if "repository" in filters:
                # For GitHub, repository info is in metadata_json
                query = query.filter(Document.metadata_json.contains({"repository": filters["repository"]}))
        
        elif request.deletion_type == DeletionType.DOCUMENT:
            if "document_ids" in filters:
                query = query.filter(Document.id.in_(filters["document_ids"]))
            if "filename" in filters:
                query = query.filter(Document.filename.like(f"%{filters['filename']}%"))
        
        # Additional common filters
        if "file_type" in filters:
            query = query.filter(Document.metadata_json.contains({"file_type": filters["file_type"]}))
        
        if "status" in filters:
            query = query.filter(Document.status == filters["status"])
        
        if "created_after" in filters:
            query = query.filter(Document.created_at >= filters["created_after"])
        
        if "created_before" in filters:
            query = query.filter(Document.created_at <= filters["created_before"])
        
        return query
    
    def _generate_safety_warnings(self, request: DeleteRequest, doc_count: int, chunk_count: int) -> List[str]:
        """Generate safety warnings based on deletion scope"""
        warnings = []
        
        if request.deletion_type == DeletionType.SOURCE:
            warnings.append(f"⚠️  SOURCE-LEVEL DELETION: This will delete ALL data from {request.target_filters.get('source_tool', 'unknown')} source")
        
        if doc_count > 100:
            warnings.append(f"⚠️  LARGE DELETION: {doc_count} documents will be deleted")
        
        if chunk_count > 1000:
            warnings.append(f"⚠️  MASSIVE CHUNK DELETION: {chunk_count} chunks will be deleted")
        
        if request.target_filters.get("source_tool") == "manual_upload":
            warnings.append("⚠️  MANUAL UPLOADS: This includes manually uploaded files that may be hard to recover")
        
        if not request.backup_before_delete:
            warnings.append("⚠️  NO BACKUP: Backup is disabled - deletion will be irreversible")
        
        return warnings
    
    async def _create_backup(self, db: Session, documents: List[Document], request: DeleteRequest) -> str:
        """Create backup metadata for potential restoration"""
        backup_id = str(uuid.uuid4())
        
        # Serialize document and chunk data
        doc_data = []
        for doc in documents:
            doc_data.append({
                "id": doc.id,
                "filename": doc.filename,
                "file_path": doc.file_path,
                "source_tool": doc.source_tool,
                "content_type": doc.content_type,
                "file_size": doc.file_size,
                "status": doc.status,
                "metadata_json": doc.metadata_json,
                "chunk_count": doc.chunk_count,
                "created_at": doc.created_at.isoformat(),
                "indexed_at": doc.indexed_at.isoformat() if doc.indexed_at else None
            })
        
        # Get chunk data
        doc_ids = [doc.id for doc in documents]
        chunks = db.query(DocumentChunk).filter(
            DocumentChunk.document_id.in_(doc_ids)
        ).all()
        
        chunk_data = []
        for chunk in chunks:
            chunk_data.append({
                "id": chunk.id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "chunk_text": chunk.chunk_text,
                "chunk_hash": chunk.chunk_hash,
                "vector_id": chunk.vector_id,
                "metadata_json": chunk.metadata_json,
                "created_at": chunk.created_at.isoformat()
            })
        
        # Store backup
        backup = DeletionBackup(
            backup_id=backup_id,
            deletion_type=request.deletion_type.value,
            target_filters=request.target_filters,
            document_count=len(documents),
            chunk_count=len(chunks),
            backup_data={
                "documents": doc_data,
                "chunks": chunk_data
            },
            created_at=datetime.utcnow(),
            can_restore=True
        )
        
        db.add(backup)
        db.commit()
        
        logger.info("Created deletion backup", backup_id=backup_id, 
                   documents=len(documents), chunks=len(chunks))
        
        return backup_id


# Global instance
deletion_service = DeletionService()