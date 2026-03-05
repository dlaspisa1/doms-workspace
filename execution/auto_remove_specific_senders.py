"""
Auto-remove emails from specific senders after N days
"""

from datetime import datetime, timedelta
from gmail_auth import get_gmail_service

def auto_remove_old_emails(sender_domains, days_old=7, dry_run=True):
    """
    Remove emails from specific senders older than specified days

    Args:
        sender_domains: List of sender domains/addresses to target
        days_old: Number of days old before removal (default 7)
        dry_run: Preview actions without executing
    """
    service = get_gmail_service()

    print("=" * 80)
    print(f"{'[DRY RUN] ' if dry_run else ''}Auto-Remove Old Emails from Specific Senders")
    print("=" * 80)
    print(f"Target senders: {', '.join(sender_domains)}")
    print(f"Remove emails older than: {days_old} days")
    print()

    date_threshold = datetime.now() - timedelta(days=days_old)
    total_removed = 0

    for sender in sender_domains:
        print(f"\nChecking emails from: {sender}")

        # Build query
        query = f'from:{sender} before:{date_threshold.strftime("%Y/%m/%d")} -is:starred'

        try:
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=500
            ).execute()

            messages = results.get('messages', [])

            if not messages:
                print(f"  No old messages found from {sender}")
                continue

            print(f"  Found {len(messages)} messages to remove")

            if not dry_run:
                # Move to trash in batches
                for batch_start in range(0, len(messages), 1000):
                    batch = messages[batch_start:batch_start+1000]
                    service.users().messages().batchModify(
                        userId='me',
                        body={
                            'ids': [msg['id'] for msg in batch],
                            'addLabelIds': ['TRASH']
                        }
                    ).execute()

            total_removed += len(messages)
            print(f"  ✓ {'Would remove' if dry_run else 'Removed'} {len(messages)} messages")

        except Exception as e:
            print(f"  ✗ Error processing {sender}: {e}")

    print(f"\n{'=' * 80}")
    print(f"Total messages {'would be removed' if dry_run else 'removed'}: {total_removed}")
    print(f"{'=' * 80}")

if __name__ == "__main__":
    # Configuration
    SENDERS_TO_AUTO_REMOVE = [
        'redfin.com',
        'instacart.com'
    ]

    DAYS_OLD = 7
    DRY_RUN = True  # Set to False to actually remove

    auto_remove_old_emails(
        sender_domains=SENDERS_TO_AUTO_REMOVE,
        days_old=DAYS_OLD,
        dry_run=DRY_RUN
    )
