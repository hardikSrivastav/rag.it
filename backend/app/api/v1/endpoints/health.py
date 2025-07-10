from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from app.core.logging import get_logger
from app.services.rag_pipeline import rag_pipeline

logger = get_logger(__name__)

router = APIRouter()

@router.get("/")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "service": "rag-system",
        "version": "1.0.0"
    }

@router.get("/detailed")
async def detailed_health_check():
    """Detailed health check including all components"""
    try:
        # Get health status of all components
        health_status = rag_pipeline.health_check()
        
        # Determine overall health
        all_healthy = all(status for status in health_status.values())
        
        response = {
            "status": "healthy" if all_healthy else "unhealthy",
            "service": "rag-system",
            "version": "1.0.0",
            "components": health_status,
            "timestamp": logger.info("Health check completed")
        }
        
        if not all_healthy:
            logger.warning("Some components are unhealthy", health_status=health_status)
        
        return response
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "service": "rag-system",
            "version": "1.0.0",
            "error": str(e)
        }

@router.get("/components/vector-store")
async def vector_store_health():
    """Check vector store health"""
    try:
        health = rag_pipeline.vector_store.health_check()
        collection_info = rag_pipeline.vector_store.get_collection_info()
        
        return {
            "status": "healthy" if health else "unhealthy",
            "component": "vector-store",
            "collection_info": collection_info
        }
        
    except Exception as e:
        logger.error("Vector store health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "component": "vector-store",
            "error": str(e)
        }

@router.get("/components/llm-providers")
async def llm_providers_health():
    """Check LLM providers health"""
    try:
        health_status = rag_pipeline.llm_manager.health_check()
        available_providers = rag_pipeline.llm_manager.get_available_providers()
        
        return {
            "status": "healthy" if available_providers else "unhealthy",
            "component": "llm-providers",
            "providers": health_status,
            "available_providers": available_providers
        }
        
    except Exception as e:
        logger.error("LLM providers health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "component": "llm-providers",
            "error": str(e)
        } 