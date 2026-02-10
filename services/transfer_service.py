"""Service that syncs WorkDrive fields from Org A CRM to Org B CRM."""

from typing import Dict, Optional

from crm.crm_client import CRMClient
from utils.logger import MigrationLogger


class TransferResult:
    """Result of a single record sync."""

    def __init__(self, source_record_id: str):
        self.source_record_id = source_record_id
        self.source_record_name: Optional[str] = None
        self.dest_record_id: Optional[str] = None
        self.workdrive_url: Optional[str] = None
        self.workdrive_folder_id: Optional[str] = None
        self.dest_updated: bool = False
        self.source_checkbox_updated: bool = False
        self.success: bool = False
        self.error_message: Optional[str] = None


class TransferService:
    """Service for syncing Org A -> Org B CRM fields."""
    
    def __init__(
        self,
        source_crm: CRMClient,
        dest_crm: CRMClient,
        logger: MigrationLogger,
        dry_run: bool = False,
    ):
        """
        Initialize transfer service.
        
        Args:
            source_crm: CRM client for Org A (source)
            dest_crm: CRM client for Org B (destination)
            logger: Migration logger
            dry_run: If True, don't write any changes to either org
        """
        self.source_crm = source_crm
        self.dest_crm = dest_crm
        self.logger = logger
        self.dry_run = dry_run
    
    def process_record(self, record: Dict) -> TransferResult:
        """
        Process a single Org A CRM record: find matching Org B record and sync fields.
        
        Args:
            record: CRM record dictionary
            
        Returns:
            TransferResult with outcome details
        """
        record_id = record.get("id")
        record_name_field = self.source_crm.crm_config.record_name_field_api_name
        record_name = str(record.get(record_name_field, "")).strip()
        
        if not record_id:
            result = TransferResult("unknown")
            result.error_message = "Record missing ID"
            return result
        
        if not record_name:
            result = TransferResult(record_id)
            result.error_message = f"Record Name field '{record_name_field}' is empty"
            self.logger.log_warning(f"Skipping record {record_id}: {result.error_message}")
            return result
        
        result = TransferResult(record_id)
        result.source_record_name = record_name
        
        self.logger.log_record_start(record_id, record_name)
        
        try:
            # Pull WorkDrive fields from source record
            url_field_src = self.source_crm.crm_config.workdrive_url_field_api_name
            folder_id_field_src = self.source_crm.crm_config.workdrive_folder_id_field_api_name

            workdrive_url = record.get(url_field_src)
            workdrive_folder_id = record.get(folder_id_field_src)

            result.workdrive_url = str(workdrive_url).strip() if workdrive_url else None
            result.workdrive_folder_id = str(workdrive_folder_id).strip() if workdrive_folder_id else None

            if not result.workdrive_url and not result.workdrive_folder_id:
                result.error_message = (
                    f"No WorkDrive values present on Org A record (fields: {url_field_src}, {folder_id_field_src})"
                )
                self.logger.log_warning(f"Skipping record {record_id}: {result.error_message}")
                return result

            # Find matching Org B record by exact name match
            dest_id = self.dest_crm.find_record_id_by_name(record_name)
            result.dest_record_id = dest_id

            if not dest_id:
                result.error_message = f"No matching Org B record found for name '{record_name}'"
                self.logger.log_warning(result.error_message)
                return result

            # Update Org B with values from Org A
            url_field_dest = self.dest_crm.crm_config.workdrive_url_field_api_name
            folder_id_field_dest = self.dest_crm.crm_config.workdrive_folder_id_field_api_name
            trace_field_dest = self.dest_crm.crm_config.record_updated_from_field_api_name

            if self.dry_run:
                self.logger.log_info(
                    f"DRY-RUN: Would update Org B record {dest_id} fields "
                    f"({url_field_dest}, {folder_id_field_dest}"
                    f"{', ' + trace_field_dest if trace_field_dest else ''})"
                )
                result.dest_updated = True
            else:
                fields_to_set = {}
                if result.workdrive_url:
                    fields_to_set[url_field_dest] = result.workdrive_url
                if result.workdrive_folder_id:
                    fields_to_set[folder_id_field_dest] = result.workdrive_folder_id
                if trace_field_dest:
                    # Store source record ID for traceability
                    fields_to_set[trace_field_dest] = record_id
                result.dest_updated = self.dest_crm.update_record_fields(dest_id, fields_to_set)

            # Mark Org A checkbox complete if destination updated
            if result.dest_updated:
                if self.dry_run:
                    self.logger.log_info(f"DRY-RUN: Would set Org A checkbox True for record {record_id}")
                    result.source_checkbox_updated = True
                else:
                    result.source_checkbox_updated = self.source_crm.update_checkbox(record_id, True)

            result.success = result.dest_updated and result.source_checkbox_updated
        
        except Exception as e:
            result.error_message = str(e)
            self.logger.log_error(
                f"Error processing record {record_id}: {str(e)}", exc_info=True
            )
        
        # Log completion
        self.logger.log_record_complete(
            record_id=record_id,
            success=result.success,
            files_transferred=0,
            files_failed=0,
            checkbox_updated=result.source_checkbox_updated,
        )
        
        return result
