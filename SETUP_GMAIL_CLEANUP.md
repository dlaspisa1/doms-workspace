# Gmail Inbox Cleanup - Setup Guide

## Quick Start

Your Gmail inbox cleanup system is ready! Follow these steps to get started.

## Prerequisites

1. **Python 3.8+** installed
2. **Gmail account** you want to clean up
3. **Google Cloud Console** access

## Setup Steps

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Google Cloud Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the **Gmail API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Gmail API"
   - Click "Enable"
4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Application type: **Desktop app**
   - Download the credentials file
   - Save as `credentials.json` in your project root

### 3. Authenticate

Run the authentication script to generate your token:

```bash
cd "/Users/dominicklaspisa/Googipet Work Space"
python execution/gmail_auth.py
```

This will:
- Open a browser window for OAuth consent
- Ask you to authorize the app
- Save `token.json` for future use

### 4. Test Run (Dry Run)

Run the cleanup script in dry run mode to preview actions:

```bash
python execution/gmail_cleanup.py
```

This will show you what would be done without making any changes.

### 5. Customize Configuration

Edit `execution/gmail_cleanup.py` to customize:

```python
config = {
    'days_to_archive': 30,  # Archive messages older than X days
    'promotional_keywords': ["unsubscribe", "promotional", "newsletter"],
    'label_rules': {
        # Add your own label rules
        'work': {
            'from': ['@yourcompany.com']
        },
        'receipts': {
            'subject': ['receipt', 'order confirmation', 'invoice']
        },
        'social': {
            'from': ['facebook.com', 'linkedin.com', 'twitter.com']
        }
    },
    'dry_run': True  # Set to False when ready to execute
}
```

### 6. Execute Cleanup

Once satisfied with the preview, disable dry run:

```python
'dry_run': False
```

Then run:

```bash
python execution/gmail_cleanup.py
```

## What It Does

✓ **Archives old messages** (30+ days old by default)
- Skips starred, important, and unread messages
- Keeps messages in "All Mail"

✓ **Auto-labels messages** based on rules
- Work emails, receipts, social notifications, etc.
- Creates labels automatically

✓ **Deletes promotional emails**
- Moves to trash (30-day retention)
- Uses keywords and Gmail categories

## Logs

Check `.tmp/gmail_cleanup_*.json` for detailed logs of each run.

## Safety Features

- **Dry run mode** by default
- **Never touches** starred or important messages
- **Preserves unread** messages (configurable)
- **Trash retention** - deleted emails can be recovered for 30 days
- **Detailed logging** of all actions

## Automation (Optional)

To run automatically, set up a cron job:

```bash
# Run daily at 2 AM
0 2 * * * cd "/Users/dominicklaspisa/Googipet Work Space" && python execution/gmail_cleanup.py
```

## Troubleshooting

**"credentials.json not found"**
- Download OAuth credentials from Google Cloud Console
- Place in project root directory

**"Token expired"**
- Delete `token.json`
- Run `python execution/gmail_auth.py` again

**"Rate limit exceeded"**
- Gmail API has quotas (250 units/user/second)
- Script includes backoff handling
- Try again later if limits are hit

## Next Steps

1. Review the directive: [directives/cleanup_gmail_inbox.md](directives/cleanup_gmail_inbox.md)
2. Customize label rules for your needs
3. Set up automation if desired
4. Check logs regularly to refine rules

For more information, see [CLAUDE.md](CLAUDE.md) for the 3-layer architecture.
