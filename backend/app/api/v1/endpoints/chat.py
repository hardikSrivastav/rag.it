from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any
import json
import asyncio

from app.core.logging import get_logger
from app.services.rag_pipeline import rag_pipeline
from app.schemas.chat import ChatRequest, ChatResponse

logger = get_logger(__name__)

router = APIRouter()

@router.post("/query", response_model=ChatResponse)
async def chat_query(request: ChatRequest):
    """Send a query to the RAG system and get a response"""
    try:
        # Validate query
        if not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        logger.info("Processing chat query", 
                   query=request.query,
                   top_k=request.top_k,
                   session_id=request.session_id)
        
        # Process query using RAG pipeline
        response = await rag_pipeline.query(
            query=request.query,
            top_k=request.top_k
        )
        
        return ChatResponse(
            success=True,
            response=response,
            query=request.query,
            session_id=request.session_id,
            sources=[]  # TODO: Add source information
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to process chat query", 
                    query=request.query,
                    error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to process query: {str(e)}")

@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Send a query to the RAG system and get a streaming response"""
    try:
        # Validate query
        if not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        logger.info("Processing streaming chat query", 
                   query=request.query,
                   top_k=request.top_k,
                   session_id=request.session_id)
        
        async def generate_stream():
            """Generate streaming response"""
            try:
                # Send initial metadata
                metadata = {
                    "type": "metadata",
                    "query": request.query,
                    "session_id": request.session_id,
                    "top_k": request.top_k
                }
                yield f"data: {json.dumps(metadata)}\n\n"
                
                # Stream the response
                async for chunk in rag_pipeline.query_streaming(
                    query=request.query,
                    top_k=request.top_k
                ):
                    response_chunk = {
                        "type": "chunk",
                        "content": chunk
                    }
                    yield f"data: {json.dumps(response_chunk)}\n\n"
                
                # Send completion signal
                completion = {
                    "type": "completion",
                    "status": "completed"
                }
                yield f"data: {json.dumps(completion)}\n\n"
                
            except Exception as e:
                logger.error("Error in streaming response", error=str(e))
                error_response = {
                    "type": "error",
                    "error": str(e)
                }
                yield f"data: {json.dumps(error_response)}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Methods": "*"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to setup streaming chat", 
                    query=request.query,
                    error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to setup streaming: {str(e)}")

@router.get("/sessions")
async def get_chat_sessions():
    """Get list of chat sessions"""
    # TODO: Implement chat session management
    return {"sessions": [], "message": "Chat session management not yet implemented"}

@router.get("/sessions/{session_id}/history")
async def get_chat_history(session_id: str):
    """Get chat history for a specific session"""
    # TODO: Implement chat history retrieval
    return {"session_id": session_id, "messages": [], "message": "Chat history not yet implemented"}

@router.delete("/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    """Delete a chat session and its history"""
    # TODO: Implement chat session deletion
    return {"success": True, "message": "Chat session deletion not yet implemented"} 