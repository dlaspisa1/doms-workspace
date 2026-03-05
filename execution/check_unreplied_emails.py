"""
Check for important unreplied emails in Gmail inbox
"""

from datetime import datetime
from gmail_auth import get_gmail_service

def check_unreplied_emails():
    """Find important emails that haven't been replied to"""
    service = get_gmail_service()

    print("=" * 80)
    print("Checking for Important Unreplied Emails")
    print("=" * 80)
    print()

    # Query for important/unread messages in inbox that we haven't replied to
    # -label:sent means we haven't sent anything in that thread
    query = 'in:inbox (is:important OR is:unread OR is:starred) -from:me'

    try:
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=50
        ).execute()

        messages = results.get('messages', [])

        if not messages:
            print("✓ No unreplied important emails found!")
            return

        print(f"Found {len(messages)} messages requiring attention:\n")

        unreplied = []

        for msg in messages:
            # Get message details
            msg_data = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='full'
            ).execute()

            # Extract headers
            headers = msg_data.get('payload', {}).get('headers', [])
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            date_str = next((h['value'] for h in headers if h['name'] == 'Date'), '')

            # Get labels
            labels = msg_data.get('labelIds', [])

            # Check if we've replied to this thread
            thread_id = msg_data.get('threadId')
            thread_data = service.users().threads().get(
                userId='me',
                id=thread_id
            ).execute()

            # Check if any message in thread is from us
            has_reply = False
            for thread_msg in thread_data.get('messages', []):
                thread_headers = thread_msg.get('payload', {}).get('headers', [])
                thread_from = next((h['value'] for h in thread_headers if h['name'] == 'From'), '')
                # Simple check - if our email is in the From field, we've replied
                # Note: This is a simple heuristic and might need the actual user email
                if thread_msg['id'] != msg['id'] and 'SENT' in thread_msg.get('labelIds', []):
                    has_reply = True
                    break

            if not has_reply:
                status_flags = []
                if 'UNREAD' in labels:
                    status_flags.append('UNREAD')
                if 'IMPORTANT' in labels:
                    status_flags.append('IMPORTANT')
                if 'STARRED' in labels:
                    status_flags.append('STARRED')

                unreplied.append({
                    'sender': sender,
                    'subject': subject,
                    'date': date_str,
                    'flags': status_flags,
                    'id': msg['id']
                })

        # Sort by date (newest first) and display
        for i, email in enumerate(unreplied[:20], 1):  # Show top 20
            flags_str = ' | '.join(email['flags'])
            print(f"{i}. [{flags_str}]")
            print(f"   From: {email['sender']}")
            print(f"   Subject: {email['subject']}")
            print(f"   Date: {email['date'][:25]}")  # Truncate date for readability
            print()

        if len(unreplied) > 20:
            print(f"... and {len(unreplied) - 20} more")

        print(f"\nTotal unreplied messages: {len(unreplied)}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_unreplied_emails()
