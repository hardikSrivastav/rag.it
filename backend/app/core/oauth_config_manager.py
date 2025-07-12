import yaml
import os
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime

from app.core.logging import get_logger

logger = get_logger(__name__)


class OAuthConfigManager:
    """Manages OAuth configuration and tokens using YAML files"""
    
    def __init__(self, config_dir: str = "./config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        self.oauth_config_file = self.config_dir / "oauth_config.yaml"
        self.tokens_file = self.config_dir / "oauth_tokens.yaml"
        
        # Ensure files exist
        self._ensure_config_files()
    
    def _ensure_config_files(self):
        """Create config files if they don't exist"""
        if not self.oauth_config_file.exists():
            default_config = {
                "providers": {},
                "created_at": datetime.utcnow().isoformat(),
                "version": "1.0"
            }
            self._save_yaml(self.oauth_config_file, default_config)
        
        if not self.tokens_file.exists():
            default_tokens = {
                "tokens": {},
                "created_at": datetime.utcnow().isoformat(),
                "version": "1.0"
            }
            self._save_yaml(self.tokens_file, default_tokens)
    
    def _load_yaml(self, file_path: Path) -> Dict:
        """Load YAML file safely"""
        try:
            with open(file_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load {file_path}: {e}")
            return {}
    
    def _save_yaml(self, file_path: Path, data: Dict):
        """Save data to YAML file safely"""
        try:
            with open(file_path, 'w') as f:
                yaml.safe_dump(data, f, default_flow_style=False, indent=2)
            logger.debug(f"Saved config to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save {file_path}: {e}")
            raise
    
    # OAuth Provider Configuration
    def save_oauth_config(self, provider: str, client_id: str, client_secret: str, redirect_uri: str):
        """Save OAuth provider configuration"""
        config = self._load_yaml(self.oauth_config_file)
        
        config["providers"][provider] = {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "enabled": True,
            "configured_at": datetime.utcnow().isoformat()
        }
        config["updated_at"] = datetime.utcnow().isoformat()
        
        self._save_yaml(self.oauth_config_file, config)
        logger.info(f"OAuth config saved for {provider}")
    
    def get_oauth_config(self, provider: str) -> Optional[Dict]:
        """Get OAuth provider configuration"""
        config = self._load_yaml(self.oauth_config_file)
        return config.get("providers", {}).get(provider)
    
    def is_oauth_configured(self, provider: str) -> bool:
        """Check if OAuth is configured for a provider"""
        config = self.get_oauth_config(provider)
        return config is not None and config.get("enabled", False)
    
    # OAuth Token Management
    def save_oauth_token(self, provider: str, user_identifier: str, access_token: str, 
                        token_type: str = "bearer", scope: str = "", user_info: Dict = None):
        """Save OAuth token for a user"""
        tokens = self._load_yaml(self.tokens_file)
        
        token_key = f"{provider}_{user_identifier}"
        tokens["tokens"][token_key] = {
            "provider": provider,
            "user_identifier": user_identifier,
            "access_token": access_token,
            "token_type": token_type,
            "scope": scope,
            "user_info": user_info or {},
            "created_at": datetime.utcnow().isoformat(),
            "last_used": datetime.utcnow().isoformat(),
            "is_valid": True
        }
        tokens["updated_at"] = datetime.utcnow().isoformat()
        
        self._save_yaml(self.tokens_file, tokens)
        logger.info(f"OAuth token saved for {provider}:{user_identifier}")
    
    def get_oauth_token(self, provider: str, user_identifier: str) -> Optional[Dict]:
        """Get OAuth token for a user"""
        tokens = self._load_yaml(self.tokens_file)
        token_key = f"{provider}_{user_identifier}"
        return tokens.get("tokens", {}).get(token_key)
    
    def get_latest_token(self, provider: str) -> Optional[Dict]:
        """Get the most recently used token for a provider"""
        tokens = self._load_yaml(self.tokens_file)
        provider_tokens = [
            token for token in tokens.get("tokens", {}).values()
            if token.get("provider") == provider and token.get("is_valid", True)
        ]
        
        if not provider_tokens:
            return None
        
        # Sort by last_used and return the most recent
        provider_tokens.sort(key=lambda x: x.get("last_used", ""), reverse=True)
        return provider_tokens[0]
    
    def update_token_usage(self, provider: str, user_identifier: str):
        """Update last_used timestamp for a token"""
        tokens = self._load_yaml(self.tokens_file)
        token_key = f"{provider}_{user_identifier}"
        
        if token_key in tokens.get("tokens", {}):
            tokens["tokens"][token_key]["last_used"] = datetime.utcnow().isoformat()
            self._save_yaml(self.tokens_file, tokens)
    
    def invalidate_token(self, provider: str, user_identifier: str):
        """Mark a token as invalid"""
        tokens = self._load_yaml(self.tokens_file)
        token_key = f"{provider}_{user_identifier}"
        
        if token_key in tokens.get("tokens", {}):
            tokens["tokens"][token_key]["is_valid"] = False
            tokens["tokens"][token_key]["invalidated_at"] = datetime.utcnow().isoformat()
            self._save_yaml(self.tokens_file, tokens)
            logger.info(f"Token invalidated for {provider}:{user_identifier}")
    
    def list_tokens(self, provider: str = None) -> Dict:
        """List all tokens, optionally filtered by provider"""
        tokens = self._load_yaml(self.tokens_file)
        all_tokens = tokens.get("tokens", {})
        
        if provider:
            filtered_tokens = {
                key: token for key, token in all_tokens.items()
                if token.get("provider") == provider
            }
            return filtered_tokens
        
        return all_tokens
    
    def get_config_status(self) -> Dict:
        """Get overall configuration status"""
        oauth_config = self._load_yaml(self.oauth_config_file)
        tokens = self._load_yaml(self.tokens_file)
        
        providers = oauth_config.get("providers", {})
        active_tokens = {
            provider: len([
                t for t in tokens.get("tokens", {}).values()
                if t.get("provider") == provider and t.get("is_valid", True)
            ])
            for provider in providers.keys()
        }
        
        return {
            "configured_providers": list(providers.keys()),
            "active_tokens": active_tokens,
            "config_file": str(self.oauth_config_file),
            "tokens_file": str(self.tokens_file),
            "last_updated": oauth_config.get("updated_at", "Never")
        }


# Global instance
oauth_config_manager = OAuthConfigManager()