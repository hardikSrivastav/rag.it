from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import os

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()

class Document(Base):
    """Document metadata model"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    file_path = Column(String, nullable=True)
    source_tool = Column(String, default="manual_upload")
    content_type = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    status = Column(String, default="pending")  # pending, processing, indexed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    indexed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    chunk_count = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<Document(id={self.id}, filename='{self.filename}', status='{self.status}')>"

class DocumentChunk(Base):
    """Document chunk metadata model"""
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, index=True)
    chunk_index = Column(Integer)
    chunk_text = Column(Text)
    chunk_hash = Column(String, index=True)  # Hash of the chunk content
    vector_id = Column(String, index=True)  # ID in Qdrant
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<DocumentChunk(id={self.id}, document_id={self.document_id}, chunk_index={self.chunk_index})>"

class ChatSession(Base):
    """Chat session model for tracking conversations"""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<ChatSession(id={self.id}, session_id='{self.session_id}')>"

class ChatMessage(Base):
    """Chat message model"""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    role = Column(String)  # user, assistant, system
    content = Column(Text)
    sources = Column(JSON, nullable=True)  # List of source documents used
    model_used = Column(String, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<ChatMessage(id={self.id}, session_id='{self.session_id}', role='{self.role}')>"


class FileSystemNode(Base):
    """File system node model for Merkle tree persistence"""
    __tablename__ = "filesystem_nodes"
    
    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, unique=True, index=True)
    hash = Column(String, index=True)
    node_type = Column(String, index=True)  # 'file' or 'directory'
    size = Column(Integer)
    modified_time = Column(Float)
    permissions = Column(Integer)
    parent_path = Column(String, index=True, nullable=True)
    children_hashes = Column(JSON, nullable=True)  # List of child hashes for directories
    last_indexed = Column(DateTime, nullable=True)
    should_index = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<FileSystemNode(id={self.id}, path='{self.path}', type='{self.node_type}')>"


class MerkleSnapshot(Base):
    """Merkle tree snapshot model for change tracking"""
    __tablename__ = "merkle_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    root_path = Column(String, index=True)
    root_hash = Column(String, index=True)
    total_files = Column(Integer)
    total_directories = Column(Integer)
    total_size_bytes = Column(Integer)
    scan_duration_seconds = Column(Float)
    changes_detected = Column(Integer, default=0)
    files_indexed = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<MerkleSnapshot(id={self.id}, root_path='{self.root_path}', files={self.total_files})>"


class IndexingPolicy(Base):
    """Indexing policy model for file type filtering"""
    __tablename__ = "indexing_policies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    path_pattern = Column(String, index=True)  # Glob pattern for paths
    file_extensions = Column(JSON, nullable=True)  # List of allowed extensions
    max_file_size_mb = Column(Integer, nullable=True)  # Max file size in MB
    should_index = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Higher number = higher priority
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<IndexingPolicy(id={self.id}, name='{self.name}', pattern='{self.path_pattern}')>"


class ConnectorConfig(Base):
    """Connector configuration model"""
    __tablename__ = "connector_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    connector_type = Column(String, index=True)  # github, notion, email, etc.
    enabled = Column(Boolean, default=True)
    sync_interval_minutes = Column(Integer, default=60)
    max_items_per_sync = Column(Integer, default=1000)
    last_sync = Column(DateTime, nullable=True)
    last_sync_status = Column(String, nullable=True)  # success, error, running
    credentials = Column(JSON, nullable=True)  # Encrypted credentials
    settings = Column(JSON, nullable=True)  # Connector-specific settings
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<ConnectorConfig(id={self.id}, name='{self.name}', type='{self.connector_type}')>"


class ConnectorSyncLog(Base):
    """Connector sync operation log"""
    __tablename__ = "connector_sync_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    connector_id = Column(Integer, index=True)
    connector_name = Column(String, index=True)
    sync_type = Column(String, index=True)  # full, incremental
    status = Column(String, index=True)  # success, error, running
    items_processed = Column(Integer, default=0)
    items_added = Column(Integer, default=0)
    items_updated = Column(Integer, default=0)
    items_failed = Column(Integer, default=0)
    duration_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    sync_token = Column(String, nullable=True)  # For incremental syncs
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<ConnectorSyncLog(id={self.id}, connector='{self.connector_name}', status='{self.status}')>"


class OAuthConfig(Base):
    """OAuth configuration model for persistent storage"""
    __tablename__ = "oauth_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, unique=True, index=True)  # github, google, etc.
    client_id = Column(String)
    client_secret = Column(String)  # Should be encrypted in production
    redirect_uri = Column(String)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<OAuthConfig(provider='{self.provider}', enabled={self.enabled})>"


class OAuthToken(Base):
    """OAuth token storage for users"""
    __tablename__ = "oauth_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, index=True)  # github, google, etc.
    user_identifier = Column(String, index=True)  # github username, email, etc.
    access_token = Column(String)  # Should be encrypted in production
    token_type = Column(String, default="bearer")
    scope = Column(String)
    user_info = Column(JSON)  # Store user profile info
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used = Column(DateTime, default=datetime.utcnow)
    is_valid = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<OAuthToken(provider='{self.provider}', user='{self.user_identifier}')>"


class DeletionLog(Base):
    """Log of deletion operations"""
    __tablename__ = "deletion_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    deletion_type = Column(String, index=True)  # source, repository, document, chunk
    target_filters = Column(JSON)  # Filters used for deletion
    documents_deleted = Column(Integer, default=0)
    chunks_deleted = Column(Integer, default=0)
    vectors_deleted = Column(Integer, default=0)
    backup_id = Column(String, nullable=True)
    executed_by = Column(String, default="system")
    executed_at = Column(DateTime, default=datetime.utcnow)
    duration_seconds = Column(Float, nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<DeletionLog(id={self.id}, type='{self.deletion_type}', docs={self.documents_deleted})>"


class DeletionBackup(Base):
    """Backup data for deleted items (for potential restoration)"""
    __tablename__ = "deletion_backups"
    
    id = Column(Integer, primary_key=True, index=True)
    backup_id = Column(String, unique=True, index=True)
    deletion_type = Column(String, index=True)
    target_filters = Column(JSON)
    document_count = Column(Integer)
    chunk_count = Column(Integer)
    backup_data = Column(JSON)  # Serialized document and chunk data
    created_at = Column(DateTime, default=datetime.utcnow)
    can_restore = Column(Boolean, default=True)
    restored_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<DeletionBackup(backup_id='{self.backup_id}', docs={self.document_count})>"


def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database"""
    logger.info("Initializing database", database_url=settings.DATABASE_URL)
    create_tables()
    logger.info("Database initialized successfully") 