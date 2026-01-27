# Email Management Utility

A Python utility to automatically manage Gmail and Outlook emails with intelligent filtering, archiving, and calendar integration.

## Features

✨ **Automated Email Management:**
- 🗑️ Delete promotional emails older than 30 days
- 📧 Delete job alerts older than 7 days  
- 📁 Archive job rejection emails
- ⭐ Highlight important emails addressed directly to you
- 📅 Create calendar reminders for important emails

🔒 **Safe by Default:**
- Runs in dry-run mode by default (no changes made)
- Moves emails to trash/deleted items instead of permanent deletion
- Detailed logging of all actions

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Gmail Authentication

#### Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project (or select existing)
3. Enable APIs:
   - Gmail API
   - Google Calendar API
4. Configure OAuth consent screen:
   - User Type: External
   - Add your email as test user
5. Create credentials:
   - Create Credentials → OAuth 2.0 Client ID
   - Application type: Desktop app
   - Name: "Email Manager" (or any name)
6. Download credentials JSON file
7. Save as `gmail_credentials.json` in the project directory

#### Required Scopes
The app requests these permissions:
- `https://www.googleapis.com/auth/gmail.modify` - Read and modify emails
- `https://www.googleapis.com/auth/calendar` - Create calendar events

### 3. Set Up Outlook Authentication

#### Register Azure AD Application

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to Azure Active Directory → App registrations
3. Click "New registration":
   - Name: "Email Manager" (or any name)
   - Supported account types: "Accounts in any organizational directory and personal Microsoft accounts"
   - Redirect URI: Leave blank for now
4. After creation, note the **Application (client) ID**
5. Configure platform:
   - Go to Authentication
   - Add platform → Mobile and desktop applications
   - Add redirect URI: `http://localhost`
6. Configure API permissions:
   - Add permission → Microsoft Graph → Delegated permissions
   - Add: `Mail.ReadWrite`, `Calendars.ReadWrite`
   - Grant admin consent (if required)
7. Create `outlook_credentials.json`:

```json
{
    "client_id": "your-application-client-id-here",
    "authority": "https://login.microsoftonline.com/common"
}
```

## Usage

### First Run - Authentication Setup

```bash
# Setup Gmail only
python email_manager.py --provider gmail --setup-only

# Setup Outlook only
python email_manager.py --provider outlook --setup-only

# Setup both
python email_manager.py --setup-only
```

This will open your browser for OAuth authentication. After granting permissions, credentials are saved locally for future use.

### Dry Run (Test Mode)

**Recommended for first use** - Shows what would be done without making changes:

```bash
# Process both Gmail and Outlook (dry run)
python email_manager.py

# Process only Gmail
python email_manager.py --provider gmail

# Process only Outlook
python email_manager.py --provider outlook
```

### Live Mode (Make Actual Changes)

```bash
# Explicit authentication step (recommended before live runs)
python email_manager.py --setup-only

# Process both providers (make actual changes)
python email_manager.py --live

# Process only Gmail
python email_manager.py --provider gmail --live

# Process only Outlook  
python email_manager.py --provider outlook --live
```

## How It Works

### Authentication Flow

#### Gmail (OAuth 2.0)
1. First run opens browser for Google login
2. Grants app permission to access Gmail and Calendar
3. Token saved to `gmail_token.pickle` for future use
4. Token auto-refreshes when expired

#### Outlook (OAuth 2.0 with MSAL)
1. First run opens browser for Microsoft login
2. Grants app permission to access Mail and Calendar
3. Token cached by MSAL library
4. Token auto-refreshes when expired

### Email Filtering Logic

#### Promotional Emails (30+ days old)
- **Gmail**: Uses built-in `category:promotions` label
- **Outlook**: Keyword matching on sender addresses:
  - Contains: noreply, newsletter, marketing, promotions, offers, unsubscribe

#### Job Alerts (7+ days old)
- **Gmail**: Searches for:
  - Subject/body: "job alert", "career opportunity", "new jobs", "job notification"
  - From: linkedin.com, indeed.com, glassdoor.com
- **Outlook**: Searches:
  - Sender domains: linkedin.com, indeed.com, glassdoor.com, monster.com, careerbuilder.com
  - Subject: "job alert", "career opportunity", "new jobs"

#### Rejection Emails
Archives emails containing phrases like:
- "regret to inform"
- "not moving forward"
- "chosen to pursue other candidates"
- "not been successful"
- "position has been filled"

