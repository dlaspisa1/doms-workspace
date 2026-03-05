#!/usr/bin/env python3
"""
Get financial reports from QuickBooks Online with error handling
Uses direct API calls since python-quickbooks doesn't support reports.
"""

import os
import json
import argparse
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Ensure .tmp directory exists
os.makedirs('.tmp/qbo_data', exist_ok=True)

REPORT_TYPES = {
    'profit_and_loss': 'ProfitAndLoss',
    'balance_sheet': 'BalanceSheet',
    'cash_flow': 'CashFlow',
    'ar_aging': 'AgedReceivables',
    'ap_aging': 'AgedPayables',
    'general_ledger': 'GeneralLedger',
    'trial_balance': 'TrialBalance',
    'profit_and_loss_detail': 'ProfitAndLossDetail',
}

# API base URL
ENVIRONMENT = os.getenv('QBO_ENVIRONMENT', 'sandbox')
if ENVIRONMENT == 'production':
    API_BASE_URL = "https://quickbooks.api.intuit.com"
else:
    API_BASE_URL = "https://sandbox-quickbooks.api.intuit.com"


def get_tokens():
    """Load tokens from file"""
    token_file = os.path.expanduser('~/.qbo_tokens.json')
    if not os.path.exists(token_file):
        raise Exception("No tokens found. Run qbo_auth.py first.")
    with open(token_file, 'r') as f:
        return json.load(f)


def get_report(report_type, start_date=None, end_date=None, accounting_method='Accrual'):
    """
    Get a financial report using direct API call

    Args:
        report_type: Type of report (see REPORT_TYPES)
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        accounting_method: 'Accrual' or 'Cash'

    Returns:
        Report data dictionary
    """
    tokens = get_tokens()
    realm_id = tokens.get('realm_id') or os.getenv('QBO_REALM_ID')
    access_token = tokens['access_token']

    # Map friendly name to QuickBooks report name
    qb_report_type = REPORT_TYPES.get(report_type.lower(), report_type)

    # Build URL
    url = f"{API_BASE_URL}/v3/company/{realm_id}/reports/{qb_report_type}"

    # Build params
    params = {
        'accounting_method': accounting_method,
    }
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
    }

    print(f"Fetching {qb_report_type} report...")
    print(f"  Date range: {start_date or 'N/A'} to {end_date or 'N/A'}")
    print(f"  Method: {accounting_method}\n")

    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        raise Exception(f"API Error {response.status_code}: {response.text}")

    return response.json()


def format_report_to_dict(report):
    """Format report for output - already a dict from API"""
    return report


def main():
    parser = argparse.ArgumentParser(description='Get QuickBooks financial reports')
    parser.add_argument('--report', required=True,
                        choices=list(REPORT_TYPES.keys()),
                        help='Type of report')
    parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    parser.add_argument('--method', choices=['Accrual', 'Cash'], default='Accrual',
                        help='Accounting method')
    parser.add_argument('--output', help='Output file path (default: .tmp/qbo_data/{report_type}.json)')

    args = parser.parse_args()

    # Set default dates if not provided (current fiscal year)
    if not args.start_date:
        # Default to Jan 1st of current year
        args.start_date = datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d')

    if not args.end_date:
        # Default to today
        args.end_date = datetime.now().strftime('%Y-%m-%d')

    # Get report
    report = get_report(
        report_type=args.report,
        start_date=args.start_date,
        end_date=args.end_date,
        accounting_method=args.method
    )

    # Determine output path
    output_path = args.output or f'.tmp/qbo_data/{args.report}.json'

    # Save to file
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    print(f"✓ Report fetched successfully")
    print(f"✓ Saved to {output_path}")

    # Print report info
    header = report.get('Header', {})
    print(f"\nReport Details:")
    print(f"  Name: {header.get('ReportName', 'Unknown')}")
    print(f"  Period: {header.get('StartPeriod', args.start_date)} to {header.get('EndPeriod', args.end_date)}")
    print(f"  Method: {args.method}")
    print(f"  Currency: {header.get('Currency', 'USD')}")


if __name__ == '__main__':
    main()
