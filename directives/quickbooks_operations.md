# QuickBooks Online Operations

## Purpose
Access and manage QuickBooks Online data across multiple company files. This directive enables reading financial data, exporting reports, and managing transactions via the QuickBooks API.

## Prerequisites
- QuickBooks Online account with API access
- OAuth 2.0 credentials from Intuit Developer Portal
- Company Realm IDs for each QuickBooks company you want to access

## Tools Available

### Authentication
- `execution/qbo_auth.py` - Handles OAuth 2.0 authentication flow
  - Generates authorization URL
  - Exchanges authorization code for access/refresh tokens
  - Refreshes expired tokens automatically

### Data Access
- `execution/qbo_get_report.py` - Fetch financial reports (P&L, Balance Sheet, etc.)
- `execution/qbo_get_customers.py` - Retrieve customer list
- `execution/qbo_get_invoices.py` - Get invoices with filters
- `execution/qbo_get_vendors.py` - Retrieve vendor list
- `execution/qbo_get_accounts.py` - Get chart of accounts
- `execution/qbo_export_to_sheet.py` - Export QBO data to Google Sheets

## Setup Process

### 1. Get QuickBooks API Credentials
1. Go to https://developer.intuit.com
2. Create an app or use existing app
3. Get Client ID and Client Secret
4. Set Redirect URI to `http://localhost:8080/callback`
5. Add to `.env`:
   ```
   QBO_CLIENT_ID=your_client_id
   QBO_CLIENT_SECRET=your_client_secret
   QBO_REDIRECT_URI=http://localhost:8080/callback
   QBO_ENVIRONMENT=sandbox  # or 'production'
   ```

### 2. Get Company Realm ID
1. Run `python execution/qbo_auth.py` to authenticate
2. After authorization, the script displays your Realm ID
3. Add to `.env`:
   ```
   QBO_REALM_ID=123456789
   ```

### 3. For Multiple Companies
Create separate workspaces with different `.env` files:
```
/Company-A-workspace/.env → QBO_REALM_ID=111111111
/Company-B-workspace/.env → QBO_REALM_ID=222222222
```

## Common Operations

### Get Profit & Loss Report
```bash
python execution/qbo_get_report.py --report profit_and_loss --start-date 2024-01-01 --end-date 2024-12-31
```

### Export Invoices to Google Sheets
```bash
python execution/qbo_export_to_sheet.py --data-type invoices --sheet-id YOUR_SHEET_ID
```

### Get Customer List
```bash
python execution/qbo_get_customers.py --active-only
```

## Error Handling

### Comprehensive Error Handling
All scripts include comprehensive error handling that:
- **Captures intuit_tid**: Transaction IDs from API responses for troubleshooting
- **Logs all errors**: Detailed error logs saved to `.tmp/logs/qbo_errors.log`
- **Categorizes errors**: Authentication, validation, syntax, and rate limit errors
- **Provides support info**: Contact details and log location for troubleshooting

### Error Types

**Authentication Errors (401)**
- Token expired or invalid
- Scripts automatically refresh tokens using refresh_token
- If refresh fails, re-run `qbo_auth.py` to re-authenticate

**Validation Errors (400)**
- Invalid data in API requests
- Check error message for specific validation issues
- Review API documentation for correct data formats

**Syntax Errors (400)**
- Malformed API requests
- Check query syntax or request structure
- Error details include the problematic query/request

**Rate Limit Errors (429)**
- QuickBooks API: 500 requests per minute per company
- Scripts automatically retry with exponential backoff
- Reduce `max_results` or add delays between requests

### Error Logs

**Location**: `.tmp/logs/qbo_errors.log`

**Contains**:
- Timestamp of error
- Error type and message
- intuit_tid (transaction ID) for Intuit support
- Error code and details
- Context (function, parameters, etc.)

**Example log entry**:
```json
{
  "timestamp": "2024-01-21T10:30:45",
  "error_type": "QBOAuthError",
  "error_message": "Invalid grant",
  "intuit_tid": "abc123-def456-ghi789",
  "error_code": "INVALID_GRANT",
  "context": {
    "function": "refresh_tokens",
    "realm_id": "123456789"
  }
}
```

### Support Contact

Error messages include support contact information set in `.env`:
```
SUPPORT_EMAIL=your-email@example.com
```

When errors occur, users are directed to:
1. Check error logs at `.tmp/logs/qbo_errors.log`
2. Contact support with the intuit_tid for faster troubleshooting
3. Include relevant log entries when reporting issues

### Invalid Realm ID
- Verify realm ID matches the company you authenticated with
- Re-authenticate if you switched companies

## Data Output

All scripts output to:
- `.tmp/qbo_data/` for JSON responses
- Google Sheets for deliverables (via `qbo_export_to_sheet.py`)

## Security Notes

- OAuth tokens stored in `.tmp/qbo_tokens.json` (gitignored)
- Never commit `.env` or token files
- Tokens auto-refresh, valid for 100 days with activity
- Use production environment only for live data

## Learnings & Updates

### 2024-01-21
- Initial directive created
- OAuth flow implemented
- Core data access scripts ready
