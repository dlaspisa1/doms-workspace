#!/usr/bin/env python3
"""
Review bank transactions in QuickBooks Online
Identifies transactions that need to be categorized or posted
"""

import os
import json
from datetime import datetime, timedelta
from qbo_client import get_client
from qbo_error_handler import handle_exception, QBOError, get_support_info
from quickbooks.objects.deposit import Deposit
from quickbooks.objects.purchase import Purchase

# Ensure .tmp directory exists
os.makedirs('.tmp/qbo_data', exist_ok=True)


def get_bank_transactions(client, days_back=90):
    """Fetch recent bank transactions"""
    print(f"Fetching bank transactions from last {days_back} days...")

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    # Query for purchases (expenses, checks, credit card charges)
    purchase_query = f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date.strftime('%Y-%m-%d')}' MAXRESULTS 1000"
    purchases = Purchase.query(purchase_query, qb=client.client)

    # Query for deposits
    deposit_query = f"SELECT * FROM Deposit WHERE TxnDate >= '{start_date.strftime('%Y-%m-%d')}' MAXRESULTS 1000"
    deposits = Deposit.query(deposit_query, qb=client.client)

    return purchases, deposits


def analyze_purchases(purchases):
    """Analyze purchase transactions"""
    uncategorized = []
    needs_review = []
    categorized = []

    for purchase in purchases:
        # Get account info
        account_ref = getattr(purchase, 'AccountRef', None)
        account_name = account_ref.name if account_ref else 'Unknown'

        # Get payment info
        payment_type = getattr(purchase, 'PaymentType', 'Unknown')

        # Get entity (vendor/customer)
        entity_ref = getattr(purchase, 'EntityRef', None)
        entity_name = entity_ref.name if entity_ref else None

        # Get line items
        line_items = getattr(purchase, 'Line', [])

        txn_data = {
            'id': purchase.Id,
            'date': str(purchase.TxnDate),
            'amount': float(purchase.TotalAmt) if purchase.TotalAmt else 0.0,
            'payment_type': payment_type,
            'account': account_name,
            'entity': entity_name,
            'doc_number': getattr(purchase, 'DocNumber', None),
            'private_note': getattr(purchase, 'PrivateNote', None),
            'line_count': len(line_items),
            'line_items': []
        }

        # Analyze line items
        for line in line_items:
            line_detail = {
                'amount': float(getattr(line, 'Amount', 0)),
                'description': getattr(line, 'Description', None),
            }

            # Check for account-based expense
            if hasattr(line, 'AccountBasedExpenseLineDetail'):
                detail = line.AccountBasedExpenseLineDetail
                account = getattr(detail, 'AccountRef', None)
                line_detail['category'] = account.name if account else 'Uncategorized'
                line_detail['type'] = 'AccountBased'
            # Check for item-based expense
            elif hasattr(line, 'ItemBasedExpenseLineDetail'):
                detail = line.ItemBasedExpenseLineDetail
                item = getattr(detail, 'ItemRef', None)
                line_detail['category'] = item.name if item else 'Uncategorized'
                line_detail['type'] = 'ItemBased'
            else:
                line_detail['category'] = 'Uncategorized'
                line_detail['type'] = 'Unknown'

            txn_data['line_items'].append(line_detail)

        # Categorize transaction status
        has_uncategorized_lines = any(
            item['category'] == 'Uncategorized' for item in txn_data['line_items']
        )

        if has_uncategorized_lines:
            uncategorized.append(txn_data)
        elif not entity_name:
            needs_review.append(txn_data)
        else:
            categorized.append(txn_data)

    return {
        'uncategorized': uncategorized,
        'needs_review': needs_review,
        'categorized': categorized
    }


