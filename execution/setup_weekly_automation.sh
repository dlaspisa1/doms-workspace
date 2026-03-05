#!/bin/bash
# Setup Weekly Gmail Cleanup Automation
# Adds a cron job to run the smart cleanup script every week

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WORKSPACE_DIR="$(dirname "$SCRIPT_DIR")"
CLEANUP_SCRIPT="$WORKSPACE_DIR/execution/gmail_cleanup_smart.py"
LOG_DIR="$WORKSPACE_DIR/.tmp/cron_logs"

# Create log directory
mkdir -p "$LOG_DIR"

# Cron job command
# Runs every Sunday at 2 AM
CRON_SCHEDULE="0 2 * * 0"
CRON_COMMAND="cd \"$WORKSPACE_DIR\" && /usr/bin/python3 \"$CLEANUP_SCRIPT\" >> \"$LOG_DIR/cleanup_\$(date +\%Y\%m\%d_\%H\%M\%S).log\" 2>&1"

echo "=========================================="
echo "Gmail Cleanup - Weekly Automation Setup"
echo "=========================================="
echo ""
echo "This will add a cron job to run the cleanup script:"
echo "  Schedule: Every Sunday at 2:00 AM"
echo "  Script: $CLEANUP_SCRIPT"
echo "  Logs: $LOG_DIR"
echo ""

# Check if cron job already exists
EXISTING_CRON=$(crontab -l 2>/dev/null | grep -F "gmail_cleanup_smart.py")

if [ -n "$EXISTING_CRON" ]; then
    echo "⚠️  Found existing Gmail cleanup cron job:"
    echo "   $EXISTING_CRON"
    echo ""
    read -p "Do you want to replace it? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled. No changes made."
        exit 0
    fi

    # Remove existing job
    crontab -l | grep -vF "gmail_cleanup_smart.py" | crontab -
    echo "✓ Removed existing cron job"
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_SCHEDULE $CRON_COMMAND") | crontab -

echo ""
echo "✓ Cron job added successfully!"
echo ""
echo "The cleanup script will run every Sunday at 2:00 AM."
echo "Logs will be saved to: $LOG_DIR"
echo ""
echo "To view your cron jobs:"
echo "  crontab -l"
echo ""
echo "To remove this cron job:"
echo "  crontab -e"
echo "  (then delete the line containing 'gmail_cleanup_smart.py')"
echo ""
echo "To change the schedule, edit this script and run again."
echo ""
echo "⚠️  IMPORTANT: Before the cron job runs automatically,"
echo "   make sure to set dry_run=False in the cleanup script:"
echo "   $CLEANUP_SCRIPT"
echo ""
