#!/usr/bin/env python3
"""
QuickBooks Journal Entry Recommendation Engine
Analyzes accounts and transactions to recommend adjusting entries
for year-end close.
"""

import os
import json
import argparse
from datetime import datetime, timedelta
from qbo_client import get_client
from qbo_error_handler import handle_exception, QBOError, get_support_info
from quickbooks.objects.account import Account
from quickbooks.objects.bill import Bill
from quickbooks.objects.invoice import Invoice

# Ensure directories exist
os.makedirs('.tmp/year_end_close', exist_ok=True)

# Standard adjusting entry categories
ADJUSTMENT_CATEGORIES = [
    'Accrued Expenses',
    'Accrued Revenue',
    'Prepaid Expenses',
    'Depreciation',
    'Bad Debt',
    'Inventory Adjustment',
    'Payroll Accrual',
    'Interest Accrual',
    'Deferred Revenue',
    'Reclassification',
]


def get_all_accounts(client):
    """Fetch all accounts"""
    query = "SELECT * FROM Account MAXRESULTS 1000"
    accounts = Account.query(query, qb=client.client)
    return {acct.Name: acct for acct in accounts}


def check_prepaid_accounts(accounts, year):
    """Check prepaid expense accounts for amortization needs"""
    recommendations = []

    prepaid_keywords = ['prepaid', 'prepay', 'advance']

    for name, acct in accounts.items():
        if acct.AccountType in ['Other Current Asset']:
            name_lower = name.lower()
            if any(kw in name_lower for kw in prepaid_keywords):
                balance = float(acct.CurrentBalance) if acct.CurrentBalance else 0.0

                if balance > 0:
                    recommendations.append({
                        'category': 'Prepaid Expenses',
                        'priority': 'High',
                        'account': name,
                        'current_balance': balance,
                        'issue': f'Prepaid account has balance of ${balance:,.2f}',
                        'recommended_je': {
                            'description': f'Amortize prepaid expenses for {year}',
                            'debit_account': 'Related expense account (insurance, rent, etc.)',
                            'credit_account': name,
                            'amount': 'Calculate based on prepaid schedule',
                        },
                        'action_needed': 'Review prepaid schedule and calculate amount to expense for the year'
                    })

    return recommendations


def check_depreciation_accounts(accounts, year):
    """Check fixed assets for depreciation entries"""
    recommendations = []

    # Look for fixed assets without corresponding depreciation
    fixed_assets = {}
    accum_depreciation = {}

    for name, acct in accounts.items():
        if acct.AccountType == 'Fixed Asset':
            if 'depreciation' in name.lower() or 'accum' in name.lower():
                accum_depreciation[name] = float(acct.CurrentBalance) if acct.CurrentBalance else 0.0
            else:
                fixed_assets[name] = float(acct.CurrentBalance) if acct.CurrentBalance else 0.0

    # If there are fixed assets, recommend depreciation review
    total_fixed_assets = sum(fixed_assets.values())
    if total_fixed_assets > 0:
        recommendations.append({
            'category': 'Depreciation',
            'priority': 'High',
            'total_fixed_assets': total_fixed_assets,
            'fixed_asset_accounts': list(fixed_assets.keys()),
            'issue': f'Fixed assets totaling ${total_fixed_assets:,.2f} may need depreciation',
            'recommended_je': {
                'description': f'Record {year} depreciation expense',
                'debit_account': 'Depreciation Expense',
                'credit_account': 'Accumulated Depreciation',
                'amount': 'Calculate based on depreciation schedule',
            },
            'action_needed': 'Review depreciation schedule and record annual depreciation'
        })

    return recommendations


