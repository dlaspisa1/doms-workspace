#!/usr/bin/env python3
"""
QuickBooks Bank Reconciliation Status Check
Reviews bank and credit card accounts for reconciliation status
and identifies uncleared items at year-end.
"""

import os
import json
import argparse
from datetime import datetime, timedelta
from qbo_client import get_client
from qbo_error_handler import handle_exception, QBOError, get_support_info
from quickbooks.objects.account import Account
from quickbooks.objects.purchase import Purchase
from quickbooks.objects.deposit import Deposit
from quickbooks.objects.transfer import Transfer

# Ensure directories exist
os.makedirs('.tmp/year_end_close', exist_ok=True)


def get_bank_and_cc_accounts(client):
    """Fetch all bank and credit card accounts"""
    print("Fetching bank and credit card accounts...")

    query = "SELECT * FROM Account WHERE AccountType IN ('Bank', 'Credit Card') MAXRESULTS 100"
    accounts = Account.query(query, qb=client.client)

    return accounts


def get_uncleared_checks(client, account_id, cutoff_date):
    """Get uncleared checks/payments for an account"""
    uncleared = []

    # Query purchases (checks, expenses, etc.)
    try:
        query = f"SELECT * FROM Purchase WHERE AccountRef = '{account_id}' MAXRESULTS 500"
        purchases = Purchase.query(query, qb=client.client)

        for txn in purchases:
            # Check if transaction is before cutoff and may be uncleared
            txn_date = txn.TxnDate
            if isinstance(txn_date, str):
                txn_date = datetime.strptime(txn_date[:10], '%Y-%m-%d')

            if txn_date <= cutoff_date:
                amount = float(txn.TotalAmt) if txn.TotalAmt else 0.0

                uncleared.append({
                    'type': 'Purchase/Check',
                    'id': txn.Id,
                    'date': str(txn.TxnDate),
                    'amount': amount,
                    'payee': txn.EntityRef.name if txn.EntityRef else 'Unknown',
                    'payment_type': getattr(txn, 'PaymentType', 'Unknown'),
                    'days_old': (cutoff_date - txn_date).days if isinstance(txn_date, datetime) else 0,
                })

    except Exception as e:
        print(f"    Warning: Could not fetch purchases: {e}")

    return uncleared


def get_uncleared_deposits(client, account_id, cutoff_date):
    """Get uncleared deposits for an account"""
    uncleared = []

    try:
        query = f"SELECT * FROM Deposit WHERE DepositToAccountRef = '{account_id}' MAXRESULTS 500"
        deposits = Deposit.query(query, qb=client.client)

        for txn in deposits:
            txn_date = txn.TxnDate
            if isinstance(txn_date, str):
                txn_date = datetime.strptime(txn_date[:10], '%Y-%m-%d')

            if txn_date <= cutoff_date:
                amount = float(txn.TotalAmt) if txn.TotalAmt else 0.0

                uncleared.append({
                    'type': 'Deposit',
                    'id': txn.Id,
                    'date': str(txn.TxnDate),
                    'amount': amount,
                    'days_old': (cutoff_date - txn_date).days if isinstance(txn_date, datetime) else 0,
                })

    except Exception as e:
        print(f"    Warning: Could not fetch deposits: {e}")

    return uncleared


def analyze_account_reconciliation(client, account, year):
    """Analyze reconciliation status for a single account"""
    cutoff_date = datetime(year, 12, 31)
    ninety_days_ago = cutoff_date - timedelta(days=90)

    result = {
        'account_name': account.Name,
        'account_type': account.AccountType,
        'account_id': account.Id,
        'book_balance': float(account.CurrentBalance) if account.CurrentBalance else 0.0,
        'reconciliation_status': 'Unknown',  # QBO API doesn't expose this directly
        'analysis_date': cutoff_date.strftime('%Y-%m-%d'),
        'uncleared_items': [],
        'old_uncleared_items': [],  # > 90 days
        'total_uncleared': 0.0,
        'warnings': [],
    }

    # Get transactions for this account
    print(f"  Analyzing {account.Name}...")

    # Note: QuickBooks Online API doesn't directly expose reconciliation status
    # We can identify potentially uncleared items by looking at recent transactions

    # For bank accounts, check for old outstanding checks
    if account.AccountType == 'Bank':
        result['warnings'].append(
            'Note: QBO API does not expose reconciliation status directly. '
            'Please verify reconciliation in QuickBooks Online UI.'
        )

        # Get recent purchases/checks
        uncleared = get_uncleared_checks(client, account.Id, cutoff_date)

        # Filter to items > 90 days old (likely uncleared)
        old_items = [item for item in uncleared if item['days_old'] > 90]

        if old_items:
            result['old_uncleared_items'] = old_items
            result['warnings'].append(
                f'{len(old_items)} transactions are over 90 days old and may be uncleared'
            )

    # For credit cards, check for old transactions
    elif account.AccountType == 'Credit Card':
        result['warnings'].append(
            'Credit card accounts should be reconciled to monthly statements.'
        )

    return result


