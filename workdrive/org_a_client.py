"""WorkDrive client for Organization A (destination)."""
import requests
from typing import Dict, Optional, Tuple
from auth.zoho_auth import ZohoAuthClient
from utils.retry import retry_with_backoff


class OrgAWorkDriveClient:
    """Client for accessing WorkDrive in Organization A."""
    
    def __init__(self, auth_client: ZohoAuthClient):
        """
        Initialize Org A WorkDrive client.
        
        Args:
            auth_client: Authenticated ZohoAuthClient for Org A
        """
        self.auth_client = auth_client
        self.api_endpoint = auth_client.get_api_endpoint()
        self.workdrive_base = f"{self.api_endpoint}/workdrive/api/v1"
    
    @retry_with_backoff()
    def validate_folder_exists(self, folder_id: str) -> bool:
        """
        Validate that a folder exists and is accessible.
        
        Args:
            folder_id: ID of folder to validate
            
        Returns:
            True if folder exists and is accessible
            
        Raises:
            requests.RequestException: On API errors
        """
        url = f"{self.workdrive_base}/folders/{folder_id}"
        headers = self.auth_client.get_headers()
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 404:
            return False
        
        response.raise_for_status()
        return True
    
    @retry_with_backoff()
    def ensure_folder_path(
        self, parent_folder_id: str, folder_path: Tuple[str, ...]
    ) -> str:
        """
        Ensure a folder path exists under parent, creating missing folders.
        
        Args:
            parent_folder_id: ID of parent folder
            folder_path: Tuple of folder names forming the path
            
        Returns:
            ID of the final folder in the path
            
        Raises:
            requests.RequestException: On API errors
        """
        current_folder_id = parent_folder_id
        
        for folder_name in folder_path:
            # Check if folder already exists
            existing_id = self._find_folder_by_name(current_folder_id, folder_name)
            
            if existing_id:
                current_folder_id = existing_id
            else:
                # Create folder
                current_folder_id = self._create_folder(current_folder_id, folder_name)
        
        return current_folder_id
    
    @retry_with_backoff()
    def _find_folder_by_name(self, parent_folder_id: str, folder_name: str) -> Optional[str]:
        """
        Find a folder by name within a parent folder.
        
        Args:
            parent_folder_id: ID of parent folder
            folder_name: Name of folder to find
            
        Returns:
            Folder ID if found, None otherwise
        """
        url = f"{self.workdrive_base}/folders/{parent_folder_id}/files"
        params = {"type": "folder"}
        headers = self.auth_client.get_headers()
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.get(url, headers=headers, params=params, timeout=30)
        
        response.raise_for_status()
        data = response.json()
        
        folders = data.get("data", {}).get("folders", [])
        folder_name_lower = folder_name.lower()
        
        for folder in folders:
            if folder.get("name", "").lower() == folder_name_lower:
                return folder.get("id")
        
        return None
    
    @retry_with_backoff()
    def _create_folder(self, parent_folder_id: str, folder_name: str) -> str:
        """
        Create a folder under a parent folder.
        
        Args:
            parent_folder_id: ID of parent folder
            folder_name: Name of folder to create
            
        Returns:
            ID of created folder
            
        Raises:
            requests.RequestException: On API errors
        """
        url = f"{self.workdrive_base}/folders"
        headers = self.auth_client.get_headers()
        data = {
            "name": folder_name,
            "parentId": parent_folder_id,
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.post(url, headers=headers, json=data, timeout=30)
        
        response.raise_for_status()
        result = response.json()
        
        return result.get("data", {}).get("id")
    
    @retry_with_backoff()
    def list_folder_files(self, folder_id: str) -> list[Dict]:
        """
        List files in a folder (for duplicate checking).
        
        Args:
            folder_id: ID of folder to list
            
        Returns:
            List of file dictionaries
            
        Raises:
            requests.RequestException: On API errors
        """
        url = f"{self.workdrive_base}/folders/{folder_id}/files"
        params = {"type": "file"}
        headers = self.auth_client.get_headers()
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.get(url, headers=headers, params=params, timeout=30)
        
        response.raise_for_status()
        data = response.json()
        
        return data.get("data", {}).get("files", [])
    
    @retry_with_backoff()
    def upload_file(
        self,
        folder_id: str,
        file_name: str,
        file_content: bytes,
        content_type: Optional[str] = None,
    ) -> Dict:
        """
        Upload a file to a folder (streaming).
        
        Args:
            folder_id: ID of destination folder
            file_name: Name of file to upload
            file_content: File content as bytes
            content_type: MIME type (optional, will be inferred)
            
        Returns:
            Dictionary with uploaded file metadata
            
        Raises:
            requests.RequestException: On API errors
        """
        # Use multipart/form-data for file upload
        url = f"{self.workdrive_base}/files/upload"
        
        # Get upload URL first (some Zoho APIs require this)
        # Try direct upload first
        headers = self.auth_client.get_headers()
        # Remove Content-Type from headers for multipart
        upload_headers = {k: v for k, v in headers.items() if k.lower() != "content-type"}
        
        files = {
            "file": (file_name, file_content, content_type or "application/octet-stream")
        }
        data = {
            "parentId": folder_id,
        }
        
        response = requests.post(
            url, headers=upload_headers, files=files, data=data, timeout=300
        )
        
        if response.status_code == 401:
            upload_headers = {k: v for k, v in self.auth_client.get_headers(force_refresh=True).items() 
                            if k.lower() != "content-type"}
            response = requests.post(
                url, headers=upload_headers, files=files, data=data, timeout=300
            )
        
        response.raise_for_status()
        result = response.json()
        
        return result.get("data", {})
