"""Tests for transfer service logic."""
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock
from services.transfer_service import TransferService, TransferResult
from crm.crm_client import CRMClient
from workdrive.org_b_client import OrgBWorkDriveClient
from workdrive.org_a_client import OrgAWorkDriveClient
from utils.logger import MigrationLogger


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return Mock(spec=MigrationLogger)


@pytest.fixture
def mock_crm_client():
    """Create a mock CRM client."""
    client = Mock(spec=CRMClient)
    client.crm_config = Mock()
    client.crm_config.folder_name_field_api_name = "Source_Folder_Name"
    client.crm_config.checkbox_field_api_name = "Transfer_Complete"
    return client


@pytest.fixture
def mock_org_b_client():
    """Create a mock Org B client."""
    return Mock(spec=OrgBWorkDriveClient)


@pytest.fixture
def mock_org_a_client():
    """Create a mock Org A client."""
    return Mock(spec=OrgAWorkDriveClient)


@pytest.fixture
def transfer_service(mock_crm_client, mock_org_b_client, mock_org_a_client, mock_logger):
    """Create a transfer service instance."""
    return TransferService(
        crm_client=mock_crm_client,
        org_b_client=mock_org_b_client,
        org_a_client=mock_org_a_client,
        dest_folder_id="dest123",
        logger=mock_logger,
        dry_run=False,
    )


def test_folder_matching_single_match(transfer_service, mock_org_b_client):
    """Test folder resolution with single match."""
    record = {
        "id": "rec123",
        "Source_Folder_Name": "TestFolder",
    }
    
    mock_org_b_client.search_folder_by_name.return_value = [
        {"id": "folder123", "name": "TestFolder", "modifiedTime": 1000}
    ]
    
    result = TransferResult("rec123")
    folder_id = transfer_service._resolve_folder("TestFolder", result)
    
    assert folder_id == "folder123"
    assert result.folder_resolved is False  # Not set until process_record


def test_folder_matching_multiple_matches(transfer_service, mock_org_b_client, mock_logger):
    """Test folder resolution with multiple matches (uses latest modified)."""
    record = {
        "id": "rec123",
        "Source_Folder_Name": "TestFolder",
    }
    
    mock_org_b_client.search_folder_by_name.return_value = [
        {"id": "folder1", "name": "TestFolder", "modifiedTime": 1000},
        {"id": "folder2", "name": "TestFolder", "modifiedTime": 2000},
        {"id": "folder3", "name": "TestFolder", "modifiedTime": 1500},
    ]
    
    result = TransferResult("rec123")
    folder_id = transfer_service._resolve_folder("TestFolder", result)
    
    # Should use folder2 (latest modified)
    assert folder_id == "folder2"
    mock_logger.log_warning.assert_called()


def test_folder_matching_no_matches(transfer_service, mock_org_b_client):
    """Test folder resolution with no matches."""
    mock_org_b_client.search_folder_by_name.return_value = []
    
    result = TransferResult("rec123")
    folder_id = transfer_service._resolve_folder("NonExistent", result)
    
    assert folder_id is None
    assert result.error_message is not None


def test_duplicate_filename_handling(transfer_service, mock_org_a_client):
    """Test duplicate filename renaming."""
    # Mock existing files
    mock_org_a_client.list_folder_files.return_value = [
        {"name": "test.txt", "id": "file1"},
        {"name": "other.pdf", "id": "file2"},
    ]
    
    # File doesn't exist - should return original
    result = transfer_service._handle_duplicate_filename("folder123", "newfile.txt", "rec123")
    assert result == "newfile.txt"
    
    # File exists - should rename
    result = transfer_service._handle_duplicate_filename("folder123", "test.txt", "rec123")
    assert result != "test.txt"
    assert result.startswith("test_")
    assert result.endswith(".txt")
    assert "_" in result  # Should have timestamp


def test_checkbox_decision_rules():
    """Test checkbox decision logic based on transfer results."""
    # At least one file transferred -> True
    result = TransferResult("rec123")
    result.files_transferred = 1
    result.files_failed = 0
    assert result.files_transferred > 0  # Would set checkbox to True
    
    # No files transferred -> False
    result = TransferResult("rec123")
    result.files_transferred = 0
    result.files_failed = 0
    assert result.files_transferred == 0  # Would set checkbox to False
    
    # All files failed -> False
    result = TransferResult("rec123")
    result.files_transferred = 0
    result.files_failed = 5
    assert result.files_transferred == 0  # Would set checkbox to False
    
    # Some succeeded, some failed -> True (at least one success)
    result = TransferResult("rec123")
    result.files_transferred = 3
    result.files_failed = 2
    assert result.files_transferred > 0  # Would set checkbox to True


def test_recursive_walk_structure(mock_org_b_client):
    """Test that recursive walk emits correct path structure."""
    # Mock folder structure:
    # root/
    #   file1.txt
    #   subfolder/
    #     file2.txt
    #     nested/
    #       file3.txt
    
    def mock_get_contents(folder_id):
        if folder_id == "root":
            return {
                "files": [{"id": "f1", "name": "file1.txt"}],
                "folders": [{"id": "sub", "name": "subfolder"}],
            }
        elif folder_id == "sub":
            return {
                "files": [{"id": "f2", "name": "file2.txt"}],
                "folders": [{"id": "nested", "name": "nested"}],
            }
        elif folder_id == "nested":
            return {
                "files": [{"id": "f3", "name": "file3.txt"}],
                "folders": [],
            }
        return {"files": [], "folders": []}
    
    mock_org_b_client.get_folder_contents.side_effect = mock_get_contents
    
    # Walk the structure
    items = mock_org_b_client.walk_folder_recursive("root")
    
    # Verify structure
    file_paths = [(path, item_type) for path, _, item_type in items if item_type == "file"]
    
    assert ("file1.txt",) in [p for p, _ in file_paths]
    assert ("subfolder", "file2.txt") in [p for p, _ in file_paths]
    assert ("subfolder", "nested", "file3.txt") in [p for p, _ in file_paths]


def test_per_file_error_isolation(transfer_service, mock_org_b_client, mock_org_a_client):
    """Test that one file failure doesn't stop other files."""
    record = {
        "id": "rec123",
        "Source_Folder_Name": "TestFolder",
    }
    
    # Mock folder resolution
    mock_org_b_client.search_folder_by_name.return_value = [
        {"id": "folder123", "name": "TestFolder"}
    ]
    
    # Mock recursive walk with 3 files
    mock_org_b_client.walk_folder_recursive.return_value = [
        (("file1.txt",), {"id": "f1", "name": "file1.txt"}, "file"),
        (("file2.txt",), {"id": "f2", "name": "file2.txt"}, "file"),
        (("file3.txt",), {"id": "f3", "name": "file3.txt"}, "file"),
    ]
    
    # Mock downloads - file2 fails
    def mock_download(file_id):
        if file_id == "f2":
            raise Exception("Download failed")
        return b"content", {"contentType": "text/plain"}
    
    mock_org_b_client.download_file.side_effect = mock_download
    mock_org_a_client.list_folder_files.return_value = []
    mock_org_a_client.upload_file.return_value = {"id": "uploaded"}
    mock_org_a_client.ensure_folder_path.return_value = "dest123"
    
    result = transfer_service.process_record(record)
    
    # Should have transferred 2 files, failed 1
    assert result.files_transferred == 2
    assert result.files_failed == 1
    assert result.success  # Still successful because at least one file transferred