#### Important Emails
Identifies emails that are:
- Received in last 7 days
- Directly addressed to you (in To: field, max 2 recipients)
- Not from no-reply addresses
- Marked as important OR from real people

### Calendar Integration

For each important email, creates a calendar event:
- **Title**: "📧 Read: [Email Subject]"
- **When**: Tomorrow at 9:00 AM
- **Duration**: 30 minutes
- **Reminder**: 10 minutes before
- **Description**: Sender information and reminder text

## File Structure

```
email-manager/
├── email_manager.py       # Main entry point
├── gmail_handler.py       # Gmail-specific logic
├── outlook_handler.py     # Outlook-specific logic
├── requirements.txt       # Python dependencies
├── gmail_credentials.json # Google OAuth credentials (you create)
├── outlook_credentials.json # Azure AD credentials (you create)
├── gmail_token.pickle     # Saved Gmail token (auto-created)
└── email_manager.log      # Application logs
```

## Logging

All actions are logged to:
- Console (stdout)
- `email_manager.log` file

Log levels:
- INFO: Normal operations, statistics
- ERROR: Problems encountered
- WARNING: Important notices

## Customization

### Modify Time Periods

Edit the handlers to change retention periods:

```python
# In gmail_handler.py or outlook_handler.py

# Change promotion deletion period (default: 30 days)
cutoff_date = datetime.now() - timedelta(days=30)  # Change to 60, 90, etc.

# Change job alert period (default: 7 days)
cutoff_date = datetime.now() - timedelta(days=7)   # Change to 14, 30, etc.
```

### Add More Keywords

Add to the keyword lists in handlers:

```python
# More job alert keywords
job_keywords = [
    'job alert',
    'career opportunity',
    'new jobs',
    'your custom keyword here'  # Add your own
]

# More rejection phrases
rejection_phrases = [
    'regret to inform',
    'not moving forward',
    'your custom phrase here'  # Add your own
]
```

### Adjust Important Email Criteria

Modify `_find_important_emails()` and `_is_directly_addressed()` methods to change what's considered important.

## Scheduling (Automation)

### Linux/Mac (cron)

Run daily at 8 AM:

```bash
# Edit crontab
crontab -e

# Add this line (adjust path to your script)
0 8 * * * cd /path/to/email-manager && /usr/bin/python3 email_manager.py --live >> /path/to/logs/cron.log 2>&1
```

### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Daily at 8:00 AM
4. Action: Start a program
5. Program: `python`
6. Arguments: `email_manager.py --live`
7. Start in: `C:\path\to\email-manager`

## Security Notes

🔐 **Credential Storage:**
- OAuth tokens stored locally in `gmail_token.pickle` and MSAL cache
- Never share these files or commit to version control
- Add to `.gitignore`:
  ```
  gmail_token.pickle
  outlook_credentials.json
  gmail_credentials.json
  *.log
  ```

🔒 **Permissions:**
- App only requests necessary permissions
- You can revoke access anytime:
  - Gmail: [Google Account Permissions](https://myaccount.google.com/permissions)
  - Outlook: [Microsoft Account Apps](https://account.microsoft.com/privacy/app-access)

## Troubleshooting

### "gmail_credentials.json not found"
- Download OAuth credentials from Google Cloud Console
- Save in the same directory as the scripts

### "outlook_credentials.json not found"
- Create this file with your Azure AD client_id
- See Outlook setup section above

### Authentication fails
- Check that APIs are enabled in Google Cloud Console
- Verify redirect URIs are configured correctly
- Make sure you granted all requested permissions

### No emails found
- Run in dry-run mode first to see what would be processed
- Check log file for specific errors
- Verify email filters match your email patterns

### Rate limiting
- Both APIs have rate limits
- The app processes in batches to avoid hitting limits
- Add delays between requests if needed

## Contributing

Feel free to customize this utility for your needs! Some ideas:
- Add more email categories
- Integrate with other email providers
- Create a GUI interface
- Add email analytics/reporting
- Integrate with task management tools

## License

MIT License - Feel free to use and modify as needed!

## Disclaimer

⚠️ **Important**: 
- Always test in dry-run mode first
- This app permanently deletes/archives emails in live mode
- Author not responsible for any data loss
- Use at your own risk
- Keep backups of important emails
