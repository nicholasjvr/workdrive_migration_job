"""Configuration management for Zoho WorkDrive migration service."""
import os
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class OrgAConfig:
    """Configuration for Organization A (CRM + WorkDrive destination)."""
    client_id: str
    client_secret: str
    refresh_token: str


@dataclass
class OrgBConfig:
    """Configuration for Organization B (WorkDrive source)."""
    client_id: str
    client_secret: str
    refresh_token: str
    team_folder_id: str  # Root folder ID for scoped searches


@dataclass
class CRMConfig:
    """CRM module configuration."""
    module_api_name: str
    checkbox_field_api_name: str
    record_name_field_api_name: str  # Field to match against WorkDrive folder names (typically "Name")
    workdrive_url_field_api_name: str  # Field to store WorkDrive folder URL
    workdrive_folder_id_field_api_name: str  # Field to store WorkDrive folder ID


@dataclass
class WorkDriveConfig:
    """WorkDrive configuration (kept for backward compatibility, not used in reversed flow)."""
    dest_folder_id: str  # Not used in reversed flow, but kept for config validation


@dataclass
class Config:
    """Main configuration container."""
    region: str
    org_a: OrgAConfig
    org_b: OrgBConfig
    crm: CRMConfig
    workdrive: WorkDriveConfig

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        region = os.getenv("ZOHO_REGION", "com").lower()
        
        # Validate required Org A variables
        org_a_client_id = os.getenv("ORG_A_CLIENT_ID")
        org_a_client_secret = os.getenv("ORG_A_CLIENT_SECRET")
        org_a_refresh_token = os.getenv("ORG_A_REFRESH_TOKEN")
        
        if not all([org_a_client_id, org_a_client_secret, org_a_refresh_token]):
            raise ValueError(
                "Missing required Org A configuration: "
                "ORG_A_CLIENT_ID, ORG_A_CLIENT_SECRET, ORG_A_REFRESH_TOKEN"
            )
        
        # Validate required Org B variables
        org_b_client_id = os.getenv("ORG_B_CLIENT_ID")
        org_b_client_secret = os.getenv("ORG_B_CLIENT_SECRET")
        org_b_refresh_token = os.getenv("ORG_B_REFRESH_TOKEN")
        org_b_team_folder_id = os.getenv("ORG_B_TEAM_FOLDER_ID")
        
        if not all([org_b_client_id, org_b_client_secret, org_b_refresh_token, org_b_team_folder_id]):
            raise ValueError(
                "Missing required Org B configuration: "
                "ORG_B_CLIENT_ID, ORG_B_CLIENT_SECRET, ORG_B_REFRESH_TOKEN, ORG_B_TEAM_FOLDER_ID"
            )
        
        # Validate CRM configuration
        crm_module = os.getenv("CRM_MODULE_API_NAME")
        crm_checkbox = os.getenv("CRM_CHECKBOX_FIELD_API_NAME")
        crm_record_name = os.getenv("CRM_RECORD_NAME_FIELD_API_NAME", "Name")  # Default to "Name"
        crm_workdrive_url = os.getenv("CRM_WORKDRIVE_URL_FIELD_API_NAME")
        crm_workdrive_folder_id = os.getenv("CRM_WORKDRIVE_FOLDER_ID_FIELD_API_NAME")
        
        if not all([crm_module, crm_checkbox, crm_workdrive_url, crm_workdrive_folder_id]):
            raise ValueError(
                "Missing required CRM configuration: "
                "CRM_MODULE_API_NAME, CRM_CHECKBOX_FIELD_API_NAME, "
                "CRM_WORKDRIVE_URL_FIELD_API_NAME, CRM_WORKDRIVE_FOLDER_ID_FIELD_API_NAME"
            )
        
        # WorkDrive destination (not used in reversed flow, but kept for backward compatibility)
        workdrive_dest = os.getenv("WORKDRIVE_DEST_FOLDER_ID", "")
        
        return cls(
            region=region,
            org_a=OrgAConfig(
                client_id=org_a_client_id,
                client_secret=org_a_client_secret,
                refresh_token=org_a_refresh_token,
            ),
            org_b=OrgBConfig(
                client_id=org_b_client_id,
                client_secret=org_b_client_secret,
                refresh_token=org_b_refresh_token,
                team_folder_id=org_b_team_folder_id,
            ),
            crm=CRMConfig(
                module_api_name=crm_module,
                checkbox_field_api_name=crm_checkbox,
                record_name_field_api_name=crm_record_name,
                workdrive_url_field_api_name=crm_workdrive_url,
                workdrive_folder_id_field_api_name=crm_workdrive_folder_id,
            ),
            workdrive=WorkDriveConfig(
                dest_folder_id=workdrive_dest,
            ),
        )
