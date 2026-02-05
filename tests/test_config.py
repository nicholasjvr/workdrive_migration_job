"""Tests for configuration management."""
import pytest
import os
from unittest.mock import patch
from config import Config, OrgAConfig, OrgBConfig, CRMConfig, WorkDriveConfig


def test_config_from_env_complete():
    """Test loading complete configuration from environment."""
    env_vars = {
        "ZOHO_REGION": "com",
        "ORG_A_CLIENT_ID": "org_a_client",
        "ORG_A_CLIENT_SECRET": "org_a_secret",
        "ORG_A_REFRESH_TOKEN": "org_a_token",
        "ORG_B_CLIENT_ID": "org_b_client",
        "ORG_B_CLIENT_SECRET": "org_b_secret",
        "ORG_B_REFRESH_TOKEN": "org_b_token",
        "ORG_B_TEAM_FOLDER_ID": "team_folder_123",
        "CRM_MODULE_API_NAME": "Contacts",
        "CRM_CHECKBOX_FIELD_API_NAME": "Transfer_Complete",
        "CRM_FOLDER_NAME_FIELD_API_NAME": "Source_Folder_Name",
        "WORKDRIVE_DEST_FOLDER_ID": "dest_folder_123",
    }
    
    with patch.dict(os.environ, env_vars):
        config = Config.from_env()
        
        assert config.region == "com"
        assert config.org_a.client_id == "org_a_client"
        assert config.org_b.team_folder_id == "team_folder_123"
        assert config.crm.module_api_name == "Contacts"
        assert config.workdrive.dest_folder_id == "dest_folder_123"


def test_config_missing_org_a():
    """Test that missing Org A config raises error."""
    env_vars = {
        "ZOHO_REGION": "com",
        # Missing Org A vars
    }
    
    with patch.dict(os.environ, env_vars, clear=True):
        with pytest.raises(ValueError, match="Missing required Org A"):
            Config.from_env()


def test_config_missing_org_b():
    """Test that missing Org B config raises error."""
    env_vars = {
        "ZOHO_REGION": "com",
        "ORG_A_CLIENT_ID": "org_a_client",
        "ORG_A_CLIENT_SECRET": "org_a_secret",
        "ORG_A_REFRESH_TOKEN": "org_a_token",
        # Missing Org B vars
    }
    
    with patch.dict(os.environ, env_vars, clear=True):
        with pytest.raises(ValueError, match="Missing required Org B"):
            Config.from_env()


def test_config_missing_crm():
    """Test that missing CRM config raises error."""
    env_vars = {
        "ZOHO_REGION": "com",
        "ORG_A_CLIENT_ID": "org_a_client",
        "ORG_A_CLIENT_SECRET": "org_a_secret",
        "ORG_A_REFRESH_TOKEN": "org_a_token",
        "ORG_B_CLIENT_ID": "org_b_client",
        "ORG_B_CLIENT_SECRET": "org_b_secret",
        "ORG_B_REFRESH_TOKEN": "org_b_token",
        "ORG_B_TEAM_FOLDER_ID": "team_folder_123",
        # Missing CRM vars
    }
    
    with patch.dict(os.environ, env_vars, clear=True):
        with pytest.raises(ValueError, match="Missing required CRM"):
            Config.from_env()


def test_config_default_region():
    """Test that region defaults to 'com' if not specified."""
    env_vars = {
        # ZOHO_REGION not set
        "ORG_A_CLIENT_ID": "org_a_client",
        "ORG_A_CLIENT_SECRET": "org_a_secret",
        "ORG_A_REFRESH_TOKEN": "org_a_token",
        "ORG_B_CLIENT_ID": "org_b_client",
        "ORG_B_CLIENT_SECRET": "org_b_secret",
        "ORG_B_REFRESH_TOKEN": "org_b_token",
        "ORG_B_TEAM_FOLDER_ID": "team_folder_123",
        "CRM_MODULE_API_NAME": "Contacts",
        "CRM_CHECKBOX_FIELD_API_NAME": "Transfer_Complete",
        "CRM_FOLDER_NAME_FIELD_API_NAME": "Source_Folder_Name",
        "WORKDRIVE_DEST_FOLDER_ID": "dest_folder_123",
    }
    
    with patch.dict(os.environ, env_vars, clear=True):
        config = Config.from_env()
        assert config.region == "com"
