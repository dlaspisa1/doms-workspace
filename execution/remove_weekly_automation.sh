#!/bin/bash
# Remove Weekly Gmail Cleanup Automation
# Removes the cron job for the cleanup script

echo "=========================================="
echo "Gmail Cleanup - Remove Weekly Automation"
echo "=========================================="
echo ""

# Check if cron job exists
EXISTING_CRON=$(crontab -l 2>/dev/null | grep -F "gmail_cleanup_smart.py")

if [ -z "$EXISTING_CRON" ]; then
    echo "No Gmail cleanup cron job found."
    exit 0
fi

echo "Found cron job:"
echo "  $EXISTING_CRON"
echo ""
read -p "Do you want to remove this cron job? (y/n): " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled. No changes made."
    exit 0
fi

# Remove cron job
crontab -l | grep -vF "gmail_cleanup_smart.py" | crontab -

echo ""
echo "✓ Cron job removed successfully!"
echo ""
echo "The cleanup script will no longer run automatically."
echo ""
