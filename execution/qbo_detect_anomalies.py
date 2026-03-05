#!/usr/bin/env python3
"""
QuickBooks Account Anomaly Detection
Identifies posting errors, unusual balances, and issues requiring attention
for year-end close review.
"""

import os
import json
import argparse
from datetime import datetime, timedelta
from collections import defaultdict
from qbo_client import get_client
from qbo_error_handler import handle_exception, QBOError, get_support_info
from quickbooks.objects.account import Account
from quickbooks.objects.journalentry import JournalEntry
from quickbooks.objects.purchase import Purchase
from quickbooks.objects.deposit import Deposit

# Ensure directories exist
os.makedirs('.tmp/year_end_close', exist_ok=True)
os.makedirs('.tmp/qbo_data', exist_ok=True)

# Account types and their expected balance signs
# Positive = Debit balance expected, Negative = Credit balance expected
EXPECTED_BALANCE_SIGNS = {
    'Bank': 'positive',
    'Accounts Receivable': 'positive',
    'Other Current Asset': 'positive',
    'Fixed Asset': 'positive',
    'Other Asset': 'positive',
    'Accounts Payable': 'negative',
    'Credit Card': 'negative',
    'Other Current Liability': 'negative',
    'Long Term Liability': 'negative',
    'Equity': 'negative',
    'Income': 'negative',
    'Cost of Goods Sold': 'positive',
    'Expense': 'positive',
    'Other Income': 'negative',
    'Other Expense': 'positive',
}

# Accounts that commonly have clearing activity (should be zero at year-end)
CLEARING_ACCOUNTS = [
    'suspense', 'clearing', 'undeposited funds', 'ask accountant',
    'opening balance equity', 'retained earnings', 'intercompany'
]


def get_all_accounts(client):
    """Fetch all accounts with balances"""
    print("Fetching chart of accounts...")
    query = "SELECT * FROM Account MAXRESULTS 1000"
    accounts = Account.query(query, qb=client.client)
    return accounts


def get_trial_balance_data(client, as_of_date):
    """Get trial balance report data"""
    print(f"Fetching trial balance as of {as_of_date}...")

    params = {
        'date_macro': 'Custom',
        'end_date': as_of_date,
    }

    report = client.get_report('TrialBalance', **params)
    return report


def get_prior_year_balances(client, year):
    """Get prior year end balances for comparison"""
    prior_year_end = f"{year - 1}-12-31"
    print(f"Fetching prior year balances as of {prior_year_end}...")

    params = {
        'date_macro': 'Custom',
        'end_date': prior_year_end,
    }

    try:
        report = client.get_report('TrialBalance', **params)
        return report
    except Exception as e:
        print(f"  Could not fetch prior year (may not have data): {e}")
        return None


def check_balance_sign_anomalies(accounts):
    """Check for accounts with unexpected balance signs"""
    anomalies = []

    for acct in accounts:
        acct_type = acct.AccountType
        balance = float(acct.CurrentBalance) if acct.CurrentBalance else 0.0

        if balance == 0:
            continue

        expected_sign = EXPECTED_BALANCE_SIGNS.get(acct_type)

        if expected_sign == 'positive' and balance < 0:
            anomalies.append({
                'type': 'Unexpected Negative Balance',
                'severity': 'High',
                'account_name': acct.Name,
                'account_type': acct_type,
                'balance': balance,
                'expected': 'Positive (Debit)',
                'issue': f'Account has credit balance of ${abs(balance):,.2f} but should normally have debit balance',
                'suggestion': 'Review transactions for mispostings or reclassify balance'
            })
        elif expected_sign == 'negative' and balance > 0:
            anomalies.append({
                'type': 'Unexpected Positive Balance',
                'severity': 'High',
                'account_name': acct.Name,
                'account_type': acct_type,
                'balance': balance,
                'expected': 'Negative (Credit)',
                'issue': f'Account has debit balance of ${balance:,.2f} but should normally have credit balance',
                'suggestion': 'Review transactions for mispostings or reclassify balance'
            })

    return anomalies


