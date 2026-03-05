"""
List all existing Gmail labels
"""
from gmail_auth import get_gmail_service

def list_labels():
    service = get_gmail_service()
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])

    print("\n" + "="*60)
    print("Existing Gmail Labels")
    print("="*60)

    user_labels = [l for l in labels if l['type'] == 'user']
    system_labels = [l for l in labels if l['type'] == 'system']

    print(f"\nUser Labels ({len(user_labels)}):")
    for label in sorted(user_labels, key=lambda x: x['name']):
        print(f"  - {label['name']}")

    print(f"\nSystem Labels ({len(system_labels)}):")
    for label in sorted(system_labels, key=lambda x: x['name']):
        print(f"  - {label['name']}")

    return user_labels, system_labels

if __name__ == "__main__":
    list_labels()
