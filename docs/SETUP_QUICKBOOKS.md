# QuickBooks Online Setup Guide

This guide walks you through setting up QuickBooks Online API access for this system.

## Overview

The QuickBooks integration uses OAuth 2.0 authentication and allows you to:
- Pull financial reports (P&L, Balance Sheet, Cash Flow, etc.)
- Export invoices, customers, vendors, and other data
- Access multiple QuickBooks company files from different workspaces
- Automate data syncing to Google Sheets

## Prerequisites

1. QuickBooks Online account (not Desktop)
2. Access to Intuit Developer Portal
3. Python 3.7+ installed
4. This repository cloned and dependencies installed

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `python-quickbooks` - QuickBooks API client
- `intuitlib` - OAuth 2.0 library for Intuit

## Step 2: Create Intuit Developer App

### 2.1 Access Developer Portal
1. Go to https://developer.intuit.com
2. Sign in with your Intuit account
3. Click "My Apps" in the top navigation

### 2.2 Create New App
1. Click "Create an app" (or use existing app)
2. Choose "QuickBooks Online and Payments"
3. Name your app (e.g., "My QBO Integration")

### 2.3 Get Credentials
1. In your app dashboard, go to "Keys & credentials"
2. Copy your **Client ID** and **Client Secret**
3. Save these securely

### 2.4 Set Redirect URI
1. In "Keys & credentials", scroll to "Redirect URIs"
2. Add: `http://localhost:8080/callback`
3. Save

## Step 3: Configure Environment

### 3.1 Update .env File
Add these variables to your `.env` file:

```bash
# QuickBooks Online API
QBO_CLIENT_ID=your_client_id_here
QBO_CLIENT_SECRET=your_client_secret_here
QBO_REDIRECT_URI=http://localhost:8080/callback
QBO_ENVIRONMENT=sandbox
QBO_REALM_ID=
```

**Important:**
- `QBO_ENVIRONMENT` should be `sandbox` for testing, `production` for live data
- Leave `QBO_REALM_ID` empty for now (we'll get it in the next step)

## Step 4: Authenticate with QuickBooks

### 4.1 Run Authentication Script
```bash
python execution/qbo_auth.py
```

### 4.2 Follow the Prompts
1. The script will display an authorization URL
2. Copy and paste it into your browser
3. Sign in to QuickBooks
4. Select which company to connect (if you have multiple)
5. Click "Connect" to authorize

### 4.3 Save Your Realm ID
After successful authorization:
1. The script will display your **Realm ID** (company identifier)
2. Copy this ID
3. Add it to `.env`:
   ```bash
   QBO_REALM_ID=123456789012345
   ```

### 4.4 Verify Tokens
The authentication process creates `.tmp/qbo_tokens.json` which contains:
- Access token (valid for 1 hour)
- Refresh token (valid for 100 days with activity)

These tokens auto-refresh, so you won't need to re-authenticate unless:
- You revoke access in QuickBooks
- 100 days pass with no API activity
- You delete the tokens file

## Step 5: Test the Connection

```bash
python execution/qbo_client.py
```

You should see:
```
✓ Connected to QuickBooks Online
✓ Company ID: 123456789012345
✓ Environment: sandbox

Client ready for use!
```

## Step 6: Try Basic Operations

### Get Customer List
```bash
python execution/qbo_get_customers.py --active-only
```

### Get Invoices
```bash
python execution/qbo_get_invoices.py --start-date 2024-01-01 --end-date 2024-12-31
```

### Get Profit & Loss Report
```bash
python execution/qbo_get_report.py --report profit_and_loss --start-date 2024-01-01 --end-date 2024-12-31
```

All data is saved to `.tmp/qbo_data/` as JSON files.

## Multiple Company Setup

If you want to access different QuickBooks companies from separate workspaces:

### Workspace Structure
```
/Company-A-workspace/
  .env                    # QBO_REALM_ID=111111111
  directives/
  execution/
  .tmp/qbo_tokens.json    # Tokens for Company A

/Company-B-workspace/
  .env                    # QBO_REALM_ID=222222222
  directives/
  execution/
  .tmp/qbo_tokens.json    # Tokens for Company B
```

### Setup Process
1. Create separate workspace directories
2. Copy all files to each workspace
3. In each workspace, update `.env` with different `QBO_REALM_ID`
4. Run `python execution/qbo_auth.py` in each workspace
5. When prompted, select the correct company to connect

**Note:** All companies must be accessible by the same Intuit login. The OAuth credentials (Client ID/Secret) can be shared across workspaces.

## Switching Between Sandbox and Production

### Development (Sandbox)
```bash
QBO_ENVIRONMENT=sandbox
```
- Use test company data
- Safe for development and testing
- No impact on real financials

### Live Data (Production)
```bash
QBO_ENVIRONMENT=production
```
- Uses real QuickBooks data
- Be careful with write operations
- Recommended only after thorough testing in sandbox

**To switch:**
1. Update `QBO_ENVIRONMENT` in `.env`
2. Re-run `python execution/qbo_auth.py`
3. Authorize with the production company

## Security Best Practices

1. **Never commit credentials**
   - `.env` is in `.gitignore`
   - `.tmp/qbo_tokens.json` is in `.gitignore`

2. **Use environment-specific credentials**
   - Separate apps for sandbox vs production (recommended)
   - Or use same app but different realm IDs

3. **Token management**
   - Tokens auto-refresh every API call
   - Old refresh tokens are invalidated after new ones are issued
   - Revoke access from QuickBooks if tokens are compromised

4. **Scopes**
   - Current setup uses `Accounting` scope (full access)
   - Consider limiting scopes for production apps

## Troubleshooting

### "Invalid Grant" Error
- Your refresh token expired (100 days no activity)
- **Fix:** Re-run `python execution/qbo_auth.py`

### "Unauthorized" Error
- Access token expired and refresh failed
- **Fix:** Re-run `python execution/qbo_auth.py`

### "Invalid Realm ID"
- Realm ID doesn't match authenticated company
- **Fix:** Verify `QBO_REALM_ID` in `.env` matches the value from auth script

### Rate Limit Errors
- QuickBooks allows 500 requests/minute per company
- Scripts automatically retry with exponential backoff
- Reduce `max_results` parameters if hitting limits frequently

### Connection Errors
- Check internet connection
- Verify API credentials are correct
- Check Intuit Developer status page: https://status.developer.intuit.com

## Next Steps

1. Read [directives/quickbooks_operations.md](directives/quickbooks_operations.md) for usage examples
2. Explore available scripts in `execution/qbo_*.py`
3. Customize queries for your specific needs
4. Set up automated exports to Google Sheets

## Resources

- [Intuit Developer Docs](https://developer.intuit.com/app/developer/qbo/docs/get-started)
- [QuickBooks API Reference](https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/account)
- [python-quickbooks Library](https://github.com/ej2/python-quickbooks)

---

**Questions?** Check the directive file or run scripts with `--help` flag for usage details.
