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
    folder_name_field_api_name: str


@dataclass
class WorkDriveConfig:
    """WorkDrive destination configuration."""
    dest_folder_id: str


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
        crm_folder_name = os.getenv("CRM_FOLDER_NAME_FIELD_API_NAME")
        
        if not all([crm_module, crm_checkbox, crm_folder_name]):
            raise ValueError(
                "Missing required CRM configuration: "
                "CRM_MODULE_API_NAME, CRM_CHECKBOX_FIELD_API_NAME, CRM_FOLDER_NAME_FIELD_API_NAME"
            )
        
        # Validate WorkDrive destination
        workdrive_dest = os.getenv("WORKDRIVE_DEST_FOLDER_ID")
        if not workdrive_dest:
            raise ValueError("Missing required WorkDrive configuration: WORKDRIVE_DEST_FOLDER_ID")
        
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
                folder_name_field_api_name=crm_folder_name,
            ),
            workdrive=WorkDriveConfig(
                dest_folder_id=workdrive_dest,
            ),
        )
