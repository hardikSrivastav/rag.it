import asyncio
import aiohttp
import secrets
import urllib.parse
import base64
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.logging import get_logger
from app.core.oauth_config_manager import oauth_config_manager

logger = get_logger(__name__)


class NotionOAuthService:
    """Notion OAuth service for connector authentication"""
    
    def __init__(self):
        self.pending_states: Dict[str, Dict] = {}
        self._load_config()
        
    def _load_config(self):
        """Load OAuth configuration from YAML file"""
        config = oauth_config_manager.get_oauth_config("notion")
        if config:
            logger.info("Notion OAuth configuration loaded from file")
        
    def configure(self, client_id: str, client_secret: str, redirect_uri: str):
        """Configure OAuth credentials and save to file"""
        oauth_config_manager.save_oauth_config("notion", client_id, client_secret, redirect_uri)
        logger.info("Notion OAuth configured and saved", client_id=client_id[:8] + "...")
    
    def is_configured(self) -> bool:
        """Check if OAuth is properly configured"""
        return oauth_config_manager.is_oauth_configured("notion")
    
    def get_config(self) -> Optional[Dict]:
        """Get current OAuth configuration"""
        return oauth_config_manager.get_oauth_config("notion")
    
    def generate_auth_url(self, connector_name: str) -> Dict[str, str]:
        """Generate Notion OAuth authorization URL"""
        if not self.is_configured():
            raise ValueError("Notion OAuth not configured")
        
        config = self.get_config()
        if not config:
            raise ValueError("Notion OAuth configuration not found")
        
        # Generate secure state parameter
        state = secrets.token_urlsafe(32)
        
        # Store state with connector info
        self.pending_states[state] = {
            "connector_name": connector_name,
            "created_at": datetime.utcnow()
        }
        
        # Build authorization URL
        params = {
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "response_type": "code",
            "state": state,
            "owner": "user"  # Notion-specific parameter
        }
        
        auth_url = "https://api.notion.com/v1/oauth/authorize?" + urllib.parse.urlencode(params)
        
        return {
            "auth_url": auth_url,
            "state": state,
            "expires_in": 600  # 10 minutes
        }
    
    async def exchange_code_for_token(self, code: str, state: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        if not self.is_configured():
            raise ValueError("Notion OAuth not configured")
        
        config = self.get_config()
        if not config:
            raise ValueError("Notion OAuth configuration not found")
        
        # Validate state
        if state not in self.pending_states:
            raise ValueError("Invalid or expired state parameter")
        
        state_info = self.pending_states[state]
        
        # Check if state is expired (10 minutes)
        if datetime.utcnow() - state_info["created_at"] > timedelta(minutes=10):
            del self.pending_states[state]
            raise ValueError("OAuth state expired")
        
        try:
            # Exchange code for token
            async with aiohttp.ClientSession() as session:
                # Notion uses Basic auth for token exchange
                auth_string = f"{config['client_id']}:{config['client_secret']}"
                auth_bytes = auth_string.encode('ascii')
                auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
                
                headers = {
                    "Authorization": f"Basic {auth_b64}",
                    "Content-Type": "application/json",
                    "Notion-Version": "2022-06-28"
                }
                
                token_data = {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": config["redirect_uri"]
                }
                
                async with session.post(
                    "https://api.notion.com/v1/oauth/token",
                    json=token_data,
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Token exchange failed: {response.status} - {error_text}")
                    
                    token_response = await response.json()
                    
                    if "error" in token_response:
                        raise Exception(f"OAuth error: {token_response.get('error_description', token_response['error'])}")
                    
                    access_token = token_response.get("access_token")
                    if not access_token:
                        raise Exception("No access token received")
                    
                    # Get workspace info
                    workspace_info = token_response.get("workspace", {})
                    bot_user = token_response.get("bot_user", {})
                    
                    # Save token to YAML file for persistence
                    user_identifier = workspace_info.get("name", bot_user.get("id", "unknown"))
                    oauth_config_manager.save_oauth_token(
                        provider="notion",
                        user_identifier=user_identifier,
                        access_token=access_token,
                        token_type=token_response.get("token_type", "bearer"),
                        scope="",  # Notion doesn't use scopes
                        user_info={
                            "workspace": workspace_info,
                            "bot_user": bot_user,
                            "owner": token_response.get("owner", {})
                        }
                    )
                    
                    # Clean up state
                    del self.pending_states[state]
                    
                    return {
                        "access_token": access_token,
                        "token_type": token_response.get("token_type", "bearer"),
                        "workspace_info": workspace_info,
                        "bot_user": bot_user,
                        "connector_name": state_info["connector_name"],
                        "expires_at": None  # Notion tokens don't expire
                    }
                    
        except Exception as e:
            # Clean up state on error
            if state in self.pending_states:
                del self.pending_states[state]
            logger.error(f"Notion OAuth token exchange failed: {e}")
            raise
    
    def get_stored_token(self, user_identifier: str = None) -> Optional[str]:
        """Get stored OAuth token for Notion"""
        if user_identifier:
            token_data = oauth_config_manager.get_oauth_token("notion", user_identifier)
        else:
            # Get the most recent token
            token_data = oauth_config_manager.get_latest_token("notion")
        
        if token_data and token_data.get("is_valid", True):
            # Update usage timestamp
            oauth_config_manager.update_token_usage("notion", token_data["user_identifier"])
            return token_data["access_token"]
        
        return None
    
    def get_stored_user_info(self, user_identifier: str = None) -> Optional[Dict]:
        """Get stored user info for Notion"""
        if user_identifier:
            token_data = oauth_config_manager.get_oauth_token("notion", user_identifier)
        else:
            token_data = oauth_config_manager.get_latest_token("notion")
        
        if token_data:
            return token_data.get("user_info", {})
        
        return None


class GitHubOAuthService:
    """GitHub OAuth service for connector authentication"""
    
    def __init__(self):
        self.pending_states: Dict[str, Dict] = {}  # Store pending OAuth states
        self._load_config()
        
    def _load_config(self):
        """Load OAuth configuration from YAML file"""
        config = oauth_config_manager.get_oauth_config("github")
        if config:
            logger.info("GitHub OAuth configuration loaded from file")
        
    def configure(self, client_id: str, client_secret: str, redirect_uri: str):
        """Configure OAuth credentials and save to file"""
        oauth_config_manager.save_oauth_config("github", client_id, client_secret, redirect_uri)
        logger.info("GitHub OAuth configured and saved", client_id=client_id[:8] + "...")
    
    def is_configured(self) -> bool:
        """Check if OAuth is properly configured"""
        return oauth_config_manager.is_oauth_configured("github")
    
    def get_config(self) -> Optional[Dict]:
        """Get current OAuth configuration"""
        return oauth_config_manager.get_oauth_config("github")
    
    def generate_auth_url(self, connector_name: str, scopes: list = None) -> Dict[str, str]:
        """Generate GitHub OAuth authorization URL"""
        if not self.is_configured():
            raise ValueError("GitHub OAuth not configured")
        
        config = self.get_config()
        if not config:
            raise ValueError("GitHub OAuth configuration not found")
        
        if scopes is None:
            scopes = ["repo", "user:email"]
        
        # Generate secure state parameter
        state = secrets.token_urlsafe(32)
        
        # Store state with connector info
        self.pending_states[state] = {
            "connector_name": connector_name,
            "created_at": datetime.utcnow(),
            "scopes": scopes
        }
        
        # Build authorization URL
        params = {
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "scope": " ".join(scopes),
            "state": state,
            "response_type": "code"
        }
        
        auth_url = "https://github.com/login/oauth/authorize?" + urllib.parse.urlencode(params)
        
        return {
            "auth_url": auth_url,
            "state": state,
            "expires_in": 600  # 10 minutes
        }
    
    async def exchange_code_for_token(self, code: str, state: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        if not self.is_configured():
            raise ValueError("GitHub OAuth not configured")
        
        config = self.get_config()
        if not config:
            raise ValueError("GitHub OAuth configuration not found")
        
        # Validate state
        if state not in self.pending_states:
            raise ValueError("Invalid or expired state parameter")
        
        state_info = self.pending_states[state]
        
        # Check if state is expired (10 minutes)
        if datetime.utcnow() - state_info["created_at"] > timedelta(minutes=10):
            del self.pending_states[state]
            raise ValueError("OAuth state expired")
        
        try:
            # Exchange code for token
            async with aiohttp.ClientSession() as session:
                token_data = {
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                    "code": code,
                    "redirect_uri": config["redirect_uri"]
                }
                
                headers = {
                    "Accept": "application/json",
                    "User-Agent": "RAG-System/1.0"
                }
                
                async with session.post(
                    "https://github.com/login/oauth/access_token",
                    data=token_data,
                    headers=headers
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Token exchange failed: {response.status}")
                    
                    token_response = await response.json()
                    
                    if "error" in token_response:
                        raise Exception(f"OAuth error: {token_response['error_description']}")
                    
                    access_token = token_response.get("access_token")
                    if not access_token:
                        raise Exception("No access token received")
                    
                    # Get user info
                    user_info = await self._get_user_info(access_token)
                    
                    # Save token to YAML file for persistence
                    user_identifier = user_info.get("login", "unknown")
                    oauth_config_manager.save_oauth_token(
                        provider="github",
                        user_identifier=user_identifier,
                        access_token=access_token,
                        token_type=token_response.get("token_type", "bearer"),
                        scope=token_response.get("scope", ""),
                        user_info=user_info
                    )
                    
                    # Clean up state
                    del self.pending_states[state]
                    
                    return {
                        "access_token": access_token,
                        "token_type": token_response.get("token_type", "bearer"),
                        "scope": token_response.get("scope", ""),
                        "user_info": user_info,
                        "connector_name": state_info["connector_name"],
                        "expires_at": None  # GitHub tokens don't expire
                    }
                    
        except Exception as e:
            # Clean up state on error
            if state in self.pending_states:
                del self.pending_states[state]
            logger.error(f"OAuth token exchange failed: {e}")
            raise
    
    async def _get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from GitHub API"""
        try:
            headers = {
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "RAG-System/1.0"
            }
            
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get("https://api.github.com/user") as response:
                    if response.status != 200:
                        raise Exception(f"Failed to get user info: {response.status}")
                    
                    user_data = await response.json()
                    
                    return {
                        "id": user_data.get("id"),
                        "login": user_data.get("login"),
                        "name": user_data.get("name"),
                        "email": user_data.get("email"),
                        "avatar_url": user_data.get("avatar_url"),
                        "public_repos": user_data.get("public_repos"),
                        "private_repos": user_data.get("total_private_repos")
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            return {}
    
    async def validate_token(self, access_token: str) -> bool:
        """Validate if access token is still valid"""
        try:
            headers = {
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "RAG-System/1.0"
            }
            
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get("https://api.github.com/user") as response:
                    return response.status == 200
                    
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            return False
    
    async def get_user_repositories(self, access_token: str, include_private: bool = True) -> list:
        """Get list of user's repositories"""
        try:
            headers = {
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "RAG-System/1.0"
            }
            
            repositories = []
            page = 1
            per_page = 100
            
            async with aiohttp.ClientSession(headers=headers) as session:
                while True:
                    params = {
                        "visibility": "all" if include_private else "public",
                        "sort": "updated",
                        "per_page": per_page,
                        "page": page
                    }
                    
                    async with session.get("https://api.github.com/user/repos", params=params) as response:
                        if response.status != 200:
                            break
                        
                        repos = await response.json()
                        if not repos:
                            break
                        
                        for repo in repos:
                            repositories.append({
                                "full_name": repo["full_name"],
                                "name": repo["name"],
                                "private": repo["private"],
                                "description": repo.get("description", ""),
                                "language": repo.get("language"),
                                "updated_at": repo["updated_at"],
                                "size": repo["size"],
                                "default_branch": repo["default_branch"]
                            })
                        
                        if len(repos) < per_page:
                            break
                        
                        page += 1
            
            return repositories
            
        except Exception as e:
            logger.error(f"Failed to get repositories: {e}")
            return []
    
    def get_stored_token(self, user_identifier: str = None) -> Optional[str]:
        """Get stored OAuth token for GitHub"""
        if user_identifier:
            token_data = oauth_config_manager.get_oauth_token("github", user_identifier)
        else:
            # Get the most recent token
            token_data = oauth_config_manager.get_latest_token("github")
        
        if token_data and token_data.get("is_valid", True):
            # Update usage timestamp
            oauth_config_manager.update_token_usage("github", token_data["user_identifier"])
            return token_data["access_token"]
        
        return None
    
    def get_stored_user_info(self, user_identifier: str = None) -> Optional[Dict]:
        """Get stored user info for GitHub"""
        if user_identifier:
            token_data = oauth_config_manager.get_oauth_token("github", user_identifier)
        else:
            token_data = oauth_config_manager.get_latest_token("github")
        
        if token_data:
            return token_data.get("user_info", {})
        
        return None
    
    def cleanup_expired_states(self):
        """Clean up expired OAuth states"""
        current_time = datetime.utcnow()
        expired_states = [
            state for state, info in self.pending_states.items()
            if current_time - info["created_at"] > timedelta(minutes=10)
        ]
        
        for state in expired_states:
            del self.pending_states[state]
        
        if expired_states:
            logger.info(f"Cleaned up {len(expired_states)} expired OAuth states")


# Global OAuth service instance
github_oauth_service = GitHubOAuthService()