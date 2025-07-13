from fastapi import APIRouter, HTTPException, Depends
from typing import List

from app.services.deletion_service import deletion_service
from app.schemas.ingest import DeleteRequest, DeletePreviewResponse, DeleteResponse
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/preview", response_model=DeletePreviewResponse)
async def preview_deletion(request: DeleteRequest):
    """Preview what would be deleted (dry-run mode)"""
    try:
        # Force dry_run for preview endpoint
        request.dry_run = True
        result = await deletion_service.preview_deletion(request)
        
        logger.info("Deletion preview completed",
                   deletion_type=request.deletion_type.value,
                   total_documents=result.total_documents,
                   total_chunks=result.total_chunks)
        
        return result
        
    except Exception as e:
        logger.error("Failed to preview deletion", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to preview deletion: {str(e)}")


@router.post("/execute", response_model=DeleteResponse)
async def execute_deletion(request: DeleteRequest):
    """Execute actual deletion with confirmation token"""
    try:
        if request.dry_run:
            raise HTTPException(
                status_code=400, 
                detail="Cannot execute deletion in dry_run mode. Use /preview endpoint first, then set dry_run=False with confirmation_token."
            )
        
        result = await deletion_service.execute_deletion(request)
        
        if result.success:
            logger.info("Deletion executed successfully",
                       deletion_type=request.deletion_type.value,
                       documents_deleted=result.documents_deleted,
                       chunks_deleted=result.chunks_deleted)
        else:
            logger.warning("Deletion completed with errors",
                          deletion_type=request.deletion_type.value,
                          errors=result.errors)
        
        return result
        
    except Exception as e:
        logger.error("Failed to execute deletion", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to execute deletion: {str(e)}")


@router.get("/history")
async def get_deletion_history(limit: int = 50):
    """Get history of deletion operations"""
    try:
        from app.core.database import get_db, DeletionLog
        
        db = next(get_db())
        try:
            logs = (db.query(DeletionLog)
                   .order_by(DeletionLog.executed_at.desc())
                   .limit(limit)
                   .all())
            
            history = []
            for log in logs:
                history.append({
                    "id": log.id,
                    "deletion_type": log.deletion_type,
                    "target_filters": log.target_filters,
                    "documents_deleted": log.documents_deleted,
                    "chunks_deleted": log.chunks_deleted,
                    "vectors_deleted": log.vectors_deleted,
                    "backup_id": log.backup_id,
                    "executed_by": log.executed_by,
                    "executed_at": log.executed_at.isoformat() if log.executed_at else None,
                    "duration_seconds": log.duration_seconds,
                    "success": log.success,
                    "error_message": log.error_message
                })
            
            return {"history": history, "total_count": len(history)}
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Failed to get deletion history", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get deletion history: {str(e)}")


@router.get("/backups")
async def list_deletion_backups():
    """List available deletion backups"""
    try:
        from app.core.database import get_db, DeletionBackup
        
        db = next(get_db())
        try:
            backups = (db.query(DeletionBackup)
                      .filter(DeletionBackup.can_restore == True)
                      .order_by(DeletionBackup.created_at.desc())
                      .all())
            
            backup_list = []
            for backup in backups:
                backup_list.append({
                    "backup_id": backup.backup_id,
                    "deletion_type": backup.deletion_type,
                    "target_filters": backup.target_filters,
                    "document_count": backup.document_count,
                    "chunk_count": backup.chunk_count,
                    "created_at": backup.created_at.isoformat(),
                    "can_restore": backup.can_restore,
                    "restored_at": backup.restored_at.isoformat() if backup.restored_at else None
                })
            
            return {"backups": backup_list, "total_count": len(backup_list)}
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Failed to list deletion backups", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list deletion backups: {str(e)}")


@router.get("/stats")
async def get_deletion_stats():
    """Get deletion statistics"""
    try:
        from app.core.database import get_db, DeletionLog
        from sqlalchemy import func
        
        db = next(get_db())
        try:
            # Get total deletions
            total_operations = db.query(DeletionLog).count()
            
            # Get deletions by type
            deletions_by_type = db.query(
                DeletionLog.deletion_type,
                func.count(DeletionLog.id).label('count'),
                func.sum(DeletionLog.documents_deleted).label('total_docs'),
                func.sum(DeletionLog.chunks_deleted).label('total_chunks')
            ).group_by(DeletionLog.deletion_type).all()
            
            # Get recent activity (last 30 days)
            from datetime import datetime, timedelta
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_operations = db.query(DeletionLog).filter(
                DeletionLog.executed_at >= thirty_days_ago
            ).count()
            
            # Format results
            type_stats = {}
            for deletion_type, count, total_docs, total_chunks in deletions_by_type:
                type_stats[deletion_type] = {
                    "operations": count,
                    "documents_deleted": total_docs or 0,
                    "chunks_deleted": total_chunks or 0
                }
            
            return {
                "total_operations": total_operations,
                "recent_operations_30_days": recent_operations,
                "deletions_by_type": type_stats
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error("Failed to get deletion stats", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get deletion stats: {str(e)}")