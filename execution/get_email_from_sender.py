"""
Get email from specific sender on specific date and extract attachments
"""

import base64
import os
from datetime import datetime, timedelta
from gmail_auth import get_gmail_service

def get_email_from_dalila(date_str=None):
    """
    Get email from Dalila on specified date and download attachments

    Args:
        date_str: Date in format YYYY/MM/DD (defaults to today)
    """
    service = get_gmail_service()

    # Default to today if not specified
    if not date_str:
        date_str = datetime.now().strftime('%Y/%m/%d')

    print(f"Searching for emails from Dalila on {date_str}...")

    # Search query for emails from Dalila on specific date
    query = f'from:dalila after:{date_str} before:{date_str}'

    try:
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=10
        ).execute()

        messages = results.get('messages', [])

        if not messages:
            print(f"No emails found from Dalila on {date_str}")
            # Try searching without date restriction
            print("\nSearching for recent emails from Dalila...")
            results = service.users().messages().list(
                userId='me',
                q='from:dalila',
                maxResults=5
            ).execute()
            messages = results.get('messages', [])

            if not messages:
                print("No emails found from Dalila at all")
                return None

        print(f"\nFound {len(messages)} email(s) from Dalila\n")

        for idx, msg in enumerate(messages, 1):
            # Get full message details
            msg_data = service.users().messages().get(
                userId='me',
                id=msg['id'],
                format='full'
            ).execute()

            # Extract headers
            headers = msg_data.get('payload', {}).get('headers', [])
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), '')

            print(f"Email #{idx}")
            print(f"From: {sender}")
            print(f"Subject: {subject}")
            print(f"Date: {date}")
            print("-" * 80)

            # Check for attachments
            payload = msg_data.get('payload', {})
            attachments = []

            def extract_attachments(part, prefix=""):
                """Recursively extract attachments from message parts"""
                if 'parts' in part:
                    for subpart in part['parts']:
                        extract_attachments(subpart, prefix + "  ")

                filename = part.get('filename', '')
                if filename:
                    attachment_id = part.get('body', {}).get('attachmentId')
                    if attachment_id:
                        print(f"{prefix}Found attachment: {filename}")
                        attachments.append({
                            'filename': filename,
                            'attachment_id': attachment_id,
                            'mime_type': part.get('mimeType', '')
                        })

            extract_attachments(payload)

            # Download attachments
            if attachments:
                os.makedirs('.tmp/email_attachments', exist_ok=True)

                for att in attachments:
                    print(f"\nDownloading: {att['filename']}")

                    attachment = service.users().messages().attachments().get(
                        userId='me',
                        messageId=msg['id'],
                        id=att['attachment_id']
                    ).execute()

                    file_data = base64.urlsafe_b64decode(attachment['data'])
                    filepath = os.path.join('.tmp/email_attachments', att['filename'])

                    with open(filepath, 'wb') as f:
                        f.write(file_data)

                    print(f"Saved to: {filepath}")

                print(f"\nTotal attachments downloaded: {len(attachments)}")
                return filepath  # Return path to last attachment
            else:
                print("No attachments found in this email")

            print("\n" + "=" * 80 + "\n")

        return None

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    get_email_from_dalila()
