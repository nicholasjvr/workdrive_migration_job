"""Zoho OAuth authentication with refresh token handling."""
import time
import requests
from typing import Optional, Dict
from config import Config, OrgAConfig, OrgBConfig


class ZohoAuthClient:
    """OAuth client for Zoho API authentication."""
    
    # Region-specific token endpoints
    TOKEN_ENDPOINTS = {
        "com": "https://accounts.zoho.com/oauth/v2/token",
        "eu": "https://accounts.zoho.eu/oauth/v2/token",
        "in": "https://accounts.zoho.in/oauth/v2/token",
        "au": "https://accounts.zoho.com.au/oauth/v2/token",
        "jp": "https://accounts.zoho.jp/oauth/v2/token",
    }
    
    # Base API endpoints by region
    API_ENDPOINTS = {
        "com": "https://www.zohoapis.com",
        "eu": "https://www.zohoapis.eu",
        "in": "https://www.zohoapis.in",
        "au": "https://www.zohoapis.com.au",
        "jp": "https://www.zohoapis.jp",
    }
    
    def __init__(self, config: OrgAConfig | OrgBConfig, region: str):
        """
        Initialize OAuth client.
        
        Args:
            config: Organization configuration (OrgAConfig or OrgBConfig)
            region: Zoho region (com, eu, in, au, jp)
        """
        self.client_id = config.client_id
        self.client_secret = config.client_secret
        self.refresh_token = config.refresh_token
        self.region = region.lower()
        
        if self.region not in self.TOKEN_ENDPOINTS:
            raise ValueError(f"Unsupported region: {region}. Supported: {list(self.TOKEN_ENDPOINTS.keys())}")
        
        self.token_endpoint = self.TOKEN_ENDPOINTS[self.region]
        self.api_endpoint = self.API_ENDPOINTS[self.region]
        
        # In-memory token cache
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
    
    def get_access_token(self, force_refresh: bool = False) -> str:
        """
        Get a valid access token, refreshing if necessary.
        
        Args:
            force_refresh: Force token refresh even if current token is valid
            
        Returns:
            Valid access token
            
        Raises:
            requests.RequestException: If token refresh fails
        """
        # Return cached token if still valid
        if not force_refresh and self._access_token and time.time() < self._token_expires_at:
            return self._access_token
        
        # Refresh token
        response = requests.post(
            self.token_endpoint,
            data={
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            raise ValueError(f"Token refresh failed: {data.get('error_description', data['error'])}")
        
        self._access_token = data["access_token"]
        # Zoho tokens typically expire in 1 hour, but use expires_in if provided
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = time.time() + expires_in - 60  # Refresh 1 minute early
        
        return self._access_token
    
    def get_api_endpoint(self) -> str:
        """Get the base API endpoint for this region."""
        return self.api_endpoint
    
    def get_headers(self, force_refresh: bool = False) -> Dict[str, str]:
        """
        Get HTTP headers with authorization token.
        
        Args:
            force_refresh: Force token refresh
            
        Returns:
            Headers dictionary with Authorization header
        """
        token = self.get_access_token(force_refresh)
        return {
            "Authorization": f"Zoho-oauthtoken {token}",
            "Content-Type": "application/json",
        }


def create_org_a_auth(config: Config) -> ZohoAuthClient:
    """Create authentication client for Organization A."""
    return ZohoAuthClient(config.org_a, config.region)


def create_org_b_auth(config: Config) -> ZohoAuthClient:
    """Create authentication client for Organization B."""
    return ZohoAuthClient(config.org_b, config.region)
