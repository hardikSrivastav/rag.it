from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import RedirectResponse
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

from app.core.logging import get_logger
from app.services.oauth_service import github_oauth_service, gmail_oauth_service, NotionOAuthService, calendar_oauth_service
from app.services.connectors.manager import connector_manager

# Initialize Notion OAuth service
notion_oauth_service = NotionOAuthService()

logger = get_logger(__name__)

router = APIRouter()


class OAuthConfigRequest(BaseModel):
    client_id: str
    client_secret: str
    redirect_uri: str


class ConnectorOAuthRequest(BaseModel):
    connector_name: str
    connector_type: str = "github"
    scopes: List[str] = ["repo", "user:email"]
    settings: Dict = {}


@router.post("/github/configure")
async def configure_github_oauth(request: OAuthConfigRequest):
    """Configure GitHub OAuth credentials"""
    try:
        github_oauth_service.configure(
            client_id=request.client_id,
            client_secret=request.client_secret,
            redirect_uri=request.redirect_uri
        )
        
        return {
            "success": True,
            "message": "GitHub OAuth configured successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to configure GitHub OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/github/status")
async def get_github_oauth_status():
    """Get GitHub OAuth configuration status"""
    from app.core.oauth_config_manager import oauth_config_manager
    
    config = github_oauth_service.get_config()
    stored_token = github_oauth_service.get_stored_token()
    user_info = github_oauth_service.get_stored_user_info()
    
    return {
        "configured": github_oauth_service.is_configured(),
        "redirect_uri": config.get("redirect_uri") if config else None,
        "has_stored_token": stored_token is not None,
        "user_info": user_info,
        "config_status": oauth_config_manager.get_config_status()
    }


@router.post("/github/authorize")
async def start_github_oauth(request: ConnectorOAuthRequest):
    """Start GitHub OAuth flow for a connector"""
    try:
        if not github_oauth_service.is_configured():
            raise HTTPException(
                status_code=400, 
                detail="GitHub OAuth not configured. Please configure OAuth credentials first."
            )
        
        # Generate authorization URL
        auth_data = github_oauth_service.generate_auth_url(
            connector_name=request.connector_name,
            scopes=request.scopes
        )
        
        return {
            "success": True,
            "auth_url": auth_data["auth_url"],
            "state": auth_data["state"],
            "expires_in": auth_data["expires_in"],
            "message": "Visit the auth_url to authorize the application"
        }
        
    except Exception as e:
        logger.error(f"Failed to start GitHub OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/github/callback")
