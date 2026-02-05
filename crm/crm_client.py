"""CRM client for Zoho CRM (Organization A)."""
import requests
from typing import List, Dict, Optional, Tuple
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

    def _raise_for_status_with_details(self, response: requests.Response, action: str) -> None:
        """
        Raise an HTTPError that includes Zoho's response body.

        Zoho often returns useful JSON error details even when status is 4xx/5xx.
        Requests' default raise_for_status message can be empty, so include the body.
        """
        if response.ok:
            return

        details: object
        try:
            details = response.json()
        except ValueError:
            details = (response.text or "").strip()

        raise requests.HTTPError(
            f"{action} failed (HTTP {response.status_code}). Response: {details}",
            response=response,
        )
    
    @retry_with_backoff()
    def get_pending_records(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get CRM records where checkbox is False and Record Name is not empty.
        
        Args:
            limit: Maximum number of records to return (None for all)
            
        Returns:
            List of record dictionaries
            
        Raises:
            requests.RequestException: On API errors
        """
        module = self.crm_config.module_api_name
        checkbox_field = self.crm_config.checkbox_field_api_name
        record_name_field = self.crm_config.record_name_field_api_name
        
        # Build search criteria
        # Checkbox = False
        criteria = f"({checkbox_field}:equals:false)"
        
        url = f"{self.crm_base}/{module}/search"
        headers = self.auth_client.get_headers()
        
        params = {
            "criteria": criteria,
            "fields": f"id,{checkbox_field},{record_name_field}",
        }
        
        if limit:
            params["per_page"] = min(limit, 200)  # Zoho max is usually 200
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.get(url, headers=headers, params=params, timeout=30)
        
        self._raise_for_status_with_details(response, "CRM search (get_pending_records)")
        data = response.json()
        
        records = data.get("data", [])
        
        # Filter out records with empty Record Name
        filtered_records = [
            record for record in records
            if record.get(record_name_field) and str(record.get(record_name_field)).strip()
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
        record_name_field = self.crm_config.record_name_field_api_name
        
        url = f"{self.crm_base}/{module}/{record_id}"
        headers = self.auth_client.get_headers()
        params = {
            "fields": f"id,{checkbox_field},{record_name_field}",
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 404:
            return None
        
        self._raise_for_status_with_details(response, "CRM get record (get_record_by_id)")
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
        
        self._raise_for_status_with_details(response, "CRM update checkbox (update_checkbox)")
        result = response.json()
        
        # Check if update was successful
        updated_records = result.get("data", [])
        return len(updated_records) > 0
    
    @retry_with_backoff()
    def get_attachments(self, record_id: str) -> List[Dict]:
        """
        Get attachments for a CRM record from Attachments Related List.
        
        Args:
            record_id: ID of record to get attachments for
            
        Returns:
            List of attachment dictionaries
            
        Raises:
            requests.RequestException: On API errors
        """
        module = self.crm_config.module_api_name
        url = f"{self.crm_base}/{module}/{record_id}/Attachments"
        headers = self.auth_client.get_headers()
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.get(url, headers=headers, timeout=30)
        
        self._raise_for_status_with_details(response, "CRM list attachments (get_attachments)")
        data = response.json()
        
        attachments = data.get("data", [])
        return attachments if isinstance(attachments, list) else []
    
    @retry_with_backoff()
    def download_attachment(self, attachment_id: str) -> Tuple[bytes, Dict]:
        """
        Download an attachment file.
        
        Args:
            attachment_id: ID of attachment to download
            
        Returns:
            Tuple of (file_content_bytes, attachment_metadata_dict)
            
        Raises:
            requests.RequestException: On API errors
        """
        # Get attachment metadata
        url = f"{self.crm_base}/Attachments/{attachment_id}"
        headers = self.auth_client.get_headers()
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.get(url, headers=headers, timeout=30)
        
        self._raise_for_status_with_details(response, "CRM get attachment metadata (download_attachment)")
        data = response.json()
        attachment = data.get("data", [])
        if isinstance(attachment, list) and len(attachment) > 0:
            attachment = attachment[0]
        
        # Get download URL
        download_url = attachment.get("downloadUrl") or attachment.get("file_url")
        
        if not download_url:
            # Try constructing download URL
            download_url = f"{self.crm_base}/Attachments/{attachment_id}/download"
        
        # Download file content
        download_response = requests.get(download_url, headers=headers, stream=True, timeout=300)
        
        if download_response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            download_response = requests.get(download_url, headers=headers, stream=True, timeout=300)
        
        self._raise_for_status_with_details(download_response, "CRM download attachment content (download_attachment)")
        content = download_response.content
        
        return content, attachment
    
    @retry_with_backoff()
    def update_workdrive_fields(self, record_id: str, url: str, folder_id: str) -> bool:
        """
        Update WorkDrive URL and folder ID fields in a CRM record.
        
        Args:
            record_id: ID of record to update
            url: WorkDrive folder URL
            folder_id: WorkDrive folder ID
            
        Returns:
            True if update was successful
            
        Raises:
            requests.RequestException: On API errors
        """
        module = self.crm_config.module_api_name
        url_field = self.crm_config.workdrive_url_field_api_name
        folder_id_field = self.crm_config.workdrive_folder_id_field_api_name
        
        update_url = f"{self.crm_base}/{module}/{record_id}"
        headers = self.auth_client.get_headers()
        data = {
            "data": [
                {
                    "id": record_id,
                    url_field: url,
                    folder_id_field: folder_id,
                }
            ]
        }
        
        response = requests.put(update_url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.put(update_url, headers=headers, json=data, timeout=30)
        
        self._raise_for_status_with_details(response, "CRM update workdrive fields (update_workdrive_fields)")
        result = response.json()
        
        # Check if update was successful
        updated_records = result.get("data", [])
        return len(updated_records) > 0
