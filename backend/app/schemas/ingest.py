from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime

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