def generate_reconciliation_checklist(accounts_analysis, year):
    """Generate reconciliation checklist"""
    checklist = []

    for analysis in accounts_analysis:
        item = {
            'account': analysis['account_name'],
            'type': analysis['account_type'],
            'book_balance': analysis['book_balance'],
            'status': 'Needs Review',
            'action_items': [],
        }

        # Add action items based on warnings
        if analysis['old_uncleared_items']:
            item['action_items'].append(
                f"Review {len(analysis['old_uncleared_items'])} items over 90 days old"
            )
            item['status'] = 'Action Required'

        if analysis['account_type'] == 'Bank':
            item['action_items'].append(
                f"Reconcile to December {year} bank statement"
            )

        if analysis['account_type'] == 'Credit Card':
            item['action_items'].append(
                f"Reconcile to December {year} credit card statement"
            )

        checklist.append(item)

    return checklist


@handle_exception
def main():
    parser = argparse.ArgumentParser(description='Check bank reconciliation status')
    parser.add_argument('--date', help='As-of date (YYYY-MM-DD), default: year-end of current year')
    parser.add_argument('--year', type=int, help='Year to check (overridden by --date)')
    parser.add_argument('--output', help='Output file path')

    args = parser.parse_args()

    # Determine date
    if args.date:
        as_of_date = datetime.strptime(args.date, '%Y-%m-%d')
        year = as_of_date.year
    elif args.year:
        year = args.year
        as_of_date = datetime(year, 12, 31)
    else:
        year = datetime.now().year
        as_of_date = datetime(year, 12, 31)

    print("QuickBooks Bank Reconciliation Check")
    print("=" * 60)
    print(f"As of date: {as_of_date.strftime('%Y-%m-%d')}")
    print("=" * 60 + "\n")

    try:
        client = get_client()
        print(f"Connected to QuickBooks (Realm ID: {client.realm_id})\n")

        # Get bank and credit card accounts
        accounts = get_bank_and_cc_accounts(client)
        print(f"Found {len(accounts)} bank/credit card accounts\n")

        # Analyze each account
        accounts_analysis = []
        for account in accounts:
            analysis = analyze_account_reconciliation(client, account, year)
            accounts_analysis.append(analysis)

        # Generate checklist
        checklist = generate_reconciliation_checklist(accounts_analysis, year)

        # Save results
        output_file = args.output or f'.tmp/year_end_close/reconciliation_status_{year}.json'

        results = {
            'as_of_date': as_of_date.strftime('%Y-%m-%d'),
            'year': year,
            'generated_at': datetime.now().isoformat(),
            'accounts_analyzed': len(accounts_analysis),
            'accounts_needing_action': len([a for a in accounts_analysis if a['old_uncleared_items']]),
            'accounts': accounts_analysis,
            'checklist': checklist,
        }

        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        # Print summary
        print("\n" + "=" * 60)
        print("BANK RECONCILIATION STATUS")
        print("=" * 60)

        print(f"\nAccounts Analyzed: {len(accounts_analysis)}")
        print(f"Accounts Needing Action: {results['accounts_needing_action']}")

        # Print each account
        print("\n" + "-" * 60)
        print("ACCOUNT SUMMARY")
        print("-" * 60)

        for analysis in accounts_analysis:
            print(f"\n{analysis['account_name']} ({analysis['account_type']})")
            print(f"  Book Balance: ${analysis['book_balance']:,.2f}")

            if analysis['old_uncleared_items']:
                print(f"  ⚠ Old Items (>90 days): {len(analysis['old_uncleared_items'])}")
                total_old = sum(item['amount'] for item in analysis['old_uncleared_items'])
                print(f"    Total: ${total_old:,.2f}")

                # Show oldest items
                sorted_old = sorted(analysis['old_uncleared_items'],
                                   key=lambda x: x['days_old'], reverse=True)[:3]
                for item in sorted_old:
                    print(f"    - {item['date']}: ${item['amount']:,.2f} "
                          f"({item['days_old']} days old) - {item.get('payee', 'N/A')}")

            for warning in analysis['warnings'][:2]:  # Limit warnings shown
                print(f"  Note: {warning}")

        # Print checklist
        print("\n" + "-" * 60)
        print("RECONCILIATION CHECKLIST")
        print("-" * 60)

        for item in checklist:
            status_icon = "⚠" if item['status'] == 'Action Required' else "○"
            print(f"\n{status_icon} {item['account']}")
            print(f"   Balance: ${item['book_balance']:,.2f}")
            for action in item['action_items']:
                print(f"   [ ] {action}")

        print(f"\n✓ Full report saved to: {output_file}")

        # Print instructions
        print("\n" + "=" * 60)
        print("NEXT STEPS")
        print("=" * 60)
        print("""
1. Log into QuickBooks Online
2. Go to Accounting > Reconcile
3. For each bank/CC account:
   a. Select the account and statement date
   b. Enter the statement ending balance
   c. Check off cleared transactions
   d. Investigate any differences
4. For old uncleared items:
   a. Verify check was cashed (contact bank)
   b. Void stale checks (typically >6 months)
   c. Verify deposits were received
5. Document any reconciling items
""")

    except QBOError as e:
        print(f"\n✗ QuickBooks Error: {e.message}")
        if e.intuit_tid:
            print(f"  Transaction ID: {e.intuit_tid}")
        print(f"\n{get_support_info()['message']}")
        raise


if __name__ == '__main__':
    main()
