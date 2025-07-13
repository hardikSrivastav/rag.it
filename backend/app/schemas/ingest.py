from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

class IngestResponse(BaseModel):
    """Response model for file ingestion"""
    success: bool
    message: str
    document_id: int
    filename: str
    status: str
    chunk_count: int
    processing_time: float

class PushDataRequest(BaseModel):
    """Request model for pushing data from other tools"""
    source_tool: str = Field(..., description="Name of the source tool")
    content: str = Field(..., description="Text content to be ingested")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class PushDataResponse(BaseModel):
    """Response model for data push"""
    success: bool
    message: str
    document_id: int
    filename: str
    status: str
    chunk_count: int
    processing_time: float

class DocumentStatus(BaseModel):
    """Document status model"""
    document_id: int
    filename: str
    status: str
    chunk_count: int
    created_at: datetime
    indexed_at: Optional[datetime] = None
    error_message: Optional[str] = None

class DeletionType(str, Enum):
    """Types of deletion operations"""
    SOURCE = "source"           # Delete all data from a source (e.g., all GitHub)
    REPOSITORY = "repository"   # Delete specific repo/workspace
    DOCUMENT = "document"       # Delete specific documents
    CHUNK = "chunk"            # Delete specific chunks

class DeleteRequest(BaseModel):
    """Request model for deleting indexed sources"""
    deletion_type: DeletionType
    target_filters: Dict[str, Any] = Field(..., description="Filters to target specific data")
    dry_run: bool = Field(default=True, description="Preview deletion without executing")
    confirmation_token: Optional[str] = Field(None, description="Required for actual deletion")
    backup_before_delete: bool = Field(default=True, description="Create backup before deletion")
    force_delete: bool = Field(default=False, description="Skip safety checks (dangerous)")

class DeletePreviewItem(BaseModel):
    """Preview item that would be deleted"""
    document_id: int
    filename: str
    source_tool: str
    chunk_count: int
    file_size: Optional[int]
    metadata: Dict[str, Any]

class DeletePreviewResponse(BaseModel):
    """Response model for deletion preview (dry-run)"""
    success: bool
    message: str
    deletion_type: DeletionType
    target_filters: Dict[str, Any]
    items_to_delete: List[DeletePreviewItem]
    total_documents: int
    total_chunks: int
    estimated_vector_deletions: int
    confirmation_token: str
    safety_warnings: List[str]

class DeleteResponse(BaseModel):
    """Response model for actual deletion"""
    success: bool
    message: str
    deletion_type: DeletionType
    target_filters: Dict[str, Any]
    documents_deleted: int
    chunks_deleted: int
    vectors_deleted: int
    backup_id: Optional[str]
    duration_seconds: float
    errors: List[str]

class DeletionBackupMetadata(BaseModel):
    """Metadata for deletion backup"""
    backup_id: str
    deletion_type: DeletionType
    target_filters: Dict[str, Any]
    deleted_documents: List[Dict[str, Any]]
    deleted_chunks: List[Dict[str, Any]]
    created_at: datetime
    can_restore: bool 