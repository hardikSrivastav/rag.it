from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class DocumentDetail(BaseModel):
    """Detailed document model"""
    document_id: int
    filename: str
    source_tool: str
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    status: str
    chunk_count: int
    created_at: datetime
    indexed_at: Optional[datetime] = None
    error_message: Optional[str] = None

class DocumentListResponse(BaseModel):
    """Response model for document listing"""
    documents: List[DocumentDetail]
    total_count: int
    skip: int
    limit: int

class DocumentStats(BaseModel):
    """Document statistics model"""
    total_documents: int
    indexed_documents: int
    processing_documents: int
    failed_documents: int
    total_chunks: int
    source_tools: dict 