def analyze_deposits(deposits):
    """Analyze deposit transactions"""
    uncategorized = []
    needs_review = []
    categorized = []

    for deposit in deposits:
        # Get account info
        account_ref = getattr(deposit, 'DepositToAccountRef', None)
        account_name = account_ref.name if account_ref else 'Unknown'

        # Get line items
        line_items = getattr(deposit, 'Line', [])

        txn_data = {
            'id': deposit.Id,
            'date': str(deposit.TxnDate),
            'amount': float(deposit.TotalAmt) if deposit.TotalAmt else 0.0,
            'account': account_name,
            'doc_number': getattr(deposit, 'DocNumber', None),
            'private_note': getattr(deposit, 'PrivateNote', None),
            'line_count': len(line_items),
            'line_items': []
        }

        # Analyze line items
        for line in line_items:
            line_detail = {
                'amount': float(getattr(line, 'Amount', 0)),
                'description': getattr(line, 'Description', None),
            }

            # Check for deposit line detail
            if hasattr(line, 'DepositLineDetail'):
                detail = line.DepositLineDetail
                account = getattr(detail, 'AccountRef', None)
                entity = getattr(detail, 'Entity', None)

                line_detail['category'] = account.name if account else 'Uncategorized'
                line_detail['entity'] = entity.name if entity else None
                line_detail['type'] = 'Deposit'
            else:
                line_detail['category'] = 'Uncategorized'
                line_detail['type'] = 'Unknown'

            txn_data['line_items'].append(line_detail)

        # Categorize transaction status
        has_uncategorized_lines = any(
            item['category'] == 'Uncategorized' for item in txn_data['line_items']
        )

        if has_uncategorized_lines:
            uncategorized.append(txn_data)
        elif len(line_items) == 0:
            needs_review.append(txn_data)
        else:
            categorized.append(txn_data)

    return {
        'uncategorized': uncategorized,
        'needs_review': needs_review,
        'categorized': categorized
    }


def generate_posting_suggestions(purchase_analysis, deposit_analysis):
    """Generate suggestions for posting bank transactions"""
    suggestions = []

    total_uncategorized = len(purchase_analysis['uncategorized']) + len(deposit_analysis['uncategorized'])
    total_needs_review = len(purchase_analysis['needs_review']) + len(deposit_analysis['needs_review'])

    # Uncategorized transactions
    if total_uncategorized > 0:
        uncategorized_amount = (
            sum(t['amount'] for t in purchase_analysis['uncategorized']) +
            sum(t['amount'] for t in deposit_analysis['uncategorized'])
        )

        suggestions.append({
            'category': 'Uncategorized Transactions',
            'count': total_uncategorized,
            'total_amount': uncategorized_amount,
            'action': 'Categorize and Post',
            'steps': [
                '1. Go to Banking → Transactions in QuickBooks',
                '2. Review each uncategorized transaction',
                '3. Select appropriate category/account',
                '4. Add vendor/customer if needed',
                '5. Click "Categorize" or "Match" to existing transaction',
                '6. Review and confirm posting',
            ],
            'priority': 'High',
        })

    # Transactions needing review
    if total_needs_review > 0:
        review_amount = (
            sum(t['amount'] for t in purchase_analysis['needs_review']) +
            sum(t['amount'] for t in deposit_analysis['needs_review'])
        )

        suggestions.append({
            'category': 'Transactions Needing Review',
            'count': total_needs_review,
            'total_amount': review_amount,
            'action': 'Review and Complete',
            'steps': [
                '1. Review transactions missing vendor/customer info',
                '2. Add vendor/customer details',
                '3. Verify categorization is correct',
                '4. Add memo/notes for clarity',
                '5. Confirm posting',
            ],
            'priority': 'Medium',
        })

    return suggestions


