"""
Delete specific Gmail messages by message ID
"""

from gmail_auth import get_gmail_service
import sys

def delete_messages(message_ids):
    """Delete specific messages by their IDs"""
    service = get_gmail_service()

    print("=" * 80)
    print("Deleting Specific Messages")
    print("=" * 80)
    print(f"Message IDs to delete: {len(message_ids)}")
    print()

    try:
        # Move messages to trash
        service.users().messages().batchModify(
            userId='me',
            body={
                'ids': message_ids,
                'addLabelIds': ['TRASH']
            }
        ).execute()

        print(f"✓ Successfully moved {len(message_ids)} messages to trash")

    except Exception as e:
        print(f"✗ Error deleting messages: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # U.S. Bank suspicious emails
    MESSAGE_IDS = [
        '19b68a8efc2fe1c0',
        '19ab8f73f7cbbb75'
    ]

    delete_messages(MESSAGE_IDS)