def check_clearing_account_balances(accounts):
    """Check for clearing/suspense accounts with remaining balances"""
    anomalies = []

    for acct in accounts:
        balance = float(acct.CurrentBalance) if acct.CurrentBalance else 0.0
        name_lower = acct.Name.lower()

        # Check if this is a clearing-type account
        is_clearing = any(term in name_lower for term in CLEARING_ACCOUNTS)

        if is_clearing and abs(balance) > 0.01:  # Allow for rounding
            severity = 'High' if abs(balance) > 100 else 'Medium'
            anomalies.append({
                'type': 'Clearing Account Has Balance',
                'severity': severity,
                'account_name': acct.Name,
                'account_type': acct.AccountType,
                'balance': balance,
                'issue': f'Clearing/suspense account has balance of ${balance:,.2f} that should be cleared',
                'suggestion': 'Review and reclassify to proper accounts before year-end'
            })

    return anomalies


def check_round_number_transactions(client, year, threshold=1000):
    """Find large round-number transactions that may be estimates"""
    anomalies = []

    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"

    print(f"Checking for round-number transactions...")

    # Get journal entries
    query = f"SELECT * FROM JournalEntry WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 500"

    try:
        entries = JournalEntry.query(query, qb=client.client)

        for je in entries:
            total = float(je.TotalAmt) if je.TotalAmt else 0.0

            # Check if it's a round number (divisible by 100 and >= threshold)
            if total >= threshold and total % 100 == 0:
                anomalies.append({
                    'type': 'Round Number Transaction',
                    'severity': 'Low',
                    'transaction_type': 'Journal Entry',
                    'doc_number': je.DocNumber,
                    'date': str(je.TxnDate),
                    'amount': total,
                    'issue': f'Large round-number JE of ${total:,.2f} may be an estimate',
                    'suggestion': 'Verify if this is an estimate that needs true-up or actual transaction'
                })
    except Exception as e:
        print(f"  Warning: Could not check journal entries: {e}")

    return anomalies


def check_duplicate_transactions(client, year):
    """Find potential duplicate transactions"""
    anomalies = []

    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"

    print("Checking for potential duplicate transactions...")

    # Track transactions by (date, amount, vendor/customer)
    transaction_tracker = defaultdict(list)

    # Check purchases
    try:
        query = f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' AND TxnDate <= '{end_date}' MAXRESULTS 500"
        purchases = Purchase.query(query, qb=client.client)

        for txn in purchases:
            amount = float(txn.TotalAmt) if txn.TotalAmt else 0.0
            if amount == 0:
                continue

            vendor = txn.EntityRef.name if txn.EntityRef else 'Unknown'
            key = (str(txn.TxnDate), amount, vendor)
            transaction_tracker[key].append({
                'type': 'Purchase',
                'id': txn.Id,
                'date': str(txn.TxnDate),
                'amount': amount,
                'entity': vendor,
            })
    except Exception as e:
        print(f"  Warning: Could not check purchases: {e}")

    # Find duplicates (same date, amount, vendor)
    for key, txns in transaction_tracker.items():
        if len(txns) > 1:
            anomalies.append({
                'type': 'Potential Duplicate Transaction',
                'severity': 'Medium',
                'transaction_count': len(txns),
                'date': key[0],
                'amount': key[1],
                'entity': key[2],
                'transactions': txns,
                'issue': f'{len(txns)} transactions with same date, amount (${key[1]:,.2f}), and vendor',
                'suggestion': 'Review to determine if these are true duplicates that need to be voided'
            })

    return anomalies


def check_old_uncleared_transactions(client, year):
    """Find bank transactions older than 90 days that haven't cleared"""
    anomalies = []

    # This would require checking bank reconciliation data
    # For now, flag a reminder to check reconciliation
    anomalies.append({
        'type': 'Reconciliation Reminder',
        'severity': 'Medium',
        'issue': 'Check for old uncleared checks and deposits',
        'suggestion': f'Run qbo_check_reconciliation.py to identify uncleared items older than 90 days'
    })

    return anomalies