def check_accrued_expenses(client, year):
    """Check for expenses that need to be accrued"""
    recommendations = []
    end_date = f"{year}-12-31"

    # Look for recurring expenses that may not have December bills
    # This is a heuristic - actual accruals require business knowledge

    recommendations.append({
        'category': 'Accrued Expenses',
        'priority': 'Medium',
        'issue': 'Review for expenses incurred but not yet billed',
        'common_accruals': [
            'Utilities (electric, gas, water)',
            'Professional services (legal, accounting)',
            'Interest on loans',
            'Property taxes',
            'Commissions',
            'Bonuses',
        ],
        'recommended_je': {
            'description': f'Accrue expenses incurred but not billed as of {end_date}',
            'debit_account': 'Appropriate expense account',
            'credit_account': 'Accrued Expenses (liability)',
            'amount': 'Estimate based on prior periods and known obligations',
        },
        'action_needed': 'Review each expense category and estimate unbilled amounts'
    })

    return recommendations


def check_payroll_accrual(year):
    """Check for payroll accrual needs"""
    recommendations = []
    end_date = datetime(year, 12, 31)

    # Determine if year ends mid-pay period
    day_of_week = end_date.weekday()  # 0=Monday, 6=Sunday

    if day_of_week not in [4, 5, 6]:  # Not Friday, Saturday, or Sunday
        recommendations.append({
            'category': 'Payroll Accrual',
            'priority': 'High',
            'issue': f'December 31, {year} is a {end_date.strftime("%A")} - likely mid-pay period',
            'recommended_je': {
                'description': f'Accrue wages earned but not paid through {end_date.strftime("%Y-%m-%d")}',
                'debit_account': 'Wages Expense / Salaries Expense',
                'credit_account': 'Accrued Wages Payable',
                'amount': 'Calculate based on daily wage rate x days worked',
            },
            'calculation_hint': 'Count workdays from last pay period end through 12/31',
            'action_needed': 'Calculate wages earned but unpaid at year-end'
        })

    return recommendations


def check_bad_debt(client, year):
    """Check accounts receivable for bad debt allowance"""
    recommendations = []

    # Get aged receivables
    print("Checking accounts receivable aging...")

    try:
        query = "SELECT * FROM Invoice WHERE Balance > '0' MAXRESULTS 500"
        invoices = Invoice.query(query, qb=client.client)

        total_ar = 0
        old_ar = 0  # > 90 days
        cutoff_date = datetime(year, 12, 31) - timedelta(days=90)

        for inv in invoices:
            balance = float(inv.Balance) if inv.Balance else 0.0
            total_ar += balance

            txn_date = inv.TxnDate
            if isinstance(txn_date, str):
                txn_date = datetime.strptime(txn_date[:10], '%Y-%m-%d')

            if txn_date < cutoff_date:
                old_ar += balance

        if total_ar > 0:
            old_pct = (old_ar / total_ar * 100) if total_ar else 0

            recommendations.append({
                'category': 'Bad Debt',
                'priority': 'Medium',
                'total_ar': total_ar,
                'ar_over_90_days': old_ar,
                'pct_over_90_days': round(old_pct, 1),
                'issue': f'${old_ar:,.2f} ({old_pct:.1f}%) of AR is over 90 days old',
                'recommended_je': {
                    'description': f'Adjust allowance for doubtful accounts',
                    'debit_account': 'Bad Debt Expense',
                    'credit_account': 'Allowance for Doubtful Accounts',
                    'amount': 'Calculate based on aging analysis and collection history',
                },
                'action_needed': 'Review aging report and determine appropriate allowance'
            })

    except Exception as e:
        print(f"  Warning: Could not analyze AR aging: {e}")

    return recommendations


def check_deferred_revenue(accounts, year):
    """Check for deferred revenue accounts"""
    recommendations = []

    deferred_keywords = ['deferred', 'unearned', 'prepaid revenue', 'customer deposit']

    for name, acct in accounts.items():
        name_lower = name.lower()
        if any(kw in name_lower for kw in deferred_keywords):
            balance = float(acct.CurrentBalance) if acct.CurrentBalance else 0.0

            if abs(balance) > 0:
                recommendations.append({
                    'category': 'Deferred Revenue',
                    'priority': 'Medium',
                    'account': name,
                    'current_balance': balance,
                    'issue': f'Deferred revenue account has balance of ${abs(balance):,.2f}',
                    'recommended_je': {
                        'description': f'Recognize revenue earned in {year}',
                        'debit_account': name,
                        'credit_account': 'Revenue account',
                        'amount': 'Calculate based on services/products delivered',
                    },
                    'action_needed': 'Review deferred revenue and recognize earned portion'
                })

    return recommendations


