# Email Manager - Setup Guide

This guide walks you through setting up the Email Management Utility step by step.

## Prerequisites

- Python 3.7 or higher
- pip (Python package installer)
- A Gmail account and/or Outlook/Microsoft 365 account

## Step-by-Step Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**Expected output:**
```
Successfully installed google-auth-2.25.2 google-auth-oauthlib-1.2.0 ...
```

---

## Gmail Setup (Detailed)

### Step 1: Create Google Cloud Project

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com
   - Sign in with your Google account

2. **Create New Project**
   - Click the project dropdown at the top
   - Click "New Project"
   - Project name: "Email Manager" (or your choice)
   - Click "Create"
   - Wait for project creation (takes a few seconds)

3. **Select Your Project**
   - Use the project dropdown to select your new project

### Step 2: Enable Required APIs

1. **Navigate to APIs**
   - Click hamburger menu (☰) → "APIs & Services" → "Library"

2. **Enable Gmail API**
   - Search for "Gmail API"
   - Click on it
   - Click "Enable"
   - Wait for activation

3. **Enable Google Calendar API**
   - Click "< Go back" or search again
   - Search for "Google Calendar API"
   - Click on it
   - Click "Enable"

### Step 3: Configure OAuth Consent Screen

1. **Go to OAuth Consent**
   - Click hamburger menu → "APIs & Services" → "OAuth consent screen"

2. **Choose User Type**
   - Select "External"
   - Click "Create"

3. **Fill App Information**
   - App name: "Email Manager"
   - User support email: Your email
   - Developer contact: Your email
   - Click "Save and Continue"