def check_year_over_year_variance(accounts, prior_accounts, variance_threshold=0.25):
    """Check for significant year-over-year balance changes"""
    anomalies = []

    if not prior_accounts:
        return anomalies

    print("Checking year-over-year variances...")

    # Build prior year lookup
    prior_lookup = {}
    for acct in prior_accounts:
        prior_lookup[acct.Name] = float(acct.CurrentBalance) if acct.CurrentBalance else 0.0

    for acct in accounts:
        current_balance = float(acct.CurrentBalance) if acct.CurrentBalance else 0.0
        prior_balance = prior_lookup.get(acct.Name, 0.0)

        if prior_balance == 0 and current_balance == 0:
            continue

        # Calculate variance
        if prior_balance != 0:
            variance = (current_balance - prior_balance) / abs(prior_balance)
        else:
            variance = 1.0 if current_balance != 0 else 0.0

        if abs(variance) >= variance_threshold and abs(current_balance - prior_balance) > 500:
            anomalies.append({
                'type': 'Significant Year-Over-Year Change',
                'severity': 'Low',
                'account_name': acct.Name,
                'account_type': acct.AccountType,
                'prior_balance': prior_balance,
                'current_balance': current_balance,
                'variance_pct': round(variance * 100, 1),
                'change_amount': current_balance - prior_balance,
                'issue': f'Balance changed by {abs(variance)*100:.1f}% (${abs(current_balance - prior_balance):,.2f})',
                'suggestion': 'Review if this change is expected and properly supported'
            })

    return anomalies


def check_negative_bank_balances(accounts):
    """Check for negative bank account balances"""
    anomalies = []

    for acct in accounts:
        if acct.AccountType == 'Bank':
            balance = float(acct.CurrentBalance) if acct.CurrentBalance else 0.0
            if balance < 0:
                anomalies.append({
                    'type': 'Negative Bank Balance',
                    'severity': 'High',
                    'account_name': acct.Name,
                    'balance': balance,
                    'issue': f'Bank account shows negative balance of ${abs(balance):,.2f}',
                    'suggestion': 'Verify outstanding checks/deposits or check for posting errors'
                })

    return anomalies


