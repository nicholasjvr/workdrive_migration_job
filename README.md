# Zoho CRM Field Sync Service

A Python automation service that copies WorkDrive reference fields (URL + Folder ID) from **Zoho CRM Org A** to **Zoho CRM Org B** by matching records on the configured Record Name field, and updates a checkbox in Org A to track completion.

## Features

- **CRM → CRM Sync**: Copies WorkDrive URL + Folder ID fields from Org A to Org B
- **Record Matching**: Matches by the configured Record Name field (exact match)
- **Completion Tracking**: Updates a checkbox field in Org A when Org B is updated
- **Retry Logic**: Automatic retry with exponential backoff for transient errors
- **Dry-Run Mode**: Test the service without making actual changes
- **Comprehensive Logging**: Detailed logs for all operations

## Requirements

- Python 3.11+
- Zoho OAuth Self Client credentials for both organizations
- Access to Zoho CRM (Org A + Org B)

## Installation

1. Clone or download this repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in your configuration:
```bash
copy .env.example .env
```

4. Edit `.env` with your Zoho credentials and configuration

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# Zoho Region (com, eu, in, au, jp)
ZOHO_REGION=com

# Organization A (CRM - Source of WorkDrive fields)
ORG_A_CLIENT_ID=your_org_a_client_id
ORG_A_CLIENT_SECRET=your_org_a_client_secret
ORG_A_REFRESH_TOKEN=your_org_a_refresh_token

# Organization B (CRM - Destination to populate)
ORG_B_CLIENT_ID=your_org_b_client_id
ORG_B_CLIENT_SECRET=your_org_b_client_secret
ORG_B_REFRESH_TOKEN=your_org_b_refresh_token

# CRM Configuration
CRM_MODULE_API_NAME=Contacts
CRM_CHECKBOX_FIELD_API_NAME=Transfer_Complete
CRM_RECORD_NAME_FIELD_API_NAME=Name
CRM_WORKDRIVE_URL_FIELD_API_NAME=WorkDrive_URL
CRM_WORKDRIVE_FOLDER_ID_FIELD_API_NAME=WorkDrive_Folder_ID
CRM_RECORD_UPDATED_FROM_FIELD_API_NAME=Record_Updated_From
```

### OAuth Setup

You need to create OAuth Self Clients in both Zoho organizations:

**Org A Scopes:**
- `ZohoCRM.modules.ALL`

**Org B Scopes:**
- `ZohoCRM.modules.ALL`

Generate refresh tokens for both clients and add them to your `.env` file.

## Usage

### Basic Usage

Process all pending CRM records:
```bash
python main.py
```

### Dry-Run Mode

Test without making changes:
```bash
python main.py --dry-run
```

### Process Specific Record

Process a single CRM record by ID:
```bash
python main.py --record-id 1234567890123456789
```

### Limit Records

Process only the first N records:
```bash
python main.py --limit 10
```

### Windows Task Scheduler

To run automatically on a schedule:

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., daily at 2 AM)
4. Action: Start a program
5. Program: `python` (or full path to Python executable)
6. Arguments: `C:\path\to\main.py --limit 50`
7. Start in: `C:\path\to\project\directory`

## How It Works

1. **Fetch CRM Records**: Retrieves records where the checkbox is `False` and Record Name is not empty
2. **Resolve WorkDrive Folder**: Searches for matching folder in Org B WorkDrive by Record Name (scoped to configured Team Folder)
3. **Store WorkDrive Info**: Stores WorkDrive folder URL and folder ID in CRM record fields
4. **Fetch Attachments**: Retrieves all attachments from the CRM record's Attachments Related List
5. **Upload Attachments**: Uploads each attachment to the matched WorkDrive folder in Org B
6. **Update CRM**: Sets checkbox to `True` if at least one attachment was successfully uploaded
7. **Log Results**: Logs all operations to console and log files

## Folder Matching Rules

- Matches CRM Record Name to WorkDrive folder names (case-insensitive exact match)
- If multiple matches exist, uses the most recently modified folder
- If folder not found in Org B WorkDrive, logs error and skips record (does not create folder)

## Duplicate Filename Policy

If a file with the same name already exists in the destination folder, it will be renamed:
```
original_name_YYYYMMDD_HHMMSS.ext
```

## Logging

Logs are written to:
- **Console**: Real-time output
- **File**: `logs/migration_YYYYMMDD.log` (date-based)

Log entries include:
- Record ID
- Folder names and IDs
- File transfer status
- Errors and warnings
- Summary statistics

## Error Handling

- **HTTP 429 (Rate Limit)**: Automatic retry with exponential backoff
- **HTTP 5xx (Server Errors)**: Automatic retry (up to 3 attempts)
- **401 (Unauthorized)**: Token refresh and retry
- **Per-Attachment Errors**: Isolated - one attachment failure doesn't stop the transfer

## Exit Codes

- `0`: Success (all records processed successfully)
- `1`: Error (configuration error, fatal error, or some records failed)

## Project Structure

```
project_root/
├── main.py                # CLI entrypoint
├── config.py              # Configuration management
├── auth/
│   └── zoho_auth.py       # OAuth authentication
├── crm/
│   └── crm_client.py      # CRM API client
├── workdrive/
│   ├── org_a_client.py    # WorkDrive Org A client (kept for compatibility, not used in reversed flow)
│   └── org_b_client.py    # WorkDrive Org B client (destination for attachments)
├── services/
│   └── transfer_service.py # Transfer orchestration
├── utils/
│   ├── logger.py           # Logging utilities
│   ├── retry.py            # Retry logic
│   └── file_stream.py      # File streaming utilities
├── tests/                  # Test files
├── logs/                   # Log files
├── requirements.txt        # Python dependencies
├── .env.example           # Environment template
└── README.md              # This file
```

## Testing

Run tests with pytest:

```bash
pytest
```

Run specific test file:

```bash
pytest tests/test_transfer_service.py
```

Run with verbose output:

```bash
pytest -v
```

## Troubleshooting

### "Missing required configuration" error
- Check that all required environment variables are set in `.env`
- Verify variable names match exactly (case-sensitive)

### "Token refresh failed" error
- Verify refresh tokens are valid and not expired
- Check that OAuth client credentials are correct
- Ensure scopes are properly configured

### "Folder not found" warnings
- Verify Record Names in CRM match WorkDrive folder names exactly (case-insensitive)
- Check that `ORG_B_TEAM_FOLDER_ID` is correct
- Ensure the folder exists in the specified Team Folder in Org B WorkDrive
- The service will skip records if folders are not found (does not create folders)

### "Failed to fetch attachments" errors
- Verify the CRM record has attachments in the Attachments Related List
- Check that Org A OAuth scopes include `ZohoCRM.files.READ`
- Ensure you have access to view attachments for the CRM records

## Security Notes

- Never commit `.env` file to version control
- Keep OAuth credentials secure
- Access tokens are cached in memory only (not logged)
- Refresh tokens should be stored securely

## License

This project is provided as-is for internal use.