4. **Scopes** (Step 2)
   - Click "Save and Continue" (we'll add scopes in credentials)

5. **Test Users** (Step 3)
   - Click "Add Users"
   - Enter your Gmail address
   - Click "Add"
   - Click "Save and Continue"

6. **Summary** (Step 4)
   - Review and click "Back to Dashboard"

### Step 4: Create OAuth Credentials

1. **Go to Credentials**
   - Click hamburger menu → "APIs & Services" → "Credentials"

2. **Create Credentials**
   - Click "Create Credentials" at top
   - Select "OAuth client ID"

3. **Configure OAuth Client**
   - Application type: "Desktop app"
   - Name: "Email Manager Desktop"
   - Click "Create"

4. **Download Credentials**
   - A popup appears with your Client ID and Secret
   - Click "Download JSON"
   - Save the file

5. **Rename Downloaded File**
   - Rename the downloaded file to: `gmail_credentials.json`
   - Move it to your email-manager directory

**Your gmail_credentials.json should look like:**
```json
{
  "installed": {
    "client_id": "123456789-abcdefg.apps.googleusercontent.com",
    "project_id": "email-manager-xxxxx",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "GOCSPX-xxxxxxxxxxxxxxxxx",
    "redirect_uris": ["http://localhost"]
  }
}
```

### Step 5: Test Gmail Authentication

```bash
python email_manager.py --provider gmail --setup-only
```

**What happens:**
1. Browser opens automatically
2. Sign in to your Google account
3. You'll see "Google hasn't verified this app" warning
   - Click "Advanced"
   - Click "Go to Email Manager (unsafe)"
   - This is normal for personal projects
4. Grant permissions:
   - ✓ Read, compose, send, and permanently delete all your email
   - ✓ See, edit, share, and permanently delete calendars
5. Click "Continue"
6. Browser shows "The authentication flow has completed"
7. Return to terminal - should show "Gmail authentication successful"

**Files created:**
- `gmail_token.pickle` - Your saved authentication token

---

## Outlook Setup (Detailed)

### Step 1: Register Azure AD Application

1. **Go to Azure Portal**
   - Visit: https://portal.azure.com
   - Sign in with your Microsoft account

2. **Navigate to App Registrations**
   - Search bar at top: Type "App registrations"
   - Click "App registrations" service

3. **Create New Registration**
   - Click "+ New registration"

4. **Fill Registration Details**
   - Name: "Email Manager"
   - Supported account types: 
     - Select "Accounts in any organizational directory and personal Microsoft accounts"
   - Redirect URI: Leave blank for now
   - Click "Register"

5. **Note Your Client ID**
   - After creation, you'll see the Overview page
   - Copy the "Application (client) ID"
   - Example: `12345678-1234-1234-1234-123456789abc`
   - Save this - you'll need it!

### Step 2: Configure Authentication

1. **Go to Authentication**
   - In left sidebar: Click "Authentication"

2. **Add Platform**
   - Click "Add a platform"
   - Select "Mobile and desktop applications"

3. **Configure Redirect URIs**
   - Check the box for `http://localhost`
   - Click "Configure"

4. **Advanced Settings** (on Authentication page)
   - Allow public client flows: "Yes"
   - Click "Save" at top

### Step 3: Add API Permissions

1. **Go to API Permissions**
   - In left sidebar: Click "API permissions"

2. **Add Permission - Mail**
   - Click "+ Add a permission"
   - Click "Microsoft Graph"
   - Click "Delegated permissions"
   - Search for "Mail"
   - Expand "Mail" and check:
     - ✓ Mail.ReadWrite
   - Click "Add permissions"

3. **Add Permission - Calendar**
   - Click "+ Add a permission" again
   - Click "Microsoft Graph"
   - Click "Delegated permissions"
   - Search for "Calendar"
   - Expand "Calendars" and check:
     - ✓ Calendars.ReadWrite
   - Click "Add permissions"

4. **Grant Admin Consent** (if prompted)
   - If you see a warning banner
   - Click "Grant admin consent for [your organization]"
   - Click "Yes" to confirm

**Final permissions list should show:**
- Microsoft Graph (2):
  - Calendars.ReadWrite (Delegated)
  - Mail.ReadWrite (Delegated)

### Step 4: Create Credentials File

1. **Create outlook_credentials.json**
   ```bash
   # Copy the template
   cp outlook_credentials.json.template outlook_credentials.json
   ```

2. **Edit the file**
   - Open `outlook_credentials.json`
   - Replace `YOUR_AZURE_AD_CLIENT_ID_HERE` with your actual Client ID
   - Save the file

**Example outlook_credentials.json:**
```json
{
    "client_id": "12345678-1234-1234-1234-123456789abc",
    "authority": "https://login.microsoftonline.com/common"
}
```

### Step 5: Test Outlook Authentication

```bash
python email_manager.py --provider outlook --setup-only
```

**What happens:**
1. Browser opens automatically
2. Sign in to your Microsoft account
3. Grant permissions:
   - ✓ Read and write access to your mail
   - ✓ Read and write access to your calendars
4. Click "Accept"
5. Browser may show "Authentication complete, you can close this window"
6. Return to terminal - should show "Outlook authentication successful"

---

## Verification

### Check Authentication Works

```bash
# Test both providers
python email_manager.py --setup-only
```

**Expected output:**
```
INFO - Setting up Gmail handler...
INFO - Authenticated as: your.email@gmail.com
INFO - Gmail authentication successful
INFO - Setting up Outlook handler...
INFO - Authenticated as: your.email@outlook.com
INFO - Outlook authentication successful
INFO - Setup complete. Run without --setup-only to process emails.
```

### Test in Dry Run Mode

```bash
# Safe test - no emails will be modified
python email_manager.py
```

This will show what emails would be processed without actually changing anything.

---

## Common Issues and Solutions

### Issue: "gmail_credentials.json not found"

**Solution:**
- Make sure you downloaded the OAuth credentials from Google Cloud Console
- Rename the file to exactly `gmail_credentials.json`
- Place it in the same directory as the Python scripts

### Issue: "Google hasn't verified this app"

**Solution:**
- This is normal for personal projects
- Click "Advanced" → "Go to Email Manager (unsafe)"
- Your app is safe - Google just hasn't reviewed it because it's personal

### Issue: "Access blocked: This app's request is invalid"

**Solution:**
- Make sure you enabled both Gmail API and Google Calendar API
- Check that OAuth consent screen is configured
- Verify you added yourself as a test user

### Issue: "outlook_credentials.json not found"

**Solution:**
- Copy the template: `cp outlook_credentials.json.template outlook_credentials.json`
- Edit the file and add your Client ID from Azure Portal

### Issue: Outlook authentication fails

**Solution:**
- Verify redirect URI `http://localhost` is added in Authentication settings
- Check that "Allow public client flows" is enabled
- Ensure Mail.ReadWrite and Calendars.ReadWrite permissions are granted

### Issue: "Invalid grant" or "Token expired"

**Solution:**
- Delete the token files:
  ```bash
  rm gmail_token.pickle
  ```
- Re-run authentication:
  ```bash
  python email_manager.py --setup-only
  ```

---

## Next Steps

Once authentication is working:

1. **Test in dry-run mode:**
   ```bash
   python email_manager.py
   ```

2. **Review the logs:**
   - Check `email_manager.log` to see what would be processed

3. **If results look good, run live mode:**
   ```bash
   # Explicit authentication step (recommended before live runs)
   python email_manager.py --setup-only

   python email_manager.py --live
   ```

4. **Set up automation:**
   - See README.md for cron (Linux/Mac) or Task Scheduler (Windows) setup

---

## Security Reminders

🔐 **Keep These Files Secret:**
- `gmail_credentials.json`
- `outlook_credentials.json`
- `gmail_token.pickle`

Never share these files or commit them to git!

🔒 **Revoke Access Anytime:**
- Gmail: https://myaccount.google.com/permissions
- Outlook: https://account.microsoft.com/privacy/app-access

---

## Need Help?

Check the main README.md for:
- Usage examples
- Customization options
- Scheduling setup
- Troubleshooting guide
