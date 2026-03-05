#!/usr/bin/env python3
"""
Bulk assign vendors to posted bank transactions in QuickBooks Online
Updates purchase transactions that are missing vendor information
"""

import os
import json
import re
from qbo_client import get_client
from qbo_error_handler import handle_exception, QBOError, get_support_info
from quickbooks.objects.purchase import Purchase
from quickbooks.objects.vendor import Vendor

# Ensure .tmp directory exists
os.makedirs('.tmp/qbo_data', exist_ok=True)


def extract_vendor_name(description):
    """Extract likely vendor name from transaction description"""
    if not description:
        return None

    # Common patterns to clean up
    description = description.strip()

    # Remove location codes (e.g., "X6656", "#1111")
    description = re.sub(r'\s+[X#]\d+', '', description)
    description = re.sub(r'\s+FX\d+', '', description)

    # Remove common prefixes
    prefixes = ['SQ *', 'TST*', 'SP ', 'LS ', 'WWW.', 'CR ']
    for prefix in prefixes:
        if description.startswith(prefix):
            description = description[len(prefix):]

    # Clean up
    description = description.strip()

    # Common vendor name mappings
    vendor_mappings = {
        'CIRCLE K': 'Circle K',
        'PEIXOTO COFFEE': 'Peixoto Coffee',
        'SHATERA': 'Shatera',
        'MCDONALD': "McDonald's",
        'BUCK AND RIDER': 'Buck and Rider',
        'TREVORS LIQUOR': 'Trevors Liquor',
        'TREVOR': 'Trevors Liquor',
        'WICKED SIX BAR': 'Wicked Six Bar & Grill',
        'SASQUATCHO TACO': 'Sasquatcho Taco',
        'ELEPHANTE': 'Elephante',
        'SALAD AND GO': 'Salad and Go',
        'GREATHEARTSAMERICA': 'Great Hearts America',
        'VALUETAINMENT': 'Valuetainment',
        'MOTORS OF ADRIAN': 'CR Motors of Adrian',
        'LINDSAY CAR WASH': 'Lindsay Car Wash',
        'SWIG': 'Swig',
        'CHICK-FIL-A': 'Chick-fil-A',
        'CHICK FIL': 'Chick-fil-A',
        'IN-N-OUT': 'In-N-Out Burger',
        'PORTILLOS': "Portillo's",
        'PORTILLO': "Portillo's",
    }

    # Check for known vendors
    description_upper = description.upper()
    for key, vendor in vendor_mappings.items():
        if key in description_upper:
            return vendor

    # Return cleaned description as vendor name
    return description.title()


def find_or_create_vendor(client, vendor_name):
    """Find existing vendor or create new one"""
    if not vendor_name or vendor_name == 'Unknown':
        return None

    # Search for existing vendor (case-insensitive)
    try:
        # Try exact match first
        query = f"SELECT * FROM Vendor WHERE DisplayName = '{vendor_name}' MAXRESULTS 1"
        vendors = Vendor.query(query, qb=client.client)

        if vendors:
            print(f"  ✓ Found existing vendor: {vendor_name}")
            return vendors[0]
    except Exception as e:
        print(f"  Warning: Could not search for vendor '{vendor_name}': {e}")

    # Create new vendor
    try:
        vendor = Vendor()
        vendor.DisplayName = vendor_name
        vendor.save(qb=client.client)
        print(f"  ✓ Created new vendor: {vendor_name}")
        return vendor
    except Exception as e:
        print(f"  ✗ Could not create vendor '{vendor_name}': {e}")
        return None


def update_purchase_with_vendor(client, purchase_id, vendor):
    """Update a purchase transaction with vendor information"""
    try:
        # Fetch the purchase
        purchase = Purchase.get(purchase_id, qb=client.client)

        # Create vendor reference
        from quickbooks.objects.base import Ref
        vendor_ref = Ref()
        vendor_ref.name = vendor.DisplayName
        vendor_ref.value = vendor.Id

        # Update vendor reference
        purchase.EntityRef = vendor_ref

        # Save the updated purchase
        purchase.save(qb=client.client)

        return True
    except Exception as e:
        print(f"  ✗ Error updating purchase {purchase_id}: {e}")
        return False


