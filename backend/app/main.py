from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1.api import api_router
from app.core.database import init_db
from app.services.startup_service import startup_service

# Setup logging
setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    
    # Initialize file system indexing
    await startup_service.initialize()
    
    yield
    
    # Shutdown - cleanup if needed
    from app.services.file_watcher import file_watcher
    file_watcher.stop_watching()
    
    from app.services.file_system_indexer import file_system_indexer
    file_system_indexer.stop_background_indexing()
    
    from app.services.connectors.manager import connector_manager
    await connector_manager.cleanup()

app = FastAPI(
    title="RAG System API",
    description="Internal RAG System / Personal Knowledge Lake",
    version="1.0.0",
    lifespan=lifespan
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "RAG System API is running", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "rag-system"}

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8792,
        reload=True,
        log_level="info"
    ) 