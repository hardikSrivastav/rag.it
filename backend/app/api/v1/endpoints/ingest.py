from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import os
import shutil
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.services.rag_pipeline import rag_pipeline
from app.schemas.ingest import IngestResponse, PushDataRequest, PushDataResponse

logger = get_logger(__name__)

router = APIRouter()

@router.post("/upload", response_model=IngestResponse)
async def upload_file(
    file: UploadFile = File(...),
    source_tool: str = Form("manual_upload"),
    metadata: Optional[str] = Form(None)
):
    """Upload and ingest a file into the RAG system"""
    try:
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"File type {file_extension} not supported. Allowed types: {settings.ALLOWED_EXTENSIONS}"
            )
        
        # Check file size
        file_size = 0
        content = await file.read()
        file_size = len(content)
        
        if file_size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400, 
                detail=f"File size {file_size} exceeds maximum allowed size {settings.MAX_FILE_SIZE}"
            )
        
        # Save file to upload directory
        file_path = Path(settings.UPLOAD_DIR) / file.filename
        
        # Handle duplicate filenames
        counter = 1
        original_stem = file_path.stem
        while file_path.exists():
            file_path = Path(settings.UPLOAD_DIR) / f"{original_stem}_{counter}{file_extension}"
            counter += 1
        
        # Write file to disk
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        logger.info("File uploaded successfully", 
                   filename=file.filename,
                   file_path=str(file_path),
                   file_size=file_size)
        
        # Parse metadata if provided
        file_metadata = {}
        if metadata:
            try:
                import json
                file_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                logger.warning("Invalid metadata JSON provided", metadata=metadata)
        
        # Add upload metadata
        file_metadata.update({
            "original_filename": file.filename,
            "file_size": file_size,
            "content_type": file.content_type
        })
        
        # Ingest file using RAG pipeline
        result = await rag_pipeline.ingest_file(
            file_path=str(file_path),
            source_tool=source_tool,
            metadata=file_metadata
        )
        
        return IngestResponse(
            success=True,
            message="File uploaded and ingested successfully",
            document_id=result["document_id"],
            filename=result["filename"],
            status=result["status"],
            chunk_count=result["chunk_count"],
            processing_time=result["processing_time"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to upload and ingest file", 
                    filename=file.filename if file else "unknown",
                    error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")

@router.post("/push", response_model=PushDataResponse)
async def push_data(request: PushDataRequest):
    """Push data directly from other tools into the RAG system"""
    try:
        # Validate request
        if not request.content.strip():
            raise HTTPException(status_code=400, detail="Content cannot be empty")
        
        # Prepare metadata
        metadata = request.metadata or {}
        metadata.update({
            "source_tool": request.source_tool,
            "content_length": len(request.content)
        })
        
        logger.info("Processing push data request", 
                   source_tool=request.source_tool,
                   content_length=len(request.content))
        
        # Ingest text using RAG pipeline
        result = await rag_pipeline.ingest_text(
            text=request.content,
            metadata=metadata
        )
        
        return PushDataResponse(
            success=True,
            message="Data ingested successfully",
            document_id=result["document_id"],
            filename=result["filename"],
            status=result["status"],
            chunk_count=result["chunk_count"],
            processing_time=result["processing_time"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to push data", 
                    source_tool=request.source_tool,
                    error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to process data: {str(e)}")

@router.get("/status/{document_id}")
async def get_ingestion_status(document_id: int):
    """Get the ingestion status of a document"""
    try:
        status = rag_pipeline.get_document_status(document_id)
        
        if not status:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get document status", 
                    document_id=document_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@router.delete("/document/{document_id}")
async def delete_document(document_id: int):
    """Delete a document and all its chunks"""
    try:
        success = rag_pipeline.delete_document(document_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Document not found or could not be deleted")
        
        return {"success": True, "message": "Document deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete document", 
                    document_id=document_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}") 