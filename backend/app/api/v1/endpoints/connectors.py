from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

from app.core.logging import get_logger
from app.services.connectors.manager import connector_manager

logger = get_logger(__name__)

router = APIRouter()


class ConnectorCreateRequest(BaseModel):
    name: str
    connector_type: str
    credentials: Dict[str, Any]
    settings: Dict[str, Any] = {}
    enabled: bool = True


class ConnectorUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    credentials: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None
    sync_interval_minutes: Optional[int] = None


class SyncRequest(BaseModel):
    incremental: bool = True


@router.get("/")
async def list_connectors():
    """List all configured connectors"""
    try:
        status = connector_manager.get_all_connector_status()
        return {"connectors": status}
    except Exception as e:
        logger.error(f"Failed to list connectors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_connector(request: ConnectorCreateRequest):
    """Create a new connector"""
    try:
        name = await connector_manager.add_connector(
            name=request.name,
            connector_type=request.connector_type,
            credentials=request.credentials,
            settings=request.settings,
            enabled=request.enabled
        )
        
        return {
            "success": True,
            "message": f"Connector '{name}' created successfully",
            "connector_name": name
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create connector: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{connector_name}")
async def get_connector(connector_name: str):
    """Get connector status and details"""
    try:
        status = connector_manager.get_connector_status(connector_name)
        if not status:
            raise HTTPException(status_code=404, detail="Connector not found")
        
        return {"connector": status}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get connector {connector_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{connector_name}")
async def delete_connector(connector_name: str):
    """Delete a connector"""
    try:
        success = await connector_manager.remove_connector(connector_name)
        if not success:
            raise HTTPException(status_code=404, detail="Connector not found")
        
        return {
            "success": True,
            "message": f"Connector '{connector_name}' deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete connector {connector_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{connector_name}/sync")
async def sync_connector(connector_name: str, request: SyncRequest):
    """Manually trigger sync for a connector"""
    try:
        result = await connector_manager.sync_connector(
            connector_name, 
            incremental=request.incremental
        )
        
        return {
            "success": result.success,
            "result": {
                "items_processed": result.items_processed,
                "items_added": result.items_added,
                "items_updated": result.items_updated,
                "items_failed": result.items_failed,
                "duration_seconds": result.duration_seconds,
                "errors": result.errors
            }
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to sync connector {connector_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-all")
async def sync_all_connectors(request: SyncRequest):
    """Sync all enabled connectors"""
    try:
        results = await connector_manager.sync_all_connectors(
            incremental=request.incremental
        )
        
        return {
            "success": True,
            "results": {
                name: {
                    "success": result.success,
                    "items_processed": result.items_processed,
                    "items_added": result.items_added,
                    "items_updated": result.items_updated,
                    "items_failed": result.items_failed,
                    "duration_seconds": result.duration_seconds,
                    "errors": result.errors
                }
                for name, result in results.items()
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to sync all connectors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{connector_name}/history")
async def get_sync_history(connector_name: str, limit: int = 10):
    """Get sync history for a connector"""
    try:
        history = connector_manager.get_sync_history(connector_name, limit)
        return {"history": history}
        
    except Exception as e:
        logger.error(f"Failed to get sync history for {connector_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/types/supported")
async def get_supported_connector_types():
    """Get list of supported connector types"""
    return {
        "supported_types": [
            {
                "type": "github",
                "name": "GitHub",
                "description": "Index code repositories from GitHub",
                "required_credentials": ["token"],
                "optional_settings": [
                    "repositories",
                    "file_extensions", 
                    "ignored_patterns",
                    "max_file_size_kb"
                ]
            },
            {
                "type": "notion",
                "name": "Notion",
                "description": "Index pages and databases from Notion workspace",
                "required_credentials": ["token"],
                "optional_settings": [
                    "sync_pages",
                    "sync_databases",
                    "max_database_entries"
                ]
            },
            {
                "type": "gmail",
                "name": "Gmail",
                "description": "Index emails from Gmail account",
                "required_credentials": ["access_token"],
                "optional_settings": [
                    "max_emails_per_sync",
                    "days_back",
                    "include_sent",
                    "include_drafts"
                ]
            }
            # Add other connector types as they're implemented
        ]
    }