from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean
from datetime import datetime

from app.core.database import Base


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