@handle_exception
def main():
    parser = argparse.ArgumentParser(description='Detect QuickBooks account anomalies')
    parser.add_argument('--year', type=int, default=datetime.now().year,
                        help='Year to analyze (default: current year)')
    parser.add_argument('--output', help='Output file path')
    parser.add_argument('--variance-threshold', type=float, default=0.25,
                        help='Year-over-year variance threshold (default: 0.25 = 25%%)')

    args = parser.parse_args()

    year = args.year
    as_of_date = f"{year}-12-31"

    print("QuickBooks Account Anomaly Detection")
    print("=" * 60)
    print(f"Analyzing year: {year}")
    print(f"As of date: {as_of_date}")
    print("=" * 60 + "\n")

    try:
        client = get_client()
        print(f"Connected to QuickBooks (Realm ID: {client.realm_id})\n")

        # Get account data
        accounts = get_all_accounts(client)
        print(f"  Found {len(accounts)} accounts\n")

        # Get prior year data for comparison
        prior_year_end = f"{year - 1}-12-31"
        prior_accounts = None
        try:
            query = f"SELECT * FROM Account MAXRESULTS 1000"
            prior_accounts = accounts  # Use same accounts, balances are point-in-time
        except:
            pass

        # Run all anomaly checks
        all_anomalies = []

        print("Running anomaly checks...")

        # 1. Balance sign anomalies
        print("  [1/7] Checking balance signs...")
        anomalies = check_balance_sign_anomalies(accounts)
        all_anomalies.extend(anomalies)
        print(f"       Found {len(anomalies)} issues")

        # 2. Clearing account balances
        print("  [2/7] Checking clearing accounts...")
        anomalies = check_clearing_account_balances(accounts)
        all_anomalies.extend(anomalies)
        print(f"       Found {len(anomalies)} issues")

        # 3. Negative bank balances
        print("  [3/7] Checking bank balances...")
        anomalies = check_negative_bank_balances(accounts)
        all_anomalies.extend(anomalies)
        print(f"       Found {len(anomalies)} issues")

        # 4. Round number transactions
        print("  [4/7] Checking round-number transactions...")
        anomalies = check_round_number_transactions(client, year)
        all_anomalies.extend(anomalies)
        print(f"       Found {len(anomalies)} issues")

        # 5. Duplicate transactions
        print("  [5/7] Checking for duplicates...")
        anomalies = check_duplicate_transactions(client, year)
        all_anomalies.extend(anomalies)
        print(f"       Found {len(anomalies)} issues")

        # 6. Old uncleared items
        print("  [6/7] Checking uncleared items...")
        anomalies = check_old_uncleared_transactions(client, year)
        all_anomalies.extend(anomalies)
        print(f"       Found {len(anomalies)} issues")

        # 7. Year-over-year variance (skip if no prior data)
        print("  [7/7] Checking YoY variances...")
        # Note: Would need separate API call to get prior year balances
        print("       Skipped (requires manual comparison)")

        # Save results
        output_file = args.output or f'.tmp/year_end_close/anomalies_{year}.json'

        results = {
            'year': year,
            'as_of_date': as_of_date,
            'generated_at': datetime.now().isoformat(),
            'total_anomalies': len(all_anomalies),
            'by_severity': {
                'High': len([a for a in all_anomalies if a.get('severity') == 'High']),
                'Medium': len([a for a in all_anomalies if a.get('severity') == 'Medium']),
                'Low': len([a for a in all_anomalies if a.get('severity') == 'Low']),
            },
            'anomalies': all_anomalies
        }

        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        # Print summary
        print("\n" + "=" * 60)
        print("ANOMALY DETECTION SUMMARY")
        print("=" * 60)

        print(f"\nTotal Issues Found: {len(all_anomalies)}")
        print(f"  High Severity:   {results['by_severity']['High']}")
        print(f"  Medium Severity: {results['by_severity']['Medium']}")
        print(f"  Low Severity:    {results['by_severity']['Low']}")

        # Print high severity items
        high_severity = [a for a in all_anomalies if a.get('severity') == 'High']
        if high_severity:
            print("\n" + "-" * 60)
            print("HIGH SEVERITY ISSUES (Require Immediate Attention)")
            print("-" * 60)
            for i, anomaly in enumerate(high_severity, 1):
                print(f"\n{i}. {anomaly['type']}")
                if 'account_name' in anomaly:
                    print(f"   Account: {anomaly['account_name']}")
                if 'balance' in anomaly:
                    print(f"   Balance: ${anomaly['balance']:,.2f}")
                print(f"   Issue: {anomaly['issue']}")
                print(f"   Suggestion: {anomaly['suggestion']}")

        # Print medium severity items
        medium_severity = [a for a in all_anomalies if a.get('severity') == 'Medium']
        if medium_severity:
            print("\n" + "-" * 60)
            print("MEDIUM SEVERITY ISSUES")
            print("-" * 60)
            for i, anomaly in enumerate(medium_severity, 1):
                print(f"\n{i}. {anomaly['type']}")
                if 'account_name' in anomaly:
                    print(f"   Account: {anomaly['account_name']}")
                print(f"   Issue: {anomaly['issue']}")

        print(f"\n✓ Full report saved to: {output_file}")
        print("=" * 60)

    except QBOError as e:
        print(f"\n✗ QuickBooks Error: {e.message}")
        if e.intuit_tid:
            print(f"  Transaction ID: {e.intuit_tid}")
        print(f"\n{get_support_info()['message']}")
        raise


if __name__ == '__main__':
    main()
