"""WorkDrive client for Organization B (source)."""
import requests
from typing import List, Dict, Optional, Tuple
from auth.zoho_auth import ZohoAuthClient
from utils.retry import retry_with_backoff


class OrgBWorkDriveClient:
    """Client for accessing WorkDrive in Organization B."""
    
    def __init__(self, auth_client: ZohoAuthClient, team_folder_id: str):
        """
        Initialize Org B WorkDrive client.
        
        Args:
            auth_client: Authenticated ZohoAuthClient for Org B
            team_folder_id: Root Team Folder ID for scoped searches
        """
        self.auth_client = auth_client
        self.team_folder_id = team_folder_id
        self.api_endpoint = auth_client.get_api_endpoint()
        self.workdrive_base = f"{self.api_endpoint}/workdrive/api/v1"
    
    @retry_with_backoff()
    def search_folder_by_name(self, folder_name: str) -> List[Dict]:
        """
        Search for a folder by name within the configured Team Folder root.
        
        Args:
            folder_name: Name of folder to search for
            
        Returns:
            List of matching folder dictionaries
            
        Raises:
            requests.RequestException: On API errors
        """
        # Search within the team folder
        url = f"{self.workdrive_base}/folders"
        params = {
            "teamfolderid": self.team_folder_id,
            "search": folder_name,
            "type": "folder",
        }
        
        headers = self.auth_client.get_headers()
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        # Handle 401 by refreshing token and retrying once
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.get(url, headers=headers, params=params, timeout=30)
        
        response.raise_for_status()
        data = response.json()
        
        # Filter for case-insensitive exact match
        matches = []
        folder_name_lower = folder_name.lower()
        
        if "data" in data and isinstance(data["data"], list):
            for folder in data["data"]:
                if folder.get("name", "").lower() == folder_name_lower:
                    matches.append(folder)
        
        return matches
    
    @retry_with_backoff()
    def get_folder_contents(self, folder_id: str) -> Dict:
        """
        Get contents of a folder (files and subfolders).
        
        Args:
            folder_id: ID of folder to list
            
        Returns:
            Dictionary with 'files' and 'folders' lists
            
        Raises:
            requests.RequestException: On API errors
        """
        url = f"{self.workdrive_base}/folders/{folder_id}/files"
        headers = self.auth_client.get_headers()
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.get(url, headers=headers, timeout=30)
        
        response.raise_for_status()
        data = response.json()
        
        return {
            "files": data.get("data", {}).get("files", []),
            "folders": data.get("data", {}).get("folders", []),
        }
    
    @retry_with_backoff()
    def download_file(self, file_id: str) -> Tuple[bytes, Dict]:
        """
        Download a file by ID (streaming).
        
        Args:
            file_id: ID of file to download
            
        Returns:
            Tuple of (file_content_bytes, file_metadata_dict)
            
        Raises:
            requests.RequestException: On API errors
        """
        # First get file metadata
        metadata_url = f"{self.workdrive_base}/files/{file_id}"
        headers = self.auth_client.get_headers()
        
        metadata_response = requests.get(metadata_url, headers=headers, timeout=30)
        
        if metadata_response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            metadata_response = requests.get(metadata_url, headers=headers, timeout=30)
        
        metadata_response.raise_for_status()
        metadata = metadata_response.json().get("data", {})
        
        # Get download URL
        download_url = metadata.get("downloadUrl") or f"{self.workdrive_base}/files/{file_id}/download"
        
        # Download file content
        download_response = requests.get(download_url, headers=headers, stream=True, timeout=300)
        
        if download_response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            download_response = requests.get(download_url, headers=headers, stream=True, timeout=300)
        
        download_response.raise_for_status()
        content = download_response.content
        
        return content, metadata
    
    def walk_folder_recursive(
        self, folder_id: str, parent_path: Tuple[str, ...] = ()
    ) -> List[Tuple[Tuple[str, ...], Dict, str]]:
        """
        Recursively walk folder structure, yielding (path_parts, item_dict, item_type).
        
        Args:
            folder_id: ID of folder to walk
            parent_path: Tuple of path components leading to this folder
            
        Returns:
            List of tuples: (relative_path_parts, item_dict, "file" or "folder")
        """
        items = []
        
        try:
            contents = self.get_folder_contents(folder_id)
            
            # Process files
            for file_item in contents.get("files", []):
                file_name = file_item.get("name", "")
                path_parts = parent_path + (file_name,)
                items.append((path_parts, file_item, "file"))
            
            # Process subfolders recursively
            for folder_item in contents.get("folders", []):
                folder_name = folder_item.get("name", "")
                folder_item_id = folder_item.get("id")
                path_parts = parent_path + (folder_name,)
                
                # Add folder itself
                items.append((path_parts, folder_item, "folder"))
                
                # Recurse into subfolder
                if folder_item_id:
                    sub_items = self.walk_folder_recursive(folder_item_id, path_parts)
                    items.extend(sub_items)
        
        except Exception as e:
            # Log error but continue with other items
            # We'll handle this at the service level
            raise
        
        return items
