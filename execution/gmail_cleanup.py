"""
Gmail Inbox Cleanup Script
Archives old messages, applies labels, and removes promotional emails
"""

import os
import json
import time
from datetime import datetime, timedelta
from gmail_auth import get_gmail_service

class GmailCleanup:
    def __init__(self, dry_run=True):
        self.service = get_gmail_service()
        self.dry_run = dry_run
        self.stats = {
            'archived': 0,
            'labeled': {},
            'deleted': 0,
            'errors': []
        }

    def archive_old_messages(self, days_old=30):
        """Archive messages older than specified days"""
        print(f"\n{'[DRY RUN] ' if self.dry_run else ''}Archiving messages older than {days_old} days...")

        # Calculate date threshold
        date_threshold = datetime.now() - timedelta(days=days_old)
        query = f"in:inbox before:{date_threshold.strftime('%Y/%m/%d')} -is:starred -is:important"

        try:
            # Get messages matching query
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=500
            ).execute()

            messages = results.get('messages', [])

            if not messages:
                print("  No old messages to archive")
                return

            print(f"  Found {len(messages)} messages to archive")

            if not self.dry_run:
                # Batch modify to remove INBOX label (archive)
                self.service.users().messages().batchModify(
                    userId='me',
                    body={
                        'ids': [msg['id'] for msg in messages],
                        'removeLabelIds': ['INBOX']
                    }
                ).execute()

            self.stats['archived'] = len(messages)
            print(f"  ✓ {'Would archive' if self.dry_run else 'Archived'} {len(messages)} messages")

        except Exception as e:
            error = f"Error archiving messages: {e}"
            print(f"  ✗ {error}")
            self.stats['errors'].append(error)

    def apply_labels(self, label_rules):
        """Apply labels based on rules"""
        print(f"\n{'[DRY RUN] ' if self.dry_run else ''}Applying labels...")

        # Get or create labels
        labels = self._get_or_create_labels(label_rules.keys())

        for label_name, conditions in label_rules.items():
            try:
                # Build query from conditions
                query_parts = ["in:inbox"]

                if 'from' in conditions:
                    from_query = ' OR '.join([f'from:{sender}' for sender in conditions['from']])
                    query_parts.append(f"({from_query})")

                if 'subject' in conditions:
                    subject_query = ' OR '.join([f'subject:{term}' for term in conditions['subject']])
                    query_parts.append(f"({subject_query})")

                query = ' '.join(query_parts)

                # Get matching messages
                results = self.service.users().messages().list(
                    userId='me',
                    q=query,
                    maxResults=500
                ).execute()

                messages = results.get('messages', [])

                if not messages:
                    print(f"  No messages for label '{label_name}'")
                    continue

                print(f"  Found {len(messages)} messages for label '{label_name}'")

                if not self.dry_run:
                    # Apply label
                    label_id = labels[label_name]
                    self.service.users().messages().batchModify(
                        userId='me',
                        body={
                            'ids': [msg['id'] for msg in messages],
                            'addLabelIds': [label_id]
                        }
                    ).execute()

                self.stats['labeled'][label_name] = len(messages)
                print(f"  ✓ {'Would label' if self.dry_run else 'Labeled'} {len(messages)} messages as '{label_name}'")

            except Exception as e:
                error = f"Error labeling '{label_name}': {e}"
                print(f"  ✗ {error}")
                self.stats['errors'].append(error)

    def delete_promotional(self, keywords=None):
        """Delete promotional emails"""
        if keywords is None:
            keywords = ["unsubscribe", "promotional", "newsletter"]

        print(f"\n{'[DRY RUN] ' if self.dry_run else ''}Deleting promotional emails...")

        # Build query for promotional content
        keyword_query = ' OR '.join([f'"{kw}"' for kw in keywords])
        query = f"in:inbox ({keyword_query}) category:promotions"

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
                # Batch trash messages
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

    def _get_or_create_labels(self, label_names):
        """Get existing labels or create new ones"""
        labels = {}

        # Get existing labels
        results = self.service.users().labels().list(userId='me').execute()
        existing_labels = {label['name']: label['id'] for label in results.get('labels', [])}

        for label_name in label_names:
            if label_name in existing_labels:
                labels[label_name] = existing_labels[label_name]
            else:
                if not self.dry_run:
                    # Create new label
                    label = self.service.users().labels().create(
                        userId='me',
                        body={'name': label_name}
                    ).execute()
                    labels[label_name] = label['id']
                    print(f"  Created new label: '{label_name}'")
                else:
                    labels[label_name] = f"DRY_RUN_{label_name}"
                    print(f"  Would create new label: '{label_name}'")

        return labels

    def save_log(self):
        """Save cleanup log to .tmp directory"""
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
    print("Gmail Inbox Cleanup")
    print("=" * 60)

    # Configuration
    config = {
        'days_to_archive': 30,
        'promotional_keywords': ["unsubscribe", "promotional", "newsletter"],
        'label_rules': {
            'receipts': {
                'subject': ['receipt', 'order confirmation', 'invoice']
            },
            'social': {
                'from': ['facebook.com', 'linkedin.com', 'twitter.com']
            }
        },
        'dry_run': True  # Change to False to execute
    }

    print(f"\nConfiguration:")
    print(f"  Archive messages older than: {config['days_to_archive']} days")
    print(f"  Label rules: {len(config['label_rules'])} categories")
    print(f"  Dry run: {config['dry_run']}")

    # Execute cleanup
    cleanup = GmailCleanup(dry_run=config['dry_run'])

    cleanup.archive_old_messages(days_old=config['days_to_archive'])
    cleanup.apply_labels(config['label_rules'])
    cleanup.delete_promotional(keywords=config['promotional_keywords'])

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Messages archived: {cleanup.stats['archived']}")
    print(f"  Messages labeled: {sum(cleanup.stats['labeled'].values())}")
    for label, count in cleanup.stats['labeled'].items():
        print(f"    - {label}: {count}")
    print(f"  Messages deleted: {cleanup.stats['deleted']}")
    if cleanup.stats['errors']:
        print(f"  Errors: {len(cleanup.stats['errors'])}")
        for error in cleanup.stats['errors']:
            print(f"    - {error}")

    # Save log
    cleanup.save_log()

if __name__ == "__main__":
    main()
