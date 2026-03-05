"""
Smart Gmail Inbox Cleanup Script
Intelligently categorizes emails into existing folders and archives old messages
"""

import os
import json
import re
from datetime import datetime, timedelta
from gmail_auth import get_gmail_service

class SmartGmailCleanup:
    def __init__(self, dry_run=True):
        self.service = get_gmail_service()
        self.dry_run = dry_run
        self.stats = {
            'archived': 0,
            'labeled': {},
            'deleted': 0,
            'duplicates_archived': 0,
            'skipped_important': 0,
            'errors': []
        }
        self.existing_labels = {}
        self.label_cache = {}
        self._load_existing_labels()

    def _load_existing_labels(self):
        """Load all existing user labels"""
        results = self.service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])

        for label in labels:
            if label['type'] == 'user':
                self.existing_labels[label['name']] = label['id']
                # Also index by lowercase for matching
                self.label_cache[label['name'].lower()] = label['id']

        print(f"Loaded {len(self.existing_labels)} existing labels")

    def _match_to_existing_label(self, sender, subject, body_snippet=""):
        """Intelligently match email to existing label based on content"""
        sender_lower = sender.lower()
        subject_lower = subject.lower()
        snippet_lower = body_snippet.lower()

        # Category matching patterns
        patterns = {
            # Real Estate
            'Folders/Real Estate': [
                'realtor', 'zillow', 'trulia', 'redfin', 'mortgage',
                'property', 'real estate', 'lease', 'rent'
            ],
            'Folders/Receipts': [
                'receipt', 'invoice', 'order confirmation', 'your order',
                'payment received', 'transaction', 'purchase'
            ],
            'Folders/Amazon': ['amazon.com', 'aws'],
            'Folders/Medical': [
                'doctor', 'medical', 'health', 'prescription', 'pharmacy',
                'clinic', 'hospital', 'patient'
            ],
            'Folders/Insurance': [
                'insurance', 'policy', 'claim', 'premium', 'coverage'
            ],
            'Folders/Travel & Leisure': [
                'booking', 'hotel', 'flight', 'airline', 'reservation',
                'trip', 'travel', 'itinerary'
            ],
            'Folders/Career': [
                'linkedin', 'indeed', 'job', 'career', 'resume',
                'application', 'interview'
            ],
            'Folders/Investments': [
                'vanguard', 'schwab', 'fidelity', 'etrade', 'investment',
                'portfolio', 'dividend', 'stock'
            ],
            'Folders/Income Taxes': [
                'irs', 'tax', 'form 1099', 'w-2', 'tax return',
                'turbotax', 'h&r block'
            ],
            'Folders/Concierge': ['concierge'],
            'Folders/DoorDash': ['doordash'],
            'Folders/Lyft': ['lyft'],
            'Folders/Ebay': ['ebay'],
            'Folders/Alibaba': ['alibaba'],
        }

        # Check patterns
        for label_name, keywords in patterns.items():
            if label_name in self.existing_labels:
                for keyword in keywords:
                    if (keyword in sender_lower or
                        keyword in subject_lower or
                        keyword in snippet_lower):
                        return label_name

        # Check for specific senders that match folder names
        for label_name in self.existing_labels.keys():
            # Extract company name from folder path
            if label_name.startswith('Folders/'):
                company = label_name.split('/')[-1].lower()
                if company in sender_lower:
                    return label_name

        return None

    def _is_important_email(self, message_data):
        """Determine if email should be kept in inbox (not archived)"""
        labels = message_data.get('labelIds', [])

        # Keep if starred, important, or unread
        if 'STARRED' in labels or 'IMPORTANT' in labels or 'UNREAD' in labels:
            return True

        return False

    def categorize_inbox(self, max_messages=1000):
        """Categorize emails in inbox to appropriate folders"""
        print(f"\n{'[DRY RUN] ' if self.dry_run else ''}Categorizing inbox messages...")

        try:
            # Get messages from inbox
            results = self.service.users().messages().list(
                userId='me',
                q='in:inbox',
                maxResults=max_messages
            ).execute()

            messages = results.get('messages', [])

            if not messages:
                print("  No messages to categorize")
                return

            print(f"  Analyzing {len(messages)} messages...")
            categorized = {}

            # Process each message
            for i, msg in enumerate(messages):
                if i % 50 == 0:
                    print(f"  Processing message {i+1}/{len(messages)}...")

                try:
                    # Get message details
                    msg_data = self.service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='metadata',
                        metadataHeaders=['From', 'Subject']
                    ).execute()

                    # Extract headers
                    headers = msg_data.get('payload', {}).get('headers', [])
                    sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
                    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
                    snippet = msg_data.get('snippet', '')

                    # Skip important emails
                    if self._is_important_email(msg_data):
                        self.stats['skipped_important'] += 1
                        continue

                    # Match to existing label
                    matched_label = self._match_to_existing_label(sender, subject, snippet)

                    if matched_label:
                        if matched_label not in categorized:
                            categorized[matched_label] = []
                        categorized[matched_label].append(msg['id'])

                except Exception as e:
                    error = f"Error processing message {msg['id']}: {e}"
                    self.stats['errors'].append(error)
                    continue

            # Apply labels
            for label_name, message_ids in categorized.items():
                if not self.dry_run:
                    # Apply label in batches
                    for batch_start in range(0, len(message_ids), 1000):
                        batch = message_ids[batch_start:batch_start+1000]
                        self.service.users().messages().batchModify(
                            userId='me',
                            body={
                                'ids': batch,
                                'addLabelIds': [self.existing_labels[label_name]]
                            }
                        ).execute()

                self.stats['labeled'][label_name] = len(message_ids)
                print(f"  ✓ {'Would label' if self.dry_run else 'Labeled'} {len(message_ids)} messages as '{label_name}'")

            print(f"\n  Total categorized: {sum(len(ids) for ids in categorized.values())}")
            print(f"  Skipped (important): {self.stats['skipped_important']}")

        except Exception as e:
            error = f"Error categorizing inbox: {e}"
            print(f"  ✗ {error}")
            self.stats['errors'].append(error)

    def archive_old_messages(self, days_old=270):
        """Archive messages older than specified days (9 months = 270 days)"""
        print(f"\n{'[DRY RUN] ' if self.dry_run else ''}Archiving messages older than {days_old} days ({days_old//30} months)...")

        date_threshold = datetime.now() - timedelta(days=days_old)
        query = f"in:inbox before:{date_threshold.strftime('%Y/%m/%d')} -is:starred -is:important -is:unread"

        try:
            # Get old messages
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=1000
            ).execute()

            messages = results.get('messages', [])

            if not messages:
                print("  No old messages to archive")
                return

            print(f"  Found {len(messages)} messages to archive")

            if not self.dry_run:
                # Archive in batches
                for batch_start in range(0, len(messages), 1000):
                    batch = messages[batch_start:batch_start+1000]
                    self.service.users().messages().batchModify(
                        userId='me',
                        body={
                            'ids': [msg['id'] for msg in batch],
                            'removeLabelIds': ['INBOX']
                        }
                    ).execute()

            self.stats['archived'] = len(messages)
            print(f"  ✓ {'Would archive' if self.dry_run else 'Archived'} {len(messages)} messages")

        except Exception as e:
            error = f"Error archiving messages: {e}"
            print(f"  ✗ {error}")
            self.stats['errors'].append(error)

    def delete_promotional(self, keywords=None):
        """Delete promotional emails"""
        if keywords is None:
            keywords = ["unsubscribe", "promotional", "newsletter", "marketing"]

        print(f"\n{'[DRY RUN] ' if self.dry_run else ''}Deleting promotional emails...")

        # Build query
        keyword_query = ' OR '.join([f'"{kw}"' for kw in keywords])
        query = f"in:inbox ({keyword_query}) category:promotions -is:starred"

        try:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=500
            ).execute()

            messages = results.get('messages', [])

            if not messages:
                print("  No promotional emails to delete")
                return

            print(f"  Found {len(messages)} promotional messages")

            if not self.dry_run:
                self.service.users().messages().batchModify(
                    userId='me',
                    body={
                        'ids': [msg['id'] for msg in messages],
                        'addLabelIds': ['TRASH']
                    }
                ).execute()

            self.stats['deleted'] = len(messages)
            print(f"  ✓ {'Would delete' if self.dry_run else 'Deleted'} {len(messages)} promotional messages")

        except Exception as e:
            error = f"Error deleting promotional emails: {e}"
            print(f"  ✗ {error}")
            self.stats['errors'].append(error)

    def detect_and_archive_duplicates(self, max_messages=2000):
        """Detect and archive duplicate emails"""
        print(f"\n{'[DRY RUN] ' if self.dry_run else ''}Detecting duplicate emails...")

        try:
            # Get messages from inbox
            results = self.service.users().messages().list(
                userId='me',
                q='in:inbox',
                maxResults=max_messages
            ).execute()

            messages = results.get('messages', [])

            if not messages:
                print("  No messages to check for duplicates")
                return

            print(f"  Analyzing {len(messages)} messages for duplicates...")

            # Track messages by (sender, subject, date)
            seen_messages = {}
            duplicates = []

            for i, msg in enumerate(messages):
                if i % 100 == 0:
                    print(f"  Checking message {i+1}/{len(messages)}...")

                try:
                    # Get message details
                    msg_data = self.service.users().messages().get(
                        userId='me',
                        id=msg['id'],
                        format='metadata',
                        metadataHeaders=['From', 'Subject', 'Date']
                    ).execute()

                    # Skip if important
                    if self._is_important_email(msg_data):
                        continue

                    # Extract headers
                    headers = msg_data.get('payload', {}).get('headers', [])
                    sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
                    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
                    date_str = next((h['value'] for h in headers if h['name'] == 'Date'), '')

                    # Create signature (sender + subject + date-prefix for grouping by day)
                    # Use first 10 chars of date to group by day
                    signature = f"{sender}||{subject}||{date_str[:10]}"

                    if signature in seen_messages:
                        # This is a duplicate - keep the first one, mark this for archiving
                        duplicates.append(msg['id'])
                    else:
                        seen_messages[signature] = msg['id']

                except Exception as e:
                    error = f"Error checking message {msg['id']}: {e}"
                    self.stats['errors'].append(error)
                    continue

            if not duplicates:
                print("  No duplicate messages found")
                return

            print(f"  Found {len(duplicates)} duplicate messages")

            if not self.dry_run:
                # Archive duplicates in batches
                for batch_start in range(0, len(duplicates), 1000):
                    batch = duplicates[batch_start:batch_start+1000]
                    self.service.users().messages().batchModify(
                        userId='me',
                        body={
                            'ids': batch,
                            'removeLabelIds': ['INBOX']
                        }
                    ).execute()

            self.stats['duplicates_archived'] = len(duplicates)
            print(f"  ✓ {'Would archive' if self.dry_run else 'Archived'} {len(duplicates)} duplicate messages")

        except Exception as e:
            error = f"Error detecting duplicates: {e}"
            print(f"  ✗ {error}")
            self.stats['errors'].append(error)

    def save_log(self):
        """Save cleanup log"""
        os.makedirs('.tmp', exist_ok=True)

        log_file = f".tmp/gmail_cleanup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'dry_run': self.dry_run,
            'stats': self.stats
        }

        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2)

        print(f"\n✓ Log saved to {log_file}")

