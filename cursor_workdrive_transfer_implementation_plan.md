# Cursor Agent Implementation Plan

## Cross-Org Zoho WorkDrive File Transfer + Zoho CRM Status Update

------------------------------------------------------------------------

## 1. Project Overview

### Goal

Build a Python automation service that:

1.  Reads CRM records from Zoho CRM (Org A)
2.  Finds a matching folder in Zoho WorkDrive (Org B)
3.  Transfers files from Org B → Org A destination folder
4.  Updates a CRM checkbox indicating transfer success
5.  Logs and audits all activity

This solution must run locally or on-premise (non-cloud).

------------------------------------------------------------------------

## 2. System Architecture

### External Systems

  System                   Role
  ------------------------ -----------------------------------
  Zoho CRM (Org A)         Source records + checkbox updates
  Zoho WorkDrive (Org A)   Destination storage
  Zoho WorkDrive (Org B)   Source folders/files

------------------------------------------------------------------------

### Execution Environment

-   Python 3.11+
-   Runs via CLI or Windows Task Scheduler
-   Uses OAuth Self Client authentication
-   Configuration stored via `.env`

------------------------------------------------------------------------

## 3. High-Level Workflow

    CRM Records → Source Folder Name
            ↓
    Search Folder in WorkDrive Org B
            ↓
    List Files
            ↓
    Download Files (Streaming)
            ↓
    Upload Files to WorkDrive Org A
            ↓
    Update CRM Checkbox
            ↓
    Log Outcome

------------------------------------------------------------------------

## 4. Authentication Requirements

### Org A OAuth Scopes

    ZohoCRM.modules.ALL
    WorkDrive.files.CREATE
    WorkDrive.files.READ
    WorkDrive.files.UPDATE
    WorkDrive.teamfolders.READ

### Org B OAuth Scopes

    WorkDrive.files.READ
    WorkDrive.teamfolders.READ

------------------------------------------------------------------------

## 5. Required Project Structure

    project_root/
    │
    ├── main.py
    ├── config.py
    ├── auth/
    │   └── zoho_auth.py
    ├── crm/
    │   └── crm_client.py
    ├── workdrive/
    │   ├── org_a_client.py
    │   └── org_b_client.py
    ├── services/
    │   └── transfer_service.py
    ├── utils/
    │   ├── logger.py
    │   ├── retry.py
    │   └── file_stream.py
    ├── tests/
    │
    ├── requirements.txt
    ├── .env.example
    └── README.md

------------------------------------------------------------------------

## 6. Configuration Requirements

### `.env` Variables

    ZOHO_REGION=

    ORG_A_CLIENT_ID=
    ORG_A_CLIENT_SECRET=
    ORG_A_REFRESH_TOKEN=

    ORG_B_CLIENT_ID=
    ORG_B_CLIENT_SECRET=
    ORG_B_REFRESH_TOKEN=

    CRM_MODULE_API_NAME=
    CRM_CHECKBOX_FIELD_API_NAME=
    CRM_FOLDER_NAME_FIELD_API_NAME=

    WORKDRIVE_DEST_FOLDER_ID=

------------------------------------------------------------------------

## 7. Functional Requirements

### CRM Record Retrieval

Retrieve records where: - Checkbox = False - Folder Name field NOT empty

Minimum fields required: - CRM Record ID - Source Folder Name -
Destination Folder ID (optional override)

------------------------------------------------------------------------

### Folder Matching Rules (Org B)

1.  Case-insensitive exact match\
2.  If duplicates exist:
    -   Prefer known parent folder (if configured)
    -   Else choose latest modified folder\
3.  If ambiguity persists:
    -   Fail record
    -   Log ambiguity

------------------------------------------------------------------------

### File Transfer Rules

For each file: - Stream download - Stream upload - Capture uploaded file
metadata

------------------------------------------------------------------------

### Transfer Result Rules

  Condition            CRM Checkbox
  -------------------- --------------
  ≥1 Upload Success    TRUE
  No Files Found       FALSE
  All Uploads Failed   FALSE

------------------------------------------------------------------------

### Duplicate Filename Policy

Rename using:

    {original_name}_{timestamp}.{ext}

------------------------------------------------------------------------

## 8. Core Process Flow

1.  Fetch CRM Records\
2.  Resolve Source Folder\
3.  Enumerate Files\
4.  Transfer Files\
5.  Update CRM\
6.  Log Results

------------------------------------------------------------------------

## 9. Implementation Phases

### Phase 1 --- Setup & Authentication

-   OAuth refresh token handler\
-   Region-aware Zoho endpoints\
-   Environment config loader

### Phase 2 --- WorkDrive Clients

Org B: - Folder search - File listing - File download streaming

Org A: - File upload streaming - Destination folder validation

### Phase 3 --- CRM Client

-   Record search via criteria\
-   Checkbox update

### Phase 4 --- Transfer Service

-   Full orchestration\
-   Duplicate filename handling\
-   Retry/backoff logic\
-   Per-file error isolation

### Phase 5 --- CLI Entry Script

`main.py` must support:

    --dry-run
    --record-id
    --limit

------------------------------------------------------------------------

## 10. Logging Requirements

Logs must include: - timestamp - CRM record ID - Folder matched - Files
discovered - Files transferred - Failures - Final status

Logs must be: - File based - Console based

------------------------------------------------------------------------

## 11. Error Handling Requirements

Retry for: - HTTP 429 - HTTP 5xx - OAuth refresh failure

Retries: - 3 attempts - Exponential backoff

------------------------------------------------------------------------

## 12. Testing Requirements

Test scenarios: - Folder found with files - Folder found without files -
Folder not found - Duplicate folder results - Upload partial failure -
Large file transfer

------------------------------------------------------------------------

## 13. Security Requirements

-   Secrets loaded from environment
-   No hardcoded credentials
-   Token refresh storage isolation
-   No logging of access tokens

------------------------------------------------------------------------

## 14. Acceptance Criteria

✔ Correct folder resolved\
✔ Files transfer successfully\
✔ CRM checkbox updates correctly\
✔ All scenarios logged\
✔ Dry-run mode works\
✔ Supports batch processing\
✔ Handles retry and failures gracefully

------------------------------------------------------------------------

## 15. Deployment Constraints

System MUST: - Run locally or on internal server - Be schedulable via
Windows Task Scheduler

------------------------------------------------------------------------

## 16. Non-Functional Requirements

-   Support large file streaming\
-   Multi-record batch execution\
-   Safe completion if interrupted\
-   Idempotent where possible

------------------------------------------------------------------------

## 17. Deliverables Expected From Cursor Agent

1.  Full project scaffold\
2.  Production-ready Python modules\
3.  Requirements file\
4.  README usage instructions\
5.  Environment template\
6.  Test stubs\
7.  Logging system\
8.  CLI entrypoint
