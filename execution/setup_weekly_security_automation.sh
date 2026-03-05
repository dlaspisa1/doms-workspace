#!/bin/bash
# Setup Weekly Gmail Security Cleanup Automation
# Adds or updates a cron job for phishing/spam cleanup with email reports.

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WORKSPACE_DIR="$(dirname "$SCRIPT_DIR")"
SECURITY_SCRIPT="$WORKSPACE_DIR/execution/gmail_security_cleanup.py"
LOG_DIR="$WORKSPACE_DIR/.tmp/cron_logs"
CRON_SCHEDULE="30 2 * * 0"
CRON_TAG="gmail_security_cleanup.py"

PYTHON_BIN="$WORKSPACE_DIR/venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="/usr/bin/python3"
fi

mkdir -p "$LOG_DIR"

CRON_COMMAND="cd \"$WORKSPACE_DIR\" && \"$PYTHON_BIN\" \"$SECURITY_SCRIPT\" >> \"$LOG_DIR/security_cleanup_\$(date +\%Y\%m\%d_\%H\%M\%S).log\" 2>&1"

echo "=========================================="
echo "Gmail Security - Weekly Automation Setup"
echo "=========================================="
echo "Schedule: Every Sunday at 2:30 AM"
echo "Script:   $SECURITY_SCRIPT"
echo "Python:   $PYTHON_BIN"
echo "Logs:     $LOG_DIR"
echo ""

EXISTING_CRON="$(crontab -l 2>/dev/null || true)"
FILTERED_CRON="$(printf "%s\n" "$EXISTING_CRON" | grep -vF "$CRON_TAG" || true)"

{
    printf "%s\n" "$FILTERED_CRON"
    printf "%s %s\n" "$CRON_SCHEDULE" "$CRON_COMMAND"
} | sed '/^[[:space:]]*$/d' | crontab -

echo "Weekly security cleanup cron job is active."
echo ""
echo "To verify:"
echo "  crontab -l | grep \"$CRON_TAG\""
echo ""
echo "To remove:"
echo "  ./execution/remove_weekly_security_automation.sh"