def main():
    """Main execution"""
    print("=" * 60)
    print("Smart Gmail Inbox Cleanup")
    print("=" * 60)

    # Configuration
    config = {
        'days_to_archive': 270,  # 9 months
        'max_messages_to_categorize': 1000,
        'max_messages_for_duplicate_check': 2000,
        'promotional_keywords': ["unsubscribe", "promotional", "newsletter", "marketing"],
        'enable_duplicate_detection': True,
        'dry_run': False  # Change to False to execute
    }

    print(f"\nConfiguration:")
    print(f"  Archive messages older than: {config['days_to_archive']} days ({config['days_to_archive']//30} months)")
    print(f"  Max messages to categorize: {config['max_messages_to_categorize']}")
    print(f"  Duplicate detection: {'Enabled' if config['enable_duplicate_detection'] else 'Disabled'}")
    print(f"  Dry run: {config['dry_run']}")
    print()

    # Execute cleanup
    cleanup = SmartGmailCleanup(dry_run=config['dry_run'])

    # Step 1: Categorize inbox messages into existing folders
    cleanup.categorize_inbox(max_messages=config['max_messages_to_categorize'])

    # Step 2: Detect and archive duplicates
    if config['enable_duplicate_detection']:
        cleanup.detect_and_archive_duplicates(max_messages=config['max_messages_for_duplicate_check'])

    # Step 3: Archive old messages (9 months+)
    cleanup.archive_old_messages(days_old=config['days_to_archive'])

    # Step 4: Delete promotional emails
    cleanup.delete_promotional(keywords=config['promotional_keywords'])

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Messages categorized: {sum(cleanup.stats['labeled'].values())}")
    if cleanup.stats['labeled']:
        print(f"  Breakdown by label:")
        for label, count in sorted(cleanup.stats['labeled'].items(), key=lambda x: -x[1])[:10]:
            print(f"    - {label}: {count}")
        if len(cleanup.stats['labeled']) > 10:
            print(f"    ... and {len(cleanup.stats['labeled']) - 10} more")
    print(f"  Important emails skipped: {cleanup.stats['skipped_important']}")
    print(f"  Duplicates archived: {cleanup.stats['duplicates_archived']}")
    print(f"  Old messages archived: {cleanup.stats['archived']}")
    print(f"  Promotional emails deleted: {cleanup.stats['deleted']}")
    if cleanup.stats['errors']:
        print(f"  Errors: {len(cleanup.stats['errors'])}")
        for error in cleanup.stats['errors'][:5]:
            print(f"    - {error}")
        if len(cleanup.stats['errors']) > 5:
            print(f"    ... and {len(cleanup.stats['errors']) - 5} more errors")

    # Save log
    cleanup.save_log()

if __name__ == "__main__":
    main()
