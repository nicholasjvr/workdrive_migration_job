"""Transfer service orchestrating file migration from Org B to Org A."""
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from crm.crm_client import CRMClient
from workdrive.org_b_client import OrgBWorkDriveClient
from workdrive.org_a_client import OrgAWorkDriveClient
from utils.logger import MigrationLogger
from utils.file_stream import safe_filename


class TransferResult:
    """Result of a transfer operation."""
    
    def __init__(self, record_id: str):
        self.record_id = record_id
        self.folder_resolved: bool = False
        self.folder_id: Optional[str] = None
        self.folder_name: Optional[str] = None
        self.files_discovered: int = 0
        self.files_transferred: int = 0
        self.files_failed: int = 0
        self.checkbox_updated: bool = False
        self.success: bool = False
        self.error_message: Optional[str] = None


class TransferService:
    """Service for transferring files from Org B to Org A."""
    
    def __init__(
        self,
        crm_client: CRMClient,
        org_b_client: OrgBWorkDriveClient,
        org_a_client: OrgAWorkDriveClient,
        dest_folder_id: str,
        logger: MigrationLogger,
        dry_run: bool = False,
    ):
        """
        Initialize transfer service.
        
        Args:
            crm_client: CRM client for Org A
            org_b_client: WorkDrive client for Org B (source)
            org_a_client: WorkDrive client for Org A (destination)
            dest_folder_id: Destination folder ID in Org A
            logger: Migration logger
            dry_run: If True, don't actually transfer files or update CRM
        """
        self.crm_client = crm_client
        self.org_b_client = org_b_client
        self.org_a_client = org_a_client
        self.dest_folder_id = dest_folder_id
        self.logger = logger
        self.dry_run = dry_run
        
        # Folder mapping cache: orgB_folderId -> orgA_folderId
        self._folder_map: Dict[str, str] = {}
    
    def process_record(self, record: Dict) -> TransferResult:
        """
        Process a single CRM record: find folder, transfer files, update CRM.
        
        Args:
            record: CRM record dictionary
            
        Returns:
            TransferResult with outcome details
        """
        record_id = record.get("id")
        folder_name_field = self.crm_client.crm_config.folder_name_field_api_name
        folder_name = record.get(folder_name_field, "").strip()
        
        if not record_id:
            result = TransferResult("unknown")
            result.error_message = "Record missing ID"
            return result
        
        if not folder_name:
            result = TransferResult(record_id)
            result.error_message = "Folder name field is empty"
            self.logger.log_folder_not_found(record_id, "", "Folder name field is empty")
            return result
        
        result = TransferResult(record_id)
        result.folder_name = folder_name
        
        self.logger.log_record_start(record_id, folder_name)
        
        try:
            # Step 1: Resolve source folder
            folder_id = self._resolve_folder(folder_name, result)
            if not folder_id:
                return result
            
            result.folder_resolved = True
            result.folder_id = folder_id
            self.logger.log_folder_resolved(record_id, folder_id, folder_name)
            
            # Step 2: Recursively walk and transfer files
            self._transfer_folder_recursive(folder_id, result)
            
            # Step 3: Update CRM checkbox based on results
            if not self.dry_run:
                checkbox_value = result.files_transferred > 0
                try:
                    updated = self.crm_client.update_checkbox(record_id, checkbox_value)
                    result.checkbox_updated = updated
                except Exception as e:
                    self.logger.log_error(
                        f"Failed to update CRM checkbox for record {record_id}: {str(e)}"
                    )
            else:
                self.logger.log_info(
                    f"DRY-RUN: Would update checkbox to {result.files_transferred > 0} for record {record_id}"
                )
                result.checkbox_updated = True  # Mark as "updated" in dry-run
            
            # Determine overall success
            result.success = (
                result.folder_resolved and
                result.files_transferred > 0 and
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
            files_transferred=result.files_transferred,
            files_failed=result.files_failed,
            checkbox_updated=result.checkbox_updated,
        )
        
        return result
    
    def _resolve_folder(self, folder_name: str, result: TransferResult) -> Optional[str]:
        """
        Resolve folder by name with duplicate handling.
        
        Args:
            folder_name: Name of folder to find
            result: TransferResult to update
            
        Returns:
            Folder ID if found and unambiguous, None otherwise
        """
        try:
            matches = self.org_b_client.search_folder_by_name(folder_name)
            
            if not matches:
                result.error_message = f"Folder '{folder_name}' not found"
                self.logger.log_folder_not_found(
                    result.record_id, folder_name, "No matches found"
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
                    f"Multiple folders found for '{folder_name}' ({len(matches)} matches). "
                    f"Using most recently modified: {matches[0].get('id')}"
                )
            
            return matches[0].get("id")
        
        except Exception as e:
            result.error_message = f"Error resolving folder: {str(e)}"
            self.logger.log_error(
                f"Error resolving folder '{folder_name}': {str(e)}", exc_info=True
            )
            return None
    
    def _transfer_folder_recursive(self, folder_id: str, result: TransferResult):
        """
        Recursively transfer all files from a folder, mirroring structure.
        
        Args:
            folder_id: Source folder ID in Org B
            result: TransferResult to update
        """
        try:
            # Walk folder recursively
            items = self.org_b_client.walk_folder_recursive(folder_id)
            
            # Count files discovered
            file_items = [item for item in items if item[2] == "file"]
            result.files_discovered = len(file_items)
            self.logger.log_files_discovered(result.record_id, result.files_discovered)
            
            if not file_items:
                return
            
            # Process each file
            for path_parts, file_item, item_type in items:
                if item_type == "file":
                    self._transfer_file(path_parts, file_item, result)
                elif item_type == "folder":
                    # Ensure folder exists in destination (for structure mirroring)
                    self._ensure_destination_folder(path_parts[:-1], folder_id)
        
        except Exception as e:
            result.error_message = f"Error walking folder: {str(e)}"
            self.logger.log_error(
                f"Error walking folder {folder_id}: {str(e)}", exc_info=True
            )
    
    def _ensure_destination_folder(
        self, folder_path: Tuple[str, ...], source_root_folder_id: str
    ) -> Optional[str]:
        """
        Ensure destination folder path exists, creating if needed.
        
        Args:
            folder_path: Tuple of folder names forming the path
            source_root_folder_id: Source root folder ID (for mapping cache)
            
        Returns:
            Destination folder ID
        """
        if not folder_path:
            return self.dest_folder_id
        
        # Check cache first
        cache_key = f"{source_root_folder_id}:{':'.join(folder_path)}"
        if cache_key in self._folder_map:
            return self._folder_map[cache_key]
        
        # Build folder path under destination
        parent_id = self.dest_folder_id
        
        # Create each folder in the path
        for folder_name in folder_path:
            if self.dry_run:
                # In dry-run, just return a placeholder
                continue
            
            try:
                parent_id = self.org_a_client.ensure_folder_path(
                    parent_id, (folder_name,)
                )
            except Exception as e:
                self.logger.log_warning(
                    f"Failed to ensure folder '{folder_name}' under {parent_id}: {str(e)}"
                )
                return None
        
        # Cache the result
        self._folder_map[cache_key] = parent_id
        return parent_id
    
    def _transfer_file(
        self,
        path_parts: Tuple[str, ...],
        file_item: Dict,
        result: TransferResult,
    ):
        """
        Transfer a single file from Org B to Org A.
        
        Args:
            path_parts: Tuple of path components (including filename)
            file_item: File metadata dictionary
            result: TransferResult to update
        """
        file_id = file_item.get("id")
        file_name = file_item.get("name", "unknown")
        
        if not file_id:
            result.files_failed += 1
            self.logger.log_file_transfer_failure(
                result.record_id, file_name, "File missing ID"
            )
            return
        
        self.logger.log_file_transfer_start(result.record_id, file_name, file_id)
        
        if self.dry_run:
            self.logger.log_info(
                f"DRY-RUN: Would transfer file '{file_name}' (ID: {file_id})"
            )
            result.files_transferred += 1
            return
        
        try:
            # Determine destination folder
            folder_path = path_parts[:-1]
            dest_folder_id = self._ensure_destination_folder(
                folder_path, result.folder_id or ""
            )
            
            if not dest_folder_id:
                result.files_failed += 1
                self.logger.log_file_transfer_failure(
                    result.record_id, file_name, "Could not resolve destination folder"
                )
                return
            
            # Check for duplicate filename
            final_file_name = self._handle_duplicate_filename(
                dest_folder_id, file_name, result.record_id
            )
            
            # Download file from Org B
            file_content, metadata = self.org_b_client.download_file(file_id)
            
            # Upload file to Org A
            uploaded_file = self.org_a_client.upload_file(
                folder_id=dest_folder_id,
                file_name=final_file_name,
                file_content=file_content,
                content_type=metadata.get("contentType"),
            )
            
            result.files_transferred += 1
            file_size = len(file_content)
            self.logger.log_file_transfer_success(
                result.record_id,
                final_file_name,
                uploaded_file.get("id", "unknown"),
                file_size,
            )
        
        except Exception as e:
            result.files_failed += 1
            error_msg = str(e)
            self.logger.log_file_transfer_failure(
                result.record_id, file_name, error_msg
            )
            # Continue with next file (per-file error isolation)
    
    def _handle_duplicate_filename(
        self, folder_id: str, file_name: str, record_id: str
    ) -> str:
        """
        Check for duplicate filename and rename if necessary.
        
        Args:
            folder_id: Destination folder ID
            file_name: Original file name
            record_id: CRM record ID (for logging)
            
        Returns:
            Safe filename (possibly renamed)
        """
        try:
            existing_files = self.org_a_client.list_folder_files(folder_id)
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
