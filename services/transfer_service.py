"""Transfer service orchestrating attachment upload from CRM to Org B WorkDrive."""
import time
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from crm.crm_client import CRMClient
from workdrive.org_b_client import OrgBWorkDriveClient
from utils.logger import MigrationLogger
from utils.file_stream import safe_filename


class TransferResult:
    """Result of a transfer operation."""
    
    def __init__(self, record_id: str):
        self.record_id = record_id
        self.folder_resolved: bool = False
        self.folder_id: Optional[str] = None
        self.folder_url: Optional[str] = None
        self.record_name: Optional[str] = None
        self.attachments_discovered: int = 0
        self.attachments_uploaded: int = 0
        self.attachments_failed: int = 0
        self.workdrive_fields_updated: bool = False
        self.checkbox_updated: bool = False
        self.success: bool = False
        self.error_message: Optional[str] = None


class TransferService:
    """Service for uploading CRM attachments to Org B WorkDrive."""
    
    def __init__(
        self,
        crm_client: CRMClient,
        org_b_client: OrgBWorkDriveClient,
        logger: MigrationLogger,
        dry_run: bool = False,
    ):
        """
        Initialize transfer service.
        
        Args:
            crm_client: CRM client for Org A
            org_b_client: WorkDrive client for Org B (destination)
            logger: Migration logger
            dry_run: If True, don't actually transfer files or update CRM
        """
        self.crm_client = crm_client
        self.org_b_client = org_b_client
        self.logger = logger
        self.dry_run = dry_run
    
    def process_record(self, record: Dict) -> TransferResult:
        """
        Process a single CRM record: find folder, upload attachments, update CRM.
        
        Args:
            record: CRM record dictionary
            
        Returns:
            TransferResult with outcome details
        """
        record_id = record.get("id")
        record_name_field = self.crm_client.crm_config.record_name_field_api_name
        record_name = record.get(record_name_field, "").strip()
        
        if not record_id:
            result = TransferResult("unknown")
            result.error_message = "Record missing ID"
            return result
        
        if not record_name:
            result = TransferResult(record_id)
            result.error_message = "Record Name field is empty"
            self.logger.log_folder_not_found(record_id, "", "Record Name field is empty")
            return result
        
        result = TransferResult(record_id)
        result.record_name = record_name
        
        self.logger.log_record_start(record_id, record_name)
        
        try:
            # Step 1: Resolve WorkDrive folder by Record Name
            folder_id = self._resolve_folder(record_name, result)
            if not folder_id:
                return result
            
            result.folder_resolved = True
            result.folder_id = folder_id
            
            # Step 2: Get folder URL
            if not self.dry_run:
                try:
                    folder_url = self.org_b_client.get_folder_url(folder_id)
                    result.folder_url = folder_url
                except Exception as e:
                    self.logger.log_warning(
                        f"Could not get folder URL for {folder_id}: {str(e)}"
                    )
                    # Continue anyway - URL is nice to have but not critical
            
            self.logger.log_folder_resolved(record_id, folder_id, record_name)
            
            # Step 3: Store WorkDrive URL and folder ID in CRM record
            if result.folder_url and not self.dry_run:
                try:
                    updated = self.crm_client.update_workdrive_fields(
                        record_id, result.folder_url, folder_id
                    )
                    result.workdrive_fields_updated = updated
                    if updated:
                        self.logger.log_info(
                            f"Stored WorkDrive URL and folder ID for record {record_id}"
                        )
                except Exception as e:
                    self.logger.log_error(
                        f"Failed to update WorkDrive fields for record {record_id}: {str(e)}"
                    )
            elif self.dry_run:
                self.logger.log_info(
                    f"DRY-RUN: Would store WorkDrive URL and folder ID for record {record_id}"
                )
                result.workdrive_fields_updated = True
            
            # Step 4: Fetch attachments from CRM
            attachments = []
            if not self.dry_run:
                try:
                    attachments = self.crm_client.get_attachments(record_id)
                except Exception as e:
                    self.logger.log_error(
                        f"Failed to fetch attachments for record {record_id}: {str(e)}"
                    )
                    result.error_message = f"Failed to fetch attachments: {str(e)}"
                    return result
            else:
                # In dry-run, simulate some attachments
                self.logger.log_info(
                    f"DRY-RUN: Would fetch attachments for record {record_id}"
                )
            
            result.attachments_discovered = len(attachments)
            self.logger.log_files_discovered(record_id, result.attachments_discovered)
            
            if not attachments:
                # No attachments to upload - still mark as success if folder was found
                result.success = result.folder_resolved and result.workdrive_fields_updated
                if not self.dry_run:
                    checkbox_value = False  # No files uploaded
                    try:
                        updated = self.crm_client.update_checkbox(record_id, checkbox_value)
                        result.checkbox_updated = updated
                    except Exception as e:
                        self.logger.log_error(
                            f"Failed to update CRM checkbox for record {record_id}: {str(e)}"
                        )
                else:
                    self.logger.log_info(
                        f"DRY-RUN: Would update checkbox to False (no attachments) for record {record_id}"
                    )
                    result.checkbox_updated = True
                
                self.logger.log_record_complete(
                    record_id=record_id,
                    success=result.success,
                    files_transferred=result.attachments_uploaded,
                    files_failed=result.attachments_failed,
                    checkbox_updated=result.checkbox_updated,
                )
                return result
            
            # Step 5: Upload each attachment to Org B WorkDrive folder
            self._upload_attachments(attachments, folder_id, result)
            
            # Step 6: Update CRM checkbox based on results
            if not self.dry_run:
                checkbox_value = result.attachments_uploaded > 0
                try:
                    updated = self.crm_client.update_checkbox(record_id, checkbox_value)
                    result.checkbox_updated = updated
                except Exception as e:
                    self.logger.log_error(
                        f"Failed to update CRM checkbox for record {record_id}: {str(e)}"
                    )
            else:
                self.logger.log_info(
                    f"DRY-RUN: Would update checkbox to {result.attachments_uploaded > 0} for record {record_id}"
                )
                result.checkbox_updated = True  # Mark as "updated" in dry-run
            
            # Determine overall success
            result.success = (
                result.folder_resolved and
                result.attachments_uploaded > 0 and
                result.checkbox_updated
            )
        
        except Exception as e:
            result.error_message = str(e)
            self.logger.log_error(
                f"Error processing record {record_id}: {str(e)}", exc_info=True
            )
        
        # Log completion
        self.logger.log_record_complete(
            record_id=record_id,
            success=result.success,
            files_transferred=result.attachments_uploaded,
            files_failed=result.attachments_failed,
            checkbox_updated=result.checkbox_updated,
        )
        
        return result
    
    def _resolve_folder(self, record_name: str, result: TransferResult) -> Optional[str]:
        """
        Resolve WorkDrive folder by Record Name with duplicate handling.
        
        Args:
            record_name: Record Name to match against folder names
            result: TransferResult to update
            
        Returns:
            Folder ID if found and unambiguous, None otherwise
        """
        try:
            matches = self.org_b_client.search_folder_by_name(record_name)
            
            if not matches:
                result.error_message = f"Folder matching '{record_name}' not found in Org B WorkDrive"
                self.logger.log_folder_not_found(
                    result.record_id, record_name, "No matches found in Org B WorkDrive"
                )
                return None
            
            if len(matches) == 1:
                return matches[0].get("id")
            
            # Multiple matches - apply resolution rules
            # Rule: Prefer latest modified folder
            matches.sort(
                key=lambda m: m.get("modifiedTime", 0),
                reverse=True
            )
            
            # If still ambiguous after sorting, log warning but use first
            if len(matches) > 1:
                self.logger.log_warning(
                    f"Multiple folders found for '{record_name}' ({len(matches)} matches). "
                    f"Using most recently modified: {matches[0].get('id')}"
                )
            
            return matches[0].get("id")
        
        except Exception as e:
            result.error_message = f"Error resolving folder: {str(e)}"
            self.logger.log_error(
                f"Error resolving folder '{record_name}': {str(e)}", exc_info=True
            )
            return None
    
    def _upload_attachments(
        self, attachments: List[Dict], folder_id: str, result: TransferResult
    ):
        """
        Upload attachments from CRM to Org B WorkDrive folder.
        
        Args:
            attachments: List of attachment dictionaries from CRM
            folder_id: Destination folder ID in Org B
            result: TransferResult to update
        """
        for attachment in attachments:
            attachment_id = attachment.get("id")
            attachment_name = attachment.get("file_name") or attachment.get("name", "unknown")
            
            if not attachment_id:
                result.attachments_failed += 1
                self.logger.log_file_transfer_failure(
                    result.record_id, attachment_name, "Attachment missing ID"
                )
                continue
            
            self.logger.log_file_transfer_start(
                result.record_id, attachment_name, attachment_id
            )
            
            if self.dry_run:
                self.logger.log_info(
                    f"DRY-RUN: Would upload attachment '{attachment_name}' (ID: {attachment_id}) "
                    f"to folder {folder_id}"
                )
                result.attachments_uploaded += 1
                continue
            
            try:
                # Download attachment from CRM
                file_content, attachment_metadata = self.crm_client.download_attachment(
                    attachment_id
                )
                
                # Get content type from metadata
                content_type = (
                    attachment_metadata.get("content_type") or
                    attachment_metadata.get("type") or
                    None
                )
                
                # Check for duplicate filename
                final_file_name = self._handle_duplicate_filename(
                    folder_id, attachment_name, result.record_id
                )
                
                # Upload to Org B WorkDrive
                uploaded_file = self.org_b_client.upload_file(
                    folder_id=folder_id,
                    file_name=final_file_name,
                    file_content=file_content,
                    content_type=content_type,
                )
                
                result.attachments_uploaded += 1
                file_size = len(file_content)
                self.logger.log_file_transfer_success(
                    result.record_id,
                    final_file_name,
                    uploaded_file.get("id", "unknown"),
                    file_size,
                )
            
            except Exception as e:
                result.attachments_failed += 1
                error_msg = str(e)
                self.logger.log_file_transfer_failure(
                    result.record_id, attachment_name, error_msg
                )
                # Continue with next attachment (per-attachment error isolation)
    
    def _handle_duplicate_filename(
        self, folder_id: str, file_name: str, record_id: str
    ) -> str:
        """
        Check for duplicate filename and rename if necessary.
        
        Args:
            folder_id: Destination folder ID in Org B
            file_name: Original file name
            record_id: CRM record ID (for logging)
            
        Returns:
            Safe filename (possibly renamed)
        """
        try:
            # Get existing files in folder
            contents = self.org_b_client.get_folder_contents(folder_id)
            existing_files = contents.get("files", [])
            existing_names = {f.get("name", "").lower() for f in existing_files}
            
            file_name_lower = file_name.lower()
            
            if file_name_lower not in existing_names:
                return safe_filename(file_name)
            
            # Duplicate found - rename with timestamp
            path = Path(file_name)
            stem = path.stem
            suffix = path.suffix
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = f"{stem}_{timestamp}{suffix}"
            
            self.logger.log_warning(
                f"Duplicate filename detected for '{file_name}' in record {record_id}. "
                f"Renaming to '{new_name}'"
            )
            
            return safe_filename(new_name)
        
        except Exception as e:
            # If we can't check for duplicates, just use safe filename
            self.logger.log_warning(
                f"Could not check for duplicate filename '{file_name}': {str(e)}"
            )
            return safe_filename(file_name)
