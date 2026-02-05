"""CRM client for Zoho CRM (Organization A)."""
import requests
from typing import List, Dict, Optional
from auth.zoho_auth import ZohoAuthClient
from config import CRMConfig
from utils.retry import retry_with_backoff


class CRMClient:
    """Client for accessing Zoho CRM."""
    
    def __init__(self, auth_client: ZohoAuthClient, crm_config: CRMConfig):
        """
        Initialize CRM client.
        
        Args:
            auth_client: Authenticated ZohoAuthClient for Org A
            crm_config: CRM configuration
        """
        self.auth_client = auth_client
        self.crm_config = crm_config
        self.api_endpoint = auth_client.get_api_endpoint()
        self.crm_base = f"{self.api_endpoint}/crm/v3"
    
    @retry_with_backoff()
    def get_pending_records(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get CRM records where checkbox is False and folder name is not empty.
        
        Args:
            limit: Maximum number of records to return (None for all)
            
        Returns:
            List of record dictionaries
            
        Raises:
            requests.RequestException: On API errors
        """
        module = self.crm_config.module_api_name
        checkbox_field = self.crm_config.checkbox_field_api_name
        folder_field = self.crm_config.folder_name_field_api_name
        
        # Build search criteria
        # Checkbox = False AND Folder Name is not empty
        criteria = f"({checkbox_field}:equals:false)"
        
        url = f"{self.crm_base}/{module}/search"
        headers = self.auth_client.get_headers()
        
        params = {
            "criteria": criteria,
            "fields": f"id,{checkbox_field},{folder_field}",
        }
        
        if limit:
            params["per_page"] = min(limit, 200)  # Zoho max is usually 200
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.get(url, headers=headers, params=params, timeout=30)
        
        response.raise_for_status()
        data = response.json()
        
        records = data.get("data", [])
        
        # Filter out records with empty folder name
        filtered_records = [
            record for record in records
            if record.get(folder_field) and str(record.get(folder_field)).strip()
        ]
        
        # Apply limit if specified (after filtering)
        if limit and len(filtered_records) > limit:
            filtered_records = filtered_records[:limit]
        
        return filtered_records
    
    @retry_with_backoff()
    def get_record_by_id(self, record_id: str) -> Optional[Dict]:
        """
        Get a specific CRM record by ID.
        
        Args:
            record_id: ID of record to retrieve
            
        Returns:
            Record dictionary or None if not found
            
        Raises:
            requests.RequestException: On API errors
        """
        module = self.crm_config.module_api_name
        checkbox_field = self.crm_config.checkbox_field_api_name
        folder_field = self.crm_config.folder_name_field_api_name
        
        url = f"{self.crm_base}/{module}/{record_id}"
        headers = self.auth_client.get_headers()
        params = {
            "fields": f"id,{checkbox_field},{folder_field}",
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 404:
            return None
        
        response.raise_for_status()
        data = response.json()
        
        record = data.get("data", [])
        if isinstance(record, list) and len(record) > 0:
            return record[0]
        return record if record else None
    
    @retry_with_backoff()
    def update_checkbox(self, record_id: str, value: bool) -> bool:
        """
        Update the checkbox field for a CRM record.
        
        Args:
            record_id: ID of record to update
            value: New checkbox value (True/False)
            
        Returns:
            True if update was successful
            
        Raises:
            requests.RequestException: On API errors
        """
        module = self.crm_config.module_api_name
        checkbox_field = self.crm_config.checkbox_field_api_name
        
        url = f"{self.crm_base}/{module}/{record_id}"
        headers = self.auth_client.get_headers()
        data = {
            "data": [
                {
                    "id": record_id,
                    checkbox_field: value,
                }
            ]
        }
        
        response = requests.put(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.put(url, headers=headers, json=data, timeout=30)
        
        response.raise_for_status()
        result = response.json()
        
        # Check if update was successful
        updated_records = result.get("data", [])
        return len(updated_records) > 0
