"""Main CLI entrypoint for WorkDrive migration service."""
import sys
import argparse
from typing import Optional

from config import Config
from auth.zoho_auth import create_org_a_auth, create_org_b_auth
from crm.crm_client import CRMClient
from services.transfer_service import TransferService
from utils.logger import MigrationLogger


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Zoho WorkDrive Migration Service - Upload CRM attachments to Org B WorkDrive"
    )
    parser.add_argument(
        "--diagnose-crm",
        action="store_true",
        help="Print CRM org/user info to verify you're connected to the expected CRM org, then exit",
    )
    parser.add_argument(
        "--diagnose-pending",
        action="store_true",
        help="Print debug info for the pending-records search criteria, then exit",
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
    
    # Load configuration (treat only this as "configuration error")
    try:
        config = Config.from_env()
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    try:
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
        org_a_crm = CRMClient(org_a_auth, config.crm)
        org_b_crm = CRMClient(org_b_auth, config.crm)

        # Diagnostics mode (helps confirm tokens point at the expected org)
        if args.diagnose_crm:
            logger.log_info("CRM diagnostics:")
            logger.log_info(f"- Org A CRM base: {org_a_crm.crm_base}")
            logger.log_info(f"- Org B CRM base: {org_b_crm.crm_base}")
            logger.log_info(f"- Module API name: {config.crm.module_api_name}")
            logger.log_info(f"- Checkbox field API name: {config.crm.checkbox_field_api_name}")
            logger.log_info(f"- Record name field API name: {config.crm.record_name_field_api_name}")

            # Sample call (usually permitted with modules scopes)
            try:
                sample_a = org_a_crm.get_module_sample(per_page=1)
                logger.log_info(f"- Org A /{config.crm.module_api_name} sample response: {sample_a}")
            except Exception as e:
                logger.log_warning(f"- Org A module sample failed: {e}")

            try:
                sample_b = org_b_crm.get_module_sample(per_page=1)
                logger.log_info(f"- Org B /{config.crm.module_api_name} sample response: {sample_b}")
            except Exception as e:
                logger.log_warning(f"- Org B module sample failed: {e}")

            # These may require additional scopes (settings/users). Best-effort only.
            try:
                org_info = org_a_crm.get_org_info()
                logger.log_info(f"- Org A /org response: {org_info}")
            except Exception as e:
                logger.log_warning(f"- Org A /org not accessible with current scopes: {e}")

            try:
                current_user = org_a_crm.get_current_user()
                logger.log_info(f"- Org A /users?type=CurrentUser response: {current_user}")
            except Exception as e:
                logger.log_warning(f"- Org A CurrentUser not accessible with current scopes: {e}")
            return 0

        if args.diagnose_pending:
            dbg = org_a_crm.get_pending_records_debug(limit=10)
            logger.log_info(f"Pending-records search debug: {dbg}")
            return 0
        
        # Initialize transfer service
        transfer_service = TransferService(
            source_crm=org_a_crm,
            dest_crm=org_b_crm,
            logger=logger,
            dry_run=args.dry_run,
        )
        
        # Get records to process
        if args.record_id:
            record = org_a_crm.get_record_by_id(args.record_id)
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
            records = org_a_crm.get_pending_records(limit=args.limit)
        
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
        # Field-sync summary (no attachments in this flow)
        updated = sum(1 for r in results if getattr(r, "dest_updated", False))
        not_updated = len(results) - updated
        
        logger.log_info(f"Records processed: {len(results)}")
        logger.log_info(f"Records successful: {successful}")
        logger.log_info(f"Records failed: {failed}")
        logger.log_info(f"Org B records updated: {updated}")
        logger.log_info(f"Org B records not updated: {not_updated}")
        logger.log_info("=" * 60)
        
        # Return exit code based on results
        if failed > 0:
            return 1
        
        return 0
    
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
