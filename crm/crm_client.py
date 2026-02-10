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

    def _json_or_error(self, response: requests.Response, action: str) -> Dict:
        """
        Parse JSON from a response, raising a helpful error if parsing fails.

        Zoho typically returns JSON. If the body is empty (e.g., 204) or non-JSON,
        surface the raw text to aid debugging.
        """
        try:
            return response.json()
        except ValueError:
            raw = (response.text or "").strip()
            if not raw:
                # Empty response body (common for some 204/empty responses)
                return {}
            raise ValueError(f"{action} returned non-JSON response: {raw[:500]}")

    def _extract_data_list(self, payload: Dict) -> List[Dict]:
        data = payload.get("data", [])
        return data if isinstance(data, list) else []

    @retry_with_backoff()
    def get_org_info(self) -> Dict:
        """
        Get CRM organization info for the authenticated connection.

        This is useful to confirm you're hitting the same org you see in the CRM UI.
        """
        url = f"{self.crm_base}/org"
        headers = self.auth_client.get_headers()
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.get(url, headers=headers, timeout=30)

        self._raise_for_status_with_details(response, "CRM org info (get_org_info)")
        return self._json_or_error(response, "CRM org info (get_org_info)")

    @retry_with_backoff()
    def get_current_user(self) -> Dict:
        """Get current (authorized) CRM user info."""
        url = f"{self.crm_base}/users"
        headers = self.auth_client.get_headers()
        params = {"type": "CurrentUser"}
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.get(url, headers=headers, params=params, timeout=30)

        self._raise_for_status_with_details(response, "CRM current user (get_current_user)")
        return self._json_or_error(response, "CRM current user (get_current_user)")

    @retry_with_backoff()
    def get_module_sample(self, per_page: int = 1) -> Dict:
        """
        Fetch a small sample page from the configured module.

        Useful to validate module API name and API access.
        """
        module = self.crm_config.module_api_name
        checkbox_field = self.crm_config.checkbox_field_api_name
        record_name_field = self.crm_config.record_name_field_api_name
        url_field = self.crm_config.workdrive_url_field_api_name
        folder_id_field = self.crm_config.workdrive_folder_id_field_api_name
        url = f"{self.crm_base}/{module}"
        headers = self.auth_client.get_headers()
        params = {
            "per_page": max(1, min(per_page, 200)),
            # Some orgs require 'fields' even for list endpoints.
            "fields": f"id,{checkbox_field},{record_name_field},{url_field},{folder_id_field}",
        }
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.get(url, headers=headers, params=params, timeout=30)

        self._raise_for_status_with_details(response, "CRM module sample (get_module_sample)")
        return self._json_or_error(response, "CRM module sample (get_module_sample)")

    def _escape_criteria_value(self, value: str) -> str:
        """
        Escape a value for use in Zoho CRM criteria.

        Use double quotes for values with spaces/special chars; escape embedded quotes.
        """
        v = str(value).replace('"', '\\"')
        return f'"{v}"'

    @retry_with_backoff()
    def find_record_id_by_name(self, name_value: str) -> Optional[str]:
        """
        Find a record ID in the configured module by exact name match.

        Uses the configured record_name_field_api_name for matching.
        Returns the first match (sorted by id desc by Zoho default).
        """
        module = self.crm_config.module_api_name
        record_name_field = self.crm_config.record_name_field_api_name

        url = f"{self.crm_base}/{module}/search"
        headers = self.auth_client.get_headers()

        criteria_value = self._escape_criteria_value(name_value)
        criteria = f"({record_name_field}:equals:{criteria_value})"

        params = {
            "criteria": criteria,
            "fields": f"id,{record_name_field}",
            "per_page": 2,
        }

        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.get(url, headers=headers, params=params, timeout=30)

        self._raise_for_status_with_details(response, "CRM search by name (find_record_id_by_name)")
        payload = self._json_or_error(response, "CRM search by name (find_record_id_by_name)")
        records = self._extract_data_list(payload)

        if not records:
            return None

        # If multiple matches, just pick the first and let higher-level logging handle ambiguity.
        return records[0].get("id")

    @retry_with_backoff()
    def update_record_fields(self, record_id: str, fields: Dict[str, object]) -> bool:
        """
        Update arbitrary fields for a record in the configured module.
        """
        module = self.crm_config.module_api_name
        update_url = f"{self.crm_base}/{module}/{record_id}"
        headers = self.auth_client.get_headers()
        data = {"data": [{"id": record_id, **fields}]}

        response = requests.put(update_url, headers=headers, json=data, timeout=30)
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.put(update_url, headers=headers, json=data, timeout=30)

        self._raise_for_status_with_details(response, "CRM update record fields (update_record_fields)")
        result = self._json_or_error(response, "CRM update record fields (update_record_fields)")
        updated_records = self._extract_data_list(result)
        return len(updated_records) > 0
    
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
        url_field = self.crm_config.workdrive_url_field_api_name
        folder_id_field = self.crm_config.workdrive_folder_id_field_api_name
        
        # Build search criteria
        # Checkbox = False
        criteria = f"({checkbox_field}:equals:false)"
        
        url = f"{self.crm_base}/{module}/search"
        headers = self.auth_client.get_headers()
        
        params = {
            "criteria": criteria,
            "fields": f"id,{checkbox_field},{record_name_field},{url_field},{folder_id_field}",
        }
        
        if limit:
            params["per_page"] = min(limit, 200)  # Zoho max is usually 200
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.get(url, headers=headers, params=params, timeout=30)
        
        self._raise_for_status_with_details(response, "CRM search (get_pending_records)")
        data = self._json_or_error(response, "CRM search (get_pending_records)")
        
        records = self._extract_data_list(data)
        
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
    def get_pending_records_debug(self, limit: int = 10) -> Dict:
        """
        Return debug info for the "pending records" search.

        Helps determine whether no records match the criteria, or records are being
        filtered out due to missing/incorrect Record Name field API name.
        """
        module = self.crm_config.module_api_name
        checkbox_field = self.crm_config.checkbox_field_api_name
        record_name_field = self.crm_config.record_name_field_api_name

        criteria = f"({checkbox_field}:equals:false)"
        url = f"{self.crm_base}/{module}/search"
        headers = self.auth_client.get_headers()

        params = {
            "criteria": criteria,
            "fields": f"id,{checkbox_field},{record_name_field}",
            "per_page": max(1, min(limit, 200)),
        }

        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.get(url, headers=headers, params=params, timeout=30)

        self._raise_for_status_with_details(response, "CRM search (get_pending_records_debug)")
        payload = self._json_or_error(response, "CRM search (get_pending_records_debug)")
        raw_records = self._extract_data_list(payload)

        missing_name = []
        kept = []
        for r in raw_records:
            name_val = r.get(record_name_field)
            if name_val is None or str(name_val).strip() == "":
                missing_name.append(r.get("id"))
            else:
                kept.append(r)

        # Keep debug output small and safe
        preview = [
            {
                "id": r.get("id"),
                checkbox_field: r.get(checkbox_field),
                record_name_field: r.get(record_name_field),
            }
            for r in kept[:5]
        ]

        return {
            "module": module,
            "criteria": criteria,
            "fields": ["id", checkbox_field, record_name_field],
            "raw_count": len(raw_records),
            "kept_count": len(kept),
            "missing_record_name_count": len(missing_name),
            "missing_record_name_ids_preview": missing_name[:5],
            "kept_preview": preview,
        }
    
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
        url_field = self.crm_config.workdrive_url_field_api_name
        folder_id_field = self.crm_config.workdrive_folder_id_field_api_name
        
        url = f"{self.crm_base}/{module}/{record_id}"
        headers = self.auth_client.get_headers()
        params = {
            "fields": f"id,{checkbox_field},{record_name_field},{url_field},{folder_id_field}",
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 401:
            headers = self.auth_client.get_headers(force_refresh=True)
            response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 404:
            return None

        if response.status_code == 204:
            return None
        
        self._raise_for_status_with_details(response, "CRM get record (get_record_by_id)")
        data = self._json_or_error(response, "CRM get record (get_record_by_id)")
        
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
        result = self._json_or_error(response, "CRM update checkbox (update_checkbox)")
        
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
        data = self._json_or_error(response, "CRM list attachments (get_attachments)")
        
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
        data = self._json_or_error(response, "CRM get attachment metadata (download_attachment)")
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
        
        return self.update_record_fields(
            record_id,
            {
                url_field: url,
                folder_id_field: folder_id,
            },
        )
