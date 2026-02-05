# Zoho WorkDrive Migration Service

A Python automation service that transfers files from Zoho WorkDrive (Organization B) to Zoho WorkDrive (Organization A) based on CRM records, and updates CRM checkboxes to track transfer completion.

## Features

- **Cross-Organization Transfer**: Transfers files from WorkDrive Org B to WorkDrive Org A
- **CRM Integration**: Reads pending records from Zoho CRM and updates transfer status
- **Recursive Transfer**: Recursively copies files and subfolders, mirroring folder structure
- **Duplicate Handling**: Automatically renames duplicate filenames with timestamps
- **Error Isolation**: Per-file error handling ensures one failure doesn't stop the entire transfer
- **Retry Logic**: Automatic retry with exponential backoff for transient errors
- **Dry-Run Mode**: Test the service without making actual changes
- **Comprehensive Logging**: Detailed logs for all operations

## Requirements

- Python 3.11+
- Zoho OAuth Self Client credentials for both organizations
- Access to Zoho CRM (Org A) and WorkDrive (both orgs)

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

# Organization A (CRM + WorkDrive Destination)
ORG_A_CLIENT_ID=your_org_a_client_id
ORG_A_CLIENT_SECRET=your_org_a_client_secret
ORG_A_REFRESH_TOKEN=your_org_a_refresh_token

# Organization B (WorkDrive Source)
ORG_B_CLIENT_ID=your_org_b_client_id
ORG_B_CLIENT_SECRET=your_org_b_client_secret
ORG_B_REFRESH_TOKEN=your_org_b_refresh_token
ORG_B_TEAM_FOLDER_ID=your_org_b_team_folder_root_id

# CRM Configuration
CRM_MODULE_API_NAME=Contacts
CRM_CHECKBOX_FIELD_API_NAME=Transfer_Complete
CRM_FOLDER_NAME_FIELD_API_NAME=Source_Folder_Name

# WorkDrive Destination
WORKDRIVE_DEST_FOLDER_ID=your_destination_folder_id
```

### OAuth Setup

You need to create OAuth Self Clients in both Zoho organizations:

**Org A Scopes:**
- `ZohoCRM.modules.ALL`
- `WorkDrive.files.CREATE`
- `WorkDrive.files.READ`
- `WorkDrive.files.UPDATE`
- `WorkDrive.teamfolders.READ`

**Org B Scopes:**
- `WorkDrive.files.READ`
- `WorkDrive.teamfolders.READ`

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

1. **Fetch CRM Records**: Retrieves records where the checkbox is `False` and folder name is not empty
2. **Resolve Source Folder**: Searches for matching folder in Org B WorkDrive (scoped to configured Team Folder)
3. **Transfer Files**: Recursively walks the folder structure and transfers all files to Org A, mirroring the folder structure
4. **Update CRM**: Sets checkbox to `True` if at least one file was successfully transferred
5. **Log Results**: Logs all operations to console and log files

## Folder Matching Rules

- Case-insensitive exact match
- If multiple matches exist, uses the most recently modified folder
- If folder not found, logs error and skips record

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
- **Per-File Errors**: Isolated - one file failure doesn't stop the transfer

## Exit Codes

- `0`: Success (all records processed successfully)
- `1`: Error (configuration error, fatal error, or some records failed)

## Project Structure

```
project_root/
├── main.py                 # CLI entrypoint
├── config.py              # Configuration management
├── auth/
│   └── zoho_auth.py       # OAuth authentication
├── crm/
│   └── crm_client.py      # CRM API client
├── workdrive/
│   ├── org_a_client.py    # WorkDrive Org A client
│   └── org_b_client.py    # WorkDrive Org B client
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
- Verify folder names in CRM match exactly (case-insensitive)
- Check that `ORG_B_TEAM_FOLDER_ID` is correct
- Ensure the folder exists in the specified Team Folder

### "Destination folder does not exist" error
- Verify `WORKDRIVE_DEST_FOLDER_ID` is correct
- Ensure you have access to the destination folder in Org A

## Security Notes

- Never commit `.env` file to version control
- Keep OAuth credentials secure
- Access tokens are cached in memory only (not logged)
- Refresh tokens should be stored securely

## License

This project is provided as-is for internal use.