def check_intercompany_balances(accounts):
    """Check for intercompany balances that need reconciliation"""
    recommendations = []

    interco_keywords = ['intercompany', 'inter-company', 'due to', 'due from', 'affiliate']

    for name, acct in accounts.items():
        name_lower = name.lower()
        if any(kw in name_lower for kw in interco_keywords):
            balance = float(acct.CurrentBalance) if acct.CurrentBalance else 0.0

            if abs(balance) > 0:
                recommendations.append({
                    'category': 'Reclassification',
                    'priority': 'Medium',
                    'account': name,
                    'current_balance': balance,
                    'issue': f'Intercompany account has balance of ${balance:,.2f}',
                    'recommended_je': {
                        'description': 'Reconcile intercompany balances',
                        'action': 'Verify balance agrees with related company',
                    },
                    'action_needed': 'Reconcile with related entity and clear any differences'
                })

    return recommendations


def check_suspense_clearing(accounts):
    """Check for items in suspense/clearing accounts"""
    recommendations = []

    clearing_keywords = ['suspense', 'clearing', 'ask accountant', 'unclassified']

    for name, acct in accounts.items():
        name_lower = name.lower()
        if any(kw in name_lower for kw in clearing_keywords):
            balance = float(acct.CurrentBalance) if acct.CurrentBalance else 0.0

            if abs(balance) > 0:
                recommendations.append({
                    'category': 'Reclassification',
                    'priority': 'High',
                    'account': name,
                    'current_balance': balance,
                    'issue': f'Suspense/clearing account has balance of ${balance:,.2f}',
                    'recommended_je': {
                        'description': 'Reclassify items from suspense account',
                        'debit_account': 'Proper expense/asset account',
                        'credit_account': name,
                        'amount': balance,
                    },
                    'action_needed': 'Review items and reclassify to proper accounts'
                })

    return recommendations


