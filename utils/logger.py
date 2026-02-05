"""Structured logging for the migration service."""
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class MigrationLogger:
    """Structured logger for migration operations."""
    
    def __init__(self, log_dir: str = "logs"):
        """
        Initialize logger with file and console handlers.
        
        Args:
            log_dir: Directory for log files
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger("workdrive_migration")
        self.logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (date-based filename)
        log_file = self.log_dir / f"migration_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
    
    def log_record_start(self, record_id: str, folder_name: str):
        """Log start of processing a CRM record."""
        self.logger.info(
            f"START RecordID={record_id} | FolderName={folder_name}"
        )
    
    def log_folder_resolved(self, record_id: str, folder_id: str, folder_name: str):
        """Log successful folder resolution."""
        self.logger.info(
            f"FOLDER_RESOLVED RecordID={record_id} | FolderID={folder_id} | FolderName={folder_name}"
        )
    
    def log_folder_not_found(self, record_id: str, folder_name: str, reason: str):
        """Log folder not found."""
        self.logger.warning(
            f"FOLDER_NOT_FOUND RecordID={record_id} | FolderName={folder_name} | Reason={reason}"
        )
    
    def log_files_discovered(self, record_id: str, file_count: int):
        """Log files discovered in folder."""
        self.logger.info(
            f"FILES_DISCOVERED RecordID={record_id} | Count={file_count}"
        )
    
    def log_file_transfer_start(self, record_id: str, file_name: str, file_id: str):
        """Log start of file transfer."""
        self.logger.info(
            f"TRANSFER_START RecordID={record_id} | FileName={file_name} | FileID={file_id}"
        )
    
    def log_file_transfer_success(
        self, record_id: str, file_name: str, dest_file_id: str, size: Optional[int] = None
    ):
        """Log successful file transfer."""
        size_str = f" | Size={size}" if size else ""
        self.logger.info(
            f"TRANSFER_SUCCESS RecordID={record_id} | FileName={file_name} | DestFileID={dest_file_id}{size_str}"
        )
    
    def log_file_transfer_failure(self, record_id: str, file_name: str, error: str):
        """Log file transfer failure."""
        self.logger.error(
            f"TRANSFER_FAILURE RecordID={record_id} | FileName={file_name} | Error={error}"
        )
    
    def log_record_complete(
        self,
        record_id: str,
        success: bool,
        files_transferred: int,
        files_failed: int,
        checkbox_updated: bool,
    ):
        """Log completion of record processing."""
        status = "SUCCESS" if success else "FAILED"
        self.logger.info(
            f"COMPLETE RecordID={record_id} | Status={status} | "
            f"Transferred={files_transferred} | Failed={files_failed} | "
            f"CheckboxUpdated={checkbox_updated}"
        )
    
    def log_error(self, message: str, exc_info: bool = False):
        """Log general error."""
        self.logger.error(message, exc_info=exc_info)
    
    def log_warning(self, message: str):
        """Log warning."""
        self.logger.warning(message)
    
    def log_info(self, message: str):
        """Log info message."""
        self.logger.info(message)
    
    def log_debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)