@handle_exception
def main():
    try:
        print("QuickBooks Bulk Vendor Assignment\n")
        print("="*60)

        client = get_client()
        print(f"Connected to QuickBooks (Realm ID: {client.realm_id})\n")

        # Load pending transactions
        transactions_file = '.tmp/qbo_data/bank_transactions.json'
        if not os.path.exists(transactions_file):
            print("✗ No transaction data found.")
            print("  Run: python3 execution/qbo_review_bank_transactions.py first")
            return

        with open(transactions_file, 'r') as f:
            data = json.load(f)

        needs_review = data['purchases']['needs_review']

        if not needs_review:
            print("✓ No transactions need vendor assignment!")
            return

        print(f"Found {len(needs_review)} transactions needing vendor assignment\n")

        # Process transactions
        results = {
            'updated': [],
            'skipped': [],
            'errors': []
        }

        # Group by vendor for efficiency
        by_vendor = {}
        for txn in needs_review:
            # Extract vendor name from description
            description = txn['private_note'] or txn['line_items'][0].get('description', '')
            vendor_name = extract_vendor_name(description)

            if not vendor_name:
                vendor_name = 'Unknown'

            if vendor_name not in by_vendor:
                by_vendor[vendor_name] = []
            by_vendor[vendor_name].append(txn)

        print(f"Identified {len(by_vendor)} unique vendors\n")
        print("Processing transactions by vendor...\n")

        vendor_cache = {}

        for vendor_name, transactions in sorted(by_vendor.items()):
            print(f"\n{vendor_name} - {len(transactions)} transaction(s)")
            print("-" * 60)

            # Skip if vendor name is Unknown
            if vendor_name == 'Unknown':
                print(f"  ⚠ Skipping - could not identify vendor from description")
                for txn in transactions:
                    results['skipped'].append({
                        'id': txn['id'],
                        'date': txn['date'],
                        'amount': txn['amount'],
                        'description': txn['private_note'],
                        'reason': 'No vendor name identified'
                    })
                continue

            # Get or create vendor
            if vendor_name in vendor_cache:
                vendor = vendor_cache[vendor_name]
            else:
                vendor = find_or_create_vendor(client, vendor_name)
                vendor_cache[vendor_name] = vendor

            if not vendor:
                print(f"  ⚠ Skipping - could not find/create vendor")
                for txn in transactions:
                    results['skipped'].append({
                        'id': txn['id'],
                        'date': txn['date'],
                        'amount': txn['amount'],
                        'description': txn['private_note'],
                        'reason': 'Could not create vendor'
                    })
                continue

            # Update each transaction
            for txn in transactions:
                success = update_purchase_with_vendor(client, txn['id'], vendor)

                if success:
                    print(f"  ✓ Updated ${txn['amount']:.2f} on {txn['date']}")
                    results['updated'].append({
                        'id': txn['id'],
                        'date': txn['date'],
                        'amount': txn['amount'],
                        'vendor': vendor_name,
                        'description': txn['private_note']
                    })
                else:
                    results['errors'].append({
                        'id': txn['id'],
                        'date': txn['date'],
                        'amount': txn['amount'],
                        'vendor': vendor_name,
                        'description': txn['private_note']
                    })

        # Save results
        results_file = '.tmp/qbo_data/vendor_assignment_results.json'
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)

        # Print summary
        print("\n" + "="*60)
        print("VENDOR ASSIGNMENT COMPLETE")
        print("="*60)

        print(f"\n✓ Updated: {len(results['updated'])} transactions")
        if results['updated']:
            total = sum(t['amount'] for t in results['updated'])
            print(f"  Total Amount: ${total:,.2f}")

        print(f"\n⚠ Skipped: {len(results['skipped'])} transactions")
        if results['skipped']:
            total = sum(t['amount'] for t in results['skipped'])
            print(f"  Total Amount: ${total:,.2f}")
            print("\n  Skipped transactions:")
            for txn in results['skipped'][:5]:
                print(f"    - {txn['date']}: ${txn['amount']:.2f} - {txn['description'][:50]}")
            if len(results['skipped']) > 5:
                print(f"    ... and {len(results['skipped']) - 5} more")

        print(f"\n✗ Errors: {len(results['errors'])} transactions")
        if results['errors']:
            total = sum(t['amount'] for t in results['errors'])
            print(f"  Total Amount: ${total:,.2f}")

        print(f"\n✓ Results saved to {results_file}")

        if results['updated']:
            print("\n" + "="*60)
            print("NEXT STEPS: SET UP BANK RULES")
            print("="*60)
            print("\nTo automate vendor assignment for future transactions:")
            print("\n1. Log into QuickBooks Online")
            print("2. Go to Banking → Rules")
            print("3. Click 'New Rule'")
            print("\nCreate rules for your most common vendors:")

            # Get top vendors
            vendor_counts = {}
            for txn in results['updated']:
                vendor = txn['vendor']
                vendor_counts[vendor] = vendor_counts.get(vendor, 0) + 1

            top_vendors = sorted(vendor_counts.items(), key=lambda x: x[1], reverse=True)[:5]

            for vendor, count in top_vendors:
                print(f"\n• {vendor} ({count} transactions)")
                print(f"  Rule: If description contains '{vendor}'")
                print(f"  Then: Assign to vendor '{vendor}'")

        print("\n" + "="*60)

    except QBOError as e:
        print(f"\n✗ QuickBooks Error: {e.message}")
        if e.intuit_tid:
            print(f"  Transaction ID: {e.intuit_tid}")
        print(f"\n{get_support_info()['message']}")
        raise
    except Exception as e:
        print(f"\n✗ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        print(f"\n{get_support_info()['message']}")
        raise


if __name__ == '__main__':
    main()
