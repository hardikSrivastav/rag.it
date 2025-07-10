from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.database import get_db, Document as DocumentModel
from app.core.logging import get_logger
from app.schemas.documents import DocumentListResponse, DocumentDetail

logger = get_logger(__name__)

router = APIRouter()

@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    skip: int = Query(default=0, description="Number of documents to skip"),
    limit: int = Query(default=50, description="Maximum number of documents to return"),
    status: Optional[str] = Query(default=None, description="Filter by document status"),
    source_tool: Optional[str] = Query(default=None, description="Filter by source tool")
):
    """List all indexed documents with optional filtering"""
    try:
        db = next(get_db())
        
        # Build query
        query = db.query(DocumentModel)
        
        # Apply filters
        if status:
            query = query.filter(DocumentModel.status == status)
        
        if source_tool:
            query = query.filter(DocumentModel.source_tool == source_tool)
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination
        documents = query.offset(skip).limit(limit).all()
        
        # Convert to response format
        document_list = []
        for doc in documents:
            document_list.append(DocumentDetail(
                document_id=doc.id,
                filename=doc.filename,
                source_tool=doc.source_tool,
                content_type=doc.content_type,
                file_size=doc.file_size,
                status=doc.status,
                chunk_count=doc.chunk_count,
                created_at=doc.created_at,
                indexed_at=doc.indexed_at,
                error_message=doc.error_message
            ))
        
        db.close()
        
        logger.info("Listed documents", 
                   count=len(documents),
                   total_count=total_count,
                   skip=skip,
                   limit=limit)
        
        return DocumentListResponse(
            documents=document_list,
            total_count=total_count,
            skip=skip,
            limit=limit
        )
        
    except Exception as e:
        logger.error("Failed to list documents", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")

@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(document_id: int):
    """Get detailed information about a specific document"""
    try:
        db = next(get_db())
        
        document = db.query(DocumentModel).filter(DocumentModel.id == document_id).first()
        
        if not document:
            db.close()
            raise HTTPException(status_code=404, detail="Document not found")
        
        document_detail = DocumentDetail(
            document_id=document.id,
            filename=document.filename,
            source_tool=document.source_tool,
            content_type=document.content_type,
            file_size=document.file_size,
            status=document.status,
            chunk_count=document.chunk_count,
            created_at=document.created_at,
            indexed_at=document.indexed_at,
            error_message=document.error_message
        )
        
        db.close()
        
        logger.info("Retrieved document details", document_id=document_id)
        
        return document_detail
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get document", document_id=document_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")

@router.get("/stats/summary")
async def get_document_stats():
    """Get summary statistics about indexed documents"""
    try:
        db = next(get_db())
        
        # Get basic counts
        total_documents = db.query(DocumentModel).count()
        indexed_documents = db.query(DocumentModel).filter(DocumentModel.status == "indexed").count()
        processing_documents = db.query(DocumentModel).filter(DocumentModel.status == "processing").count()
        failed_documents = db.query(DocumentModel).filter(DocumentModel.status == "failed").count()
        
        # Get counts by source tool
        source_tools = db.query(DocumentModel.source_tool, 
                               db.func.count(DocumentModel.id)).group_by(DocumentModel.source_tool).all()
        
        # Get total chunks
        total_chunks = db.query(db.func.sum(DocumentModel.chunk_count)).scalar() or 0
        
        db.close()
        
        stats = {
            "total_documents": total_documents,
            "indexed_documents": indexed_documents,
            "processing_documents": processing_documents,
            "failed_documents": failed_documents,
            "total_chunks": total_chunks,
            "source_tools": {tool: count for tool, count in source_tools}
        }
        
        logger.info("Retrieved document statistics", stats=stats)
        
        return stats
        
    except Exception as e:
        logger.error("Failed to get document stats", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@router.post("/{document_id}/reindex")
async def reindex_document(document_id: int):
    """Reindex a specific document"""
    # TODO: Implement document reindexing
    return {"success": True, "message": "Document reindexing not yet implemented"}

@router.get("/search/content")
async def search_document_content(
    query: str = Query(..., description="Search query"),
    limit: int = Query(default=10, description="Maximum number of results")
):
    """Search through document content using vector similarity"""
    # TODO: Implement content search through vector store
    return {"query": query, "results": [], "message": "Content search not yet implemented"} 