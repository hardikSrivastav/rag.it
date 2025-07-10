from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ChatRequest(BaseModel):
    """Request model for chat queries"""
    query: str = Field(..., description="The user's query")
    top_k: int = Field(default=5, description="Number of relevant chunks to retrieve")
    session_id: Optional[str] = Field(None, description="Chat session ID")

class ChatResponse(BaseModel):
    """Response model for chat queries"""
    success: bool
    response: str
    query: str
    session_id: Optional[str] = None
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Source documents used")

class ChatMessage(BaseModel):
    """Individual chat message model"""
    role: str = Field(..., description="Message role: user, assistant, system")
    content: str = Field(..., description="Message content")
    timestamp: str = Field(..., description="Message timestamp")
    sources: Optional[List[Dict[str, Any]]] = Field(None, description="Source documents")

class ChatSession(BaseModel):
    """Chat session model"""
    session_id: str
    created_at: str
    updated_at: str
    message_count: int

class ChatHistory(BaseModel):
    """Chat history model"""
    session_id: str
    messages: List[ChatMessage]
    total_messages: int 