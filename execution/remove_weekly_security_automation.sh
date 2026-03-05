#!/bin/bash
# Remove Weekly Gmail Security Cleanup Automation

set -euo pipefail

CRON_TAG="gmail_security_cleanup.py"

echo "=========================================="
echo "Gmail Security - Remove Weekly Automation"
echo "=========================================="
echo ""

EXISTING_CRON="$(crontab -l 2>/dev/null || true)"
MATCHED="$(printf "%s\n" "$EXISTING_CRON" | grep -F "$CRON_TAG" || true)"

if [ -z "$MATCHED" ]; then
    echo "No security cleanup cron job found."
    exit 0
fi

printf "%s\n" "$EXISTING_CRON" | grep -vF "$CRON_TAG" | crontab -
echo "Security cleanup cron job removed."
