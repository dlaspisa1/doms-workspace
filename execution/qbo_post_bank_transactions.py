#!/usr/bin/env python3
"""
Post/categorize pending bank transactions in QuickBooks Online
Helps identify and provide guidance for posting uncategorized transactions
"""

import os
import json
from datetime import datetime, timedelta
from qbo_client import get_client
from qbo_error_handler import handle_exception, QBOError, get_support_info

# Ensure .tmp directory exists
os.makedirs('.tmp/qbo_data', exist_ok=True)


@handle_exception
def main():
    try:
        print("QuickBooks Bank Transaction Posting Guide\n")
        print("="*60)

        client = get_client()
        print(f"Connected to QuickBooks (Realm ID: {client.realm_id})\n")

        print("="*60)
        print("IMPORTANT: Bank Feed Transactions")
        print("="*60)
        print("\nThe QuickBooks API does not provide direct access to")
        print("uncategorized transactions in your Banking feed.")
        print("\nThese transactions are in the 'For Review' tab and must be")
        print("categorized through the QuickBooks Online interface.")
        print("\n" + "="*60)

        print("\n\nHOW TO POST YOUR 33 PENDING TRANSACTIONS:\n")
        print("="*60)

        print("\n1. GO TO BANKING")
        print("   • Log into QuickBooks Online")
        print("   • Click 'Banking' in the left menu")
        print("   • Click on your bank account")

        print("\n2. REVIEW PENDING TRANSACTIONS")
        print("   • You'll see transactions under 'For Review' tab")
        print("   • These are the 33 pending transactions")

        print("\n3. CATEGORIZE EACH TRANSACTION")
        print("   For each transaction:")
        print("   • Select the appropriate category (expense account)")
        print("   • Common categories:")
        print("     - Meals and Entertainment")
        print("     - Vehicle Fuel")
        print("     - Office Supplies")
        print("     - Travel")
        print("     - Utilities")
        print("   • Add vendor name (optional but recommended)")
        print("   • Add memo/note if needed")

        print("\n4. POST THE TRANSACTION")
        print("   • Click 'Categorize' or 'Add' button")
        print("   • Transaction moves from 'For Review' to 'Categorized'")
        print("   • This posts it to your books")

        print("\n5. BULK ACTIONS (FASTER)")
        print("   • Select multiple similar transactions (checkbox)")
        print("   • Use 'Batch actions' at top")
        print("   • Categorize all at once")

        print("\n6. CREATE RULES (SAVES TIME)")
        print("   • For recurring vendors/transactions")
        print("   • Click 'Create rule' on a transaction")
        print("   • Future transactions auto-categorize")

        print("\n" + "="*60)
        print("SUGGESTED WORKFLOW FOR YOUR 33 TRANSACTIONS")
        print("="*60)

        print("\nBased on the 42 transactions I found earlier,")
        print("here's a suggested categorization guide:\n")

        categories = {
            'Vehicle Fuel': 'Circle K, gas stations, fuel purchases',
            'Meals and Entertainment': 'Restaurants, coffee shops, bars',
            'Vehicle Expenses': 'Car wash, maintenance, parking',
            'Vehicle Warranty': 'Vehicle service contracts',
            'Office Supplies': 'Staples, Office Depot, etc.',
            'Bank Fees': 'Service charges, monthly fees',
            'Contributions': 'Charitable donations',
            'Miscellaneous': 'Other business expenses',
        }

        for category, examples in categories.items():
            print(f"\n{category}:")
            print(f"  {examples}")

        print("\n" + "="*60)
        print("TIPS FOR POSTING")
        print("="*60)

        print("\n• Post transactions in chronological order")
        print("• Review each transaction carefully")
        print("• Split transactions if needed (e.g., meal + tip)")
        print("• Exclude personal expenses")
        print("• Create bank rules for recurring transactions")
        print("• Keep receipts for audit purposes")

        print("\n" + "="*60)
        print("\nOnce you've posted all 33 transactions in QuickBooks,")
        print("run this command again to verify they're all categorized:")
        print("\n  python3 execution/qbo_review_bank_transactions.py")
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