async def github_oauth_callback(code: str, state: str):
    """Handle GitHub OAuth callback"""
    try:
        # Exchange code for token
        token_data = await github_oauth_service.exchange_code_for_token(code, state)
        
        # Create connector with the token
        connector_name = token_data["connector_name"]
        
        # Add connector to manager
        await connector_manager.add_connector(
            name=connector_name,
            connector_type="github",
            credentials={
                "access_token": token_data["access_token"],
                "token_type": token_data["token_type"],
                "scope": token_data["scope"]
            },
            settings={
                "user_info": token_data["user_info"],
                "sync_interval_minutes": 60
            },
            enabled=True
        )
        
        return {
            "success": True,
            "message": f"GitHub connector '{connector_name}' created successfully",
            "connector_name": connector_name,
            "user_info": token_data["user_info"]
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"GitHub OAuth callback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Gmail OAuth endpoints
@router.get("/gmail/authorize")
async def gmail_oauth_authorize(connector_name: str):
    """Start Gmail OAuth flow"""
    try:
        if not gmail_oauth_service.is_configured():
            raise HTTPException(
                status_code=400, 
                detail="Gmail OAuth not configured. Please configure OAuth credentials first."
            )
        
        auth_data = gmail_oauth_service.generate_auth_url(connector_name)
        
        return {
            "auth_url": auth_data["auth_url"],
            "state": auth_data["state"],
            "expires_in": auth_data["expires_in"],
            "message": "Visit the auth_url to authorize the Gmail connector"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Gmail OAuth authorization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gmail/callback")
async def gmail_oauth_callback(code: str, state: str):
    """Handle Gmail OAuth callback"""
    try:
        # Exchange code for token
        token_data = await gmail_oauth_service.exchange_code_for_token(code, state)
        
        # Create connector with the token
        connector_name = token_data["connector_name"]
        
        # Add connector to manager
        await connector_manager.add_connector(
            name=connector_name,
            connector_type="gmail",
            credentials={
                "access_token": token_data["access_token"],
                "token_type": token_data["token_type"],
                "refresh_token": token_data.get("refresh_token"),
                "scope": token_data["scope"]
            },
            settings={
                "user_info": token_data["user_info"],
                "sync_interval_minutes": 60,
                "max_emails_per_sync": 100,
                "days_back": 30,
                "include_sent": True,
                "include_drafts": False
            },
            enabled=True
        )
        
        return {
            "success": True,
            "message": f"Gmail connector '{connector_name}' created successfully",
            "connector_name": connector_name,
            "user_info": token_data["user_info"]
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Gmail OAuth callback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gmail/configure")
async def configure_gmail_oauth(request: OAuthConfigRequest):
    """Configure Gmail OAuth credentials"""
    try:
        gmail_oauth_service.configure(
            client_id=request.client_id,
            client_secret=request.client_secret,
            redirect_uri=request.redirect_uri
        )
        
        return {
            "success": True,
            "message": "Gmail OAuth configured successfully",
            "provider": "gmail"
        }
        
    except Exception as e:
        logger.error(f"Gmail OAuth configuration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/github/repositories/{connector_name}")
async def get_github_repositories(connector_name: str):
    """Get available repositories for a GitHub connector"""
    try:
        # Get connector
        connector = connector_manager.connectors.get(connector_name)
        if not connector:
            raise HTTPException(status_code=404, detail="Connector not found")
        
        if connector.connector_type != "github":
            raise HTTPException(status_code=400, detail="Not a GitHub connector")
        
        # Get access token
        access_token = connector.config.credentials.get("token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token found")
        
        # Get repositories
        repositories = await github_oauth_service.get_user_repositories(access_token)
        
        return {
            "success": True,
            "repositories": repositories,
            "total": len(repositories)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get repositories for {connector_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/github/repositories/{connector_name}")
async def configure_github_repositories(
    connector_name: str, 
    repositories: List[str]
):
    """Configure repositories for a GitHub connector"""
    try:
        # Get connector from database and update settings
        from app.core.database import get_db, ConnectorConfig
        
        db = next(get_db())
        try:
            config = db.query(ConnectorConfig).filter(ConnectorConfig.name == connector_name).first()
            if not config:
                raise HTTPException(status_code=404, detail="Connector not found")
            
            # Update settings
            settings = config.settings or {}
            settings["repositories"] = repositories
            config.settings = settings
            config.enabled = True  # Enable connector now that repos are configured
            
            db.commit()
            db.refresh(config)  # Refresh the object to ensure it's up to date
            
        finally:
            db.close()
        
        # Recreate connector instance with new settings (outside of db session)
        await connector_manager.remove_connector(connector_name)
        
        # Get fresh config from database for connector creation
        db = next(get_db())
        try:
            fresh_config = db.query(ConnectorConfig).filter(ConnectorConfig.name == connector_name).first()
            if fresh_config:
                await connector_manager.create_connector(fresh_config)
        finally:
            db.close()
        
        return {
            "success": True,
            "message": f"Configured {len(repositories)} repositories for {connector_name}",
            "repositories": repositories
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to configure repositories for {connector_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Notion OAuth endpoints
@router.post("/notion/configure")
async def configure_notion_oauth(request: OAuthConfigRequest):
    """Configure Notion OAuth credentials"""
    try:
        notion_oauth_service.configure(
            client_id=request.client_id,
            client_secret=request.client_secret,
            redirect_uri=request.redirect_uri
        )
        
        return {
            "success": True,
            "message": "Notion OAuth configured successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to configure Notion OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notion/status")
async def get_notion_oauth_status():
    """Get Notion OAuth configuration status"""
    from app.core.oauth_config_manager import oauth_config_manager
    
    config = notion_oauth_service.get_config()
    stored_token = notion_oauth_service.get_stored_token()
    user_info = notion_oauth_service.get_stored_user_info()
    
    return {
        "configured": notion_oauth_service.is_configured(),
        "redirect_uri": config.get("redirect_uri") if config else None,
        "has_stored_token": stored_token is not None,
        "user_info": user_info,
        "config_status": oauth_config_manager.get_config_status()
    }


@router.post("/notion/authorize")
async def start_notion_oauth(request: ConnectorOAuthRequest):
    """Start Notion OAuth flow for a connector"""
    try:
        if not notion_oauth_service.is_configured():
            raise HTTPException(
                status_code=400, 
                detail="Notion OAuth not configured. Please configure OAuth credentials first."
            )
        
        # Generate authorization URL
        auth_data = notion_oauth_service.generate_auth_url(
            connector_name=request.connector_name
        )
        
        return {
            "success": True,
            "auth_url": auth_data["auth_url"],
            "state": auth_data["state"],
            "expires_in": auth_data["expires_in"],
            "message": "Visit the auth_url to authorize the application"
        }
        
    except Exception as e:
        logger.error(f"Failed to start Notion OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notion/callback")
async def notion_oauth_callback(
    code: str = Query(..., description="Authorization code from Notion"),
    state: str = Query(..., description="State parameter for security"),
    error: Optional[str] = Query(None, description="Error from Notion OAuth")
):
    """Handle Notion OAuth callback"""
    try:
        if error:
            logger.error(f"Notion OAuth error: {error}")
            raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
        
        # Exchange code for token
        token_data = await notion_oauth_service.exchange_code_for_token(code, state)
        
        # Create connector with OAuth token
        connector_name = token_data["connector_name"]
        
        # Check if connector already exists
        existing_status = connector_manager.get_connector_status(connector_name)
        if existing_status:
            # Update existing connector
            await connector_manager.remove_connector(connector_name)
        
        # Create new connector with OAuth credentials
        await connector_manager.add_connector(
            name=connector_name,
            connector_type="notion",
            credentials={
                "token": token_data["access_token"],
                "token_type": token_data["token_type"],
                "oauth_workspace": token_data["workspace_info"],
                "oauth_bot_user": token_data["bot_user"]
            },
            settings={
                "sync_pages": True,
                "sync_databases": True,
                "max_database_entries": 50  # Limit entries per database
            },
            enabled=False  # Start disabled until user enables
        )
        
        logger.info(f"Notion connector '{connector_name}' created successfully via OAuth")
        
        return {
            "success": True,
            "message": f"Notion connector '{connector_name}' authorized successfully!",
            "connector_name": connector_name,
            "workspace_info": token_data["workspace_info"],
            "next_steps": [
                "Enable the connector",
                "Start syncing pages and databases"
            ]
        }
        
    except ValueError as e:
        logger.error(f"Notion OAuth callback validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Notion OAuth callback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Google Calendar OAuth endpoints
@router.post("/calendar/configure")
async def configure_calendar_oauth(request: OAuthConfigRequest):
    """Configure Google Calendar OAuth credentials"""
    try:
        calendar_oauth_service.configure(
            client_id=request.client_id,
            client_secret=request.client_secret,
            redirect_uri=request.redirect_uri
        )
        
        return {
            "success": True,
            "message": "Google Calendar OAuth configured successfully",
            "provider": "calendar"
        }
        
    except Exception as e:
        logger.error(f"Calendar OAuth configuration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calendar/status")
async def get_calendar_oauth_status():
    """Get Google Calendar OAuth configuration status"""
    from app.core.oauth_config_manager import oauth_config_manager
    
    config = calendar_oauth_service.get_config()
    stored_token = calendar_oauth_service.get_stored_token()
    user_info = calendar_oauth_service.get_stored_user_info()
    
    return {
        "configured": calendar_oauth_service.is_configured(),
        "redirect_uri": config.get("redirect_uri") if config else None,
        "has_stored_token": stored_token is not None,
        "user_info": user_info,
        "config_status": oauth_config_manager.get_config_status()
    }


@router.get("/calendar/authorize")
async def calendar_oauth_authorize(connector_name: str):
    """Start Google Calendar OAuth flow"""
    try:
        if not calendar_oauth_service.is_configured():
            raise HTTPException(
                status_code=400, 
                detail="Google Calendar OAuth not configured. Please configure OAuth credentials first."
            )
        
        # Calendar-specific scopes
        scopes = [
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/userinfo.email"
        ]
        
        auth_data = calendar_oauth_service.generate_auth_url(
            connector_name=connector_name,
            scopes=scopes
        )
        
        return {
            "auth_url": auth_data["auth_url"],
            "state": auth_data["state"],
            "expires_in": auth_data["expires_in"],
            "message": "Visit the auth_url to authorize the Google Calendar connector"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Calendar OAuth authorization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calendar/callback")
async def calendar_oauth_callback(code: str, state: str):
    """Handle Google Calendar OAuth callback"""
    try:
        # Exchange code for token
        token_data = await calendar_oauth_service.exchange_code_for_token(code, state)
        
        # Create connector with the token
        connector_name = token_data["connector_name"]
        
        # Add connector to manager
        await connector_manager.add_connector(
            name=connector_name,
            connector_type="calendar",
            credentials={
                "access_token": token_data["access_token"],
                "refresh_token": token_data.get("refresh_token"),
                "token_type": token_data.get("token_type", "Bearer"),
                "client_id": calendar_oauth_service.get_config()["client_id"],
                "client_secret": calendar_oauth_service.get_config()["client_secret"],
                "scope": token_data["scope"]
            },
            settings={
                "user_info": token_data["user_info"],
                "sync_interval_minutes": 60,
                "calendar_ids": ["primary"],  # Default to primary calendar
                "sync_days_back": 30,
                "sync_days_forward": 90,
                "include_cancelled": False
            },
            enabled=True
        )
        
        return {
            "success": True,
            "message": f"Google Calendar connector '{connector_name}' created successfully",
            "connector_name": connector_name,
            "user_info": token_data["user_info"]
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Calendar OAuth callback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calendar/calendars/{connector_name}")
async def get_calendar_list(connector_name: str):
    """Get available calendars for a Google Calendar connector"""
    try:
        # Get connector
        connector = connector_manager.connectors.get(connector_name)
        if not connector:
            raise HTTPException(status_code=404, detail="Connector not found")
        
        if connector.connector_type != "calendar":
            raise HTTPException(status_code=400, detail="Not a calendar connector")
        
        # Get access token
        access_token = connector.config.credentials.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token found")
        
        # Get calendar list
        calendars = await get_user_calendars(access_token)
        
        return {
            "success": True,
            "calendars": calendars,
            "total": len(calendars)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get calendars for {connector_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calendar/calendars/{connector_name}")
async def configure_calendar_list(
    connector_name: str, 
    calendar_ids: List[str]
):
    """Configure calendar IDs for a Google Calendar connector"""
    try:
        # Get connector from database and update settings
        from app.core.database import get_db, ConnectorConfig
        
        db = next(get_db())
        try:
            config = db.query(ConnectorConfig).filter(ConnectorConfig.name == connector_name).first()
            if not config:
                raise HTTPException(status_code=404, detail="Connector not found")
            
            # Update settings
            settings = config.settings or {}
            settings["calendar_ids"] = calendar_ids
            config.settings = settings
            config.enabled = True  # Enable connector now that calendars are configured
            
            db.commit()
            db.refresh(config)
            
        finally:
            db.close()
        
        # Recreate connector instance with new settings
        await connector_manager.remove_connector(connector_name)
        
        # Get fresh config from database for connector creation
        db = next(get_db())
        try:
            fresh_config = db.query(ConnectorConfig).filter(ConnectorConfig.name == connector_name).first()
            if fresh_config:
                await connector_manager.create_connector(fresh_config)
        finally:
            db.close()
        
        return {
            "success": True,
            "message": f"Configured {len(calendar_ids)} calendars for {connector_name}",
            "calendar_ids": calendar_ids
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to configure calendars for {connector_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def get_user_calendars(access_token: str) -> List[Dict[str, Any]]:
    """Get user's calendar list from Google Calendar API"""
    try:
        import aiohttp
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.googleapis.com/calendar/v3/users/me/calendarList",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    calendars = []
                    
                    for calendar in data.get("items", []):
                        calendars.append({
                            "id": calendar.get("id"),
                            "summary": calendar.get("summary"),
                            "description": calendar.get("description", ""),
                            "primary": calendar.get("primary", False),
                            "access_role": calendar.get("accessRole"),
                            "color_id": calendar.get("colorId")
                        })
                    
                    return calendars
                else:
                    logger.error(f"Failed to get calendars: {response.status}")
                    return []
                    
    except Exception as e:
        logger.error(f"Error getting user calendars: {e}")
        return []