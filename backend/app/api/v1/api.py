from fastapi import APIRouter

from app.api.v1.endpoints import ingest, chat, documents, health

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(health.router, prefix="/health", tags=["health"]) 