@handle_exception
def main():
    try:
        print("QuickBooks Bank Transaction Review\n")
        print("="*60)

        client = get_client()
        print(f"Connected to QuickBooks (Realm ID: {client.realm_id})\n")

        # Fetch transactions
        purchases, deposits = get_bank_transactions(client)

        print(f"Found {len(purchases)} purchase transactions")
        print(f"Found {len(deposits)} deposit transactions\n")

        # Analyze transactions
        print("Analyzing purchases...")
        purchase_analysis = analyze_purchases(purchases)

        print("Analyzing deposits...")
        deposit_analysis = analyze_deposits(deposits)

        # Combine results
        results = {
            'purchases': purchase_analysis,
            'deposits': deposit_analysis,
            'summary': {
                'total_purchases': len(purchases),
                'total_deposits': len(deposits),
                'uncategorized_purchases': len(purchase_analysis['uncategorized']),
                'uncategorized_deposits': len(deposit_analysis['uncategorized']),
                'needs_review_purchases': len(purchase_analysis['needs_review']),
                'needs_review_deposits': len(deposit_analysis['needs_review']),
                'categorized_purchases': len(purchase_analysis['categorized']),
                'categorized_deposits': len(deposit_analysis['categorized']),
            }
        }

        # Save raw data
        output_file = '.tmp/qbo_data/bank_transactions.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        print(f"\n✓ Raw data saved to {output_file}\n")

        # Generate suggestions
        suggestions = generate_posting_suggestions(purchase_analysis, deposit_analysis)

        # Save suggestions
        suggestions_file = '.tmp/qbo_data/bank_posting_suggestions.json'
        with open(suggestions_file, 'w') as f:
            json.dump(suggestions, f, indent=2)

        # Print summary
        print("="*60)
        print("BANK TRANSACTION SUMMARY")
        print("="*60)

        print(f"\nPURCHASES (Expenses/Checks/Credit Card):")
        print(f"  Total: {len(purchases)}")
        print(f"  ✓ Categorized: {len(purchase_analysis['categorized'])}")
        print(f"  ⚠ Uncategorized: {len(purchase_analysis['uncategorized'])}")
        print(f"  ⚠ Needs Review: {len(purchase_analysis['needs_review'])}")

        if purchase_analysis['uncategorized']:
            total = sum(t['amount'] for t in purchase_analysis['uncategorized'])
            print(f"     Total Amount: ${total:,.2f}")
            print(f"     Recent uncategorized:")
            for txn in sorted(purchase_analysis['uncategorized'],
                            key=lambda x: x['date'], reverse=True)[:5]:
                entity = txn['entity'] or 'No vendor'
                print(f"       - {txn['date']}: ${txn['amount']:,.2f} ({entity})")

        print(f"\nDEPOSITS:")
        print(f"  Total: {len(deposits)}")
        print(f"  ✓ Categorized: {len(deposit_analysis['categorized'])}")
        print(f"  ⚠ Uncategorized: {len(deposit_analysis['uncategorized'])}")
        print(f"  ⚠ Needs Review: {len(deposit_analysis['needs_review'])}")

        if deposit_analysis['uncategorized']:
            total = sum(t['amount'] for t in deposit_analysis['uncategorized'])
            print(f"     Total Amount: ${total:,.2f}")
            print(f"     Recent uncategorized:")
            for txn in sorted(deposit_analysis['uncategorized'],
                            key=lambda x: x['date'], reverse=True)[:5]:
                print(f"       - {txn['date']}: ${txn['amount']:,.2f}")

        # Print suggestions
        print("\n" + "="*60)
        print("POSTING SUGGESTIONS")
        print("="*60)

        if not suggestions:
            print("\n✓ All caught up! All bank transactions are categorized.")
        else:
            for i, suggestion in enumerate(suggestions, 1):
                print(f"\n{i}. {suggestion['category']}")
                print(f"   Priority: {suggestion['priority']}")
                print(f"   Count: {suggestion['count']}")
                print(f"   Total Amount: ${suggestion['total_amount']:,.2f}")
                print(f"   Action: {suggestion['action']}")
                print(f"   Steps:")
                for step in suggestion['steps']:
                    print(f"      {step}")

        print(f"\n✓ Suggestions saved to {suggestions_file}")
        print("="*60)

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