@handle_exception
def main():
    parser = argparse.ArgumentParser(description='Generate JE recommendations for year-end close')
    parser.add_argument('--year', type=int, default=datetime.now().year,
                        help='Year to analyze (default: current year)')
    parser.add_argument('--output', help='Output file path')

    args = parser.parse_args()
    year = args.year

    print("QuickBooks Journal Entry Recommendation Engine")
    print("=" * 60)
    print(f"Analyzing year: {year}")
    print("=" * 60 + "\n")

    try:
        client = get_client()
        print(f"Connected to QuickBooks (Realm ID: {client.realm_id})\n")

        # Get account data
        print("Fetching accounts...")
        accounts = get_all_accounts(client)
        print(f"  Found {len(accounts)} accounts\n")

        # Run all recommendation checks
        all_recommendations = []

        print("Analyzing for recommended adjustments...")

        # 1. Prepaid expenses
        print("  [1/8] Checking prepaid expenses...")
        recs = check_prepaid_accounts(accounts, year)
        all_recommendations.extend(recs)
        print(f"       Found {len(recs)} recommendations")

        # 2. Depreciation
        print("  [2/8] Checking depreciation...")
        recs = check_depreciation_accounts(accounts, year)
        all_recommendations.extend(recs)
        print(f"       Found {len(recs)} recommendations")

        # 3. Accrued expenses
        print("  [3/8] Checking accrued expenses...")
        recs = check_accrued_expenses(client, year)
        all_recommendations.extend(recs)
        print(f"       Found {len(recs)} recommendations")

        # 4. Payroll accrual
        print("  [4/8] Checking payroll accrual...")
        recs = check_payroll_accrual(year)
        all_recommendations.extend(recs)
        print(f"       Found {len(recs)} recommendations")

        # 5. Bad debt
        print("  [5/8] Checking bad debt allowance...")
        recs = check_bad_debt(client, year)
        all_recommendations.extend(recs)
        print(f"       Found {len(recs)} recommendations")

        # 6. Deferred revenue
        print("  [6/8] Checking deferred revenue...")
        recs = check_deferred_revenue(accounts, year)
        all_recommendations.extend(recs)
        print(f"       Found {len(recs)} recommendations")

        # 7. Intercompany
        print("  [7/8] Checking intercompany balances...")
        recs = check_intercompany_balances(accounts)
        all_recommendations.extend(recs)
        print(f"       Found {len(recs)} recommendations")

        # 8. Suspense/clearing
        print("  [8/8] Checking suspense/clearing accounts...")
        recs = check_suspense_clearing(accounts)
        all_recommendations.extend(recs)
        print(f"       Found {len(recs)} recommendations")

        # Save results
        output_file = args.output or f'.tmp/year_end_close/recommended_jes_{year}.json'

        results = {
            'year': year,
            'generated_at': datetime.now().isoformat(),
            'total_recommendations': len(all_recommendations),
            'by_category': {},
            'by_priority': {
                'High': len([r for r in all_recommendations if r.get('priority') == 'High']),
                'Medium': len([r for r in all_recommendations if r.get('priority') == 'Medium']),
                'Low': len([r for r in all_recommendations if r.get('priority') == 'Low']),
            },
            'recommendations': all_recommendations
        }

        # Count by category
        for rec in all_recommendations:
            cat = rec.get('category', 'Other')
            results['by_category'][cat] = results['by_category'].get(cat, 0) + 1

        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        # Print summary
        print("\n" + "=" * 60)
        print("JOURNAL ENTRY RECOMMENDATIONS SUMMARY")
        print("=" * 60)

        print(f"\nTotal Recommendations: {len(all_recommendations)}")
        print(f"  High Priority:   {results['by_priority']['High']}")
        print(f"  Medium Priority: {results['by_priority']['Medium']}")
        print(f"  Low Priority:    {results['by_priority']['Low']}")

        print("\nBy Category:")
        for cat, count in results['by_category'].items():
            print(f"  {cat}: {count}")

        # Print high priority items
        high_priority = [r for r in all_recommendations if r.get('priority') == 'High']
        if high_priority:
            print("\n" + "-" * 60)
            print("HIGH PRIORITY ADJUSTMENTS")
            print("-" * 60)
            for i, rec in enumerate(high_priority, 1):
                print(f"\n{i}. {rec['category']}")
                if 'account' in rec:
                    print(f"   Account: {rec['account']}")
                if 'current_balance' in rec:
                    print(f"   Balance: ${rec['current_balance']:,.2f}")
                print(f"   Issue: {rec['issue']}")
                if 'recommended_je' in rec:
                    je = rec['recommended_je']
                    print(f"   JE: DR {je.get('debit_account', 'TBD')} / CR {je.get('credit_account', 'TBD')}")
                print(f"   Action: {rec.get('action_needed', 'Review and adjust')}")

        print(f"\n✓ Full report saved to: {output_file}")
        print("=" * 60)

        # Print checklist
        print("\n" + "=" * 60)
        print("YEAR-END ADJUSTING ENTRIES CHECKLIST")
        print("=" * 60)
        print("""
[ ] Accrued Expenses - Expenses incurred but not billed
[ ] Prepaid Expenses - Amortize insurance, rent, etc.
[ ] Depreciation - Record annual depreciation
[ ] Bad Debt - Adjust allowance for doubtful accounts
[ ] Inventory - Book-to-physical adjustments
[ ] Payroll Accrual - Wages earned but not paid
[ ] Interest Accrual - Loan interest through year-end
[ ] Deferred Revenue - Recognize earned revenue
[ ] Reclassifications - Clear suspense/clearing accounts
[ ] Intercompany - Reconcile affiliated balances
""")

    except QBOError as e:
        print(f"\n✗ QuickBooks Error: {e.message}")
        if e.intuit_tid:
            print(f"  Transaction ID: {e.intuit_tid}")
        print(f"\n{get_support_info()['message']}")
        raise


if __name__ == '__main__':
    main()
