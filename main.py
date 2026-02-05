"""Main CLI entrypoint for WorkDrive migration service."""
import sys
import argparse
from typing import Optional

from config import Config
from auth.zoho_auth import create_org_a_auth, create_org_b_auth
from crm.crm_client import CRMClient
from workdrive.org_b_client import OrgBWorkDriveClient
from services.transfer_service import TransferService
from utils.logger import MigrationLogger


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Zoho WorkDrive Migration Service - Upload CRM attachments to Org B WorkDrive"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making actual changes (no file transfers, no CRM updates)",
    )
    parser.add_argument(
        "--record-id",
        type=str,
        help="Process only a specific CRM record ID",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of records to process",
    )
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = Config.from_env()
        
        # Initialize logger
        logger = MigrationLogger()
        logger.log_info("=" * 60)
        logger.log_info("WorkDrive Migration Service Starting")
        logger.log_info(f"Dry-run mode: {args.dry_run}")
        if args.record_id:
            logger.log_info(f"Processing specific record: {args.record_id}")
        if args.limit:
            logger.log_info(f"Record limit: {args.limit}")
        logger.log_info("=" * 60)
        
        # Initialize authentication clients
        org_a_auth = create_org_a_auth(config)
        org_b_auth = create_org_b_auth(config)
        
        # Initialize clients
        crm_client = CRMClient(org_a_auth, config.crm)
        org_b_client = OrgBWorkDriveClient(org_b_auth, config.org_b.team_folder_id)
        
        # Initialize transfer service
        transfer_service = TransferService(
            crm_client=crm_client,
            org_b_client=org_b_client,
            logger=logger,
            dry_run=args.dry_run,
        )
        
        # Get records to process
        if args.record_id:
            record = crm_client.get_record_by_id(args.record_id)
            if not record:
                logger.log_error(f"Record {args.record_id} not found")
                return 1
            
            record_name_field = config.crm.record_name_field_api_name
            record_name = record.get(record_name_field, "").strip()
            
            if not record_name:
                logger.log_error(
                    f"Record {args.record_id} has empty Record Name field"
                )
                return 1
            
            records = [record]
        else:
            records = crm_client.get_pending_records(limit=args.limit)
        
        if not records:
            logger.log_info("No records to process")
            return 0
        
        logger.log_info(f"Processing {len(records)} record(s)")
        
        # Process each record
        results = []
        for record in records:
            result = transfer_service.process_record(record)
            results.append(result)
        
        # Summary
        logger.log_info("=" * 60)
        logger.log_info("Migration Summary")
        logger.log_info("=" * 60)
        
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        total_attachments_uploaded = sum(r.attachments_uploaded for r in results)
        total_attachments_failed = sum(r.attachments_failed for r in results)
        
        logger.log_info(f"Records processed: {len(results)}")
        logger.log_info(f"Records successful: {successful}")
        logger.log_info(f"Records failed: {failed}")
        logger.log_info(f"Total attachments uploaded: {total_attachments_uploaded}")
        logger.log_info(f"Total attachments failed: {total_attachments_failed}")
        logger.log_info("=" * 60)
        
        # Return exit code based on results
        if failed > 0:
            return 1
        
        return 0
    
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
