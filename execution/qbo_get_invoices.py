#!/usr/bin/env python3
"""
Get invoices from QuickBooks Online with error handling
"""

import os
import json
import argparse
from datetime import datetime
from qbo_client import get_client
from qbo_error_handler import handle_exception, QBOError, get_support_info
from quickbooks.objects.invoice import Invoice

# Ensure .tmp directory exists
os.makedirs('.tmp/qbo_data', exist_ok=True)


def get_invoices(start_date=None, end_date=None, customer_id=None, status=None, max_results=1000):
    """
    Get invoices with optional filters

    Args:
        start_date: Filter invoices after this date (YYYY-MM-DD)
        end_date: Filter invoices before this date (YYYY-MM-DD)
        customer_id: Filter by customer ID
        status: Filter by status (Paid, Unpaid, Pending, etc.)
        max_results: Maximum number of results

    Returns:
        List of invoice dictionaries
    """
    client = get_client()

    # Build query
    query = "SELECT * FROM Invoice"
    conditions = []

    if start_date:
        conditions.append(f"TxnDate >= '{start_date}'")

    if end_date:
        conditions.append(f"TxnDate <= '{end_date}'")

    if customer_id:
        conditions.append(f"CustomerRef = '{customer_id}'")

    if status:
        # Map common status values
        if status.lower() == 'paid':
            conditions.append("Balance = '0'")
        elif status.lower() == 'unpaid':
            conditions.append("Balance > '0'")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += f" MAXRESULTS {max_results}"

    print(f"Executing query: {query}\n")

    # Execute query
    invoices = Invoice.query(query, qb=client.client)

    # Convert to dictionaries
    invoice_list = []
    for inv in invoices:
        invoice_data = {
            'id': inv.Id,
            'doc_number': inv.DocNumber,
            'txn_date': str(inv.TxnDate),
            'customer_id': inv.CustomerRef.value if inv.CustomerRef else None,
            'customer_name': inv.CustomerRef.name if inv.CustomerRef else None,
            'total_amt': float(inv.TotalAmt) if inv.TotalAmt else 0.0,
            'balance': float(inv.Balance) if inv.Balance else 0.0,
            'due_date': str(inv.DueDate) if inv.DueDate else None,
            'email_status': inv.EmailStatus,
            'status': 'Paid' if (inv.Balance == 0 or inv.Balance == '0') else 'Unpaid',
        }
        invoice_list.append(invoice_data)

    return invoice_list


@handle_exception
def main():
    parser = argparse.ArgumentParser(description='Get QuickBooks invoices')
    parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')
    parser.add_argument('--customer-id', help='Filter by customer ID')
    parser.add_argument('--status', choices=['paid', 'unpaid', 'all'], default='all', help='Filter by payment status')
    parser.add_argument('--max-results', type=int, default=1000, help='Maximum results')
    parser.add_argument('--output', default='.tmp/qbo_data/invoices.json', help='Output file path')

    args = parser.parse_args()

    try:
        print("Fetching QuickBooks invoices...\n")

        status_filter = None if args.status == 'all' else args.status

        invoices = get_invoices(
            start_date=args.start_date,
            end_date=args.end_date,
            customer_id=args.customer_id,
            status=status_filter,
            max_results=args.max_results
        )

        # Save to file
        with open(args.output, 'w') as f:
            json.dump(invoices, f, indent=2)

        print(f"✓ Found {len(invoices)} invoices")
        print(f"✓ Saved to {args.output}")

        # Print summary
        total_amount = sum(inv['total_amt'] for inv in invoices)
        total_balance = sum(inv['balance'] for inv in invoices)
        paid_count = sum(1 for inv in invoices if inv['status'] == 'Paid')
        unpaid_count = len(invoices) - paid_count

        print(f"\nSummary:")
        print(f"  Total invoices: {len(invoices)}")
        print(f"  Paid: {paid_count}")
        print(f"  Unpaid: {unpaid_count}")
        print(f"  Total amount: ${total_amount:,.2f}")
        print(f"  Outstanding balance: ${total_balance:,.2f}")

    except QBOError as e:
        print(f"\n✗ QuickBooks Error: {e.message}")
        if e.intuit_tid:
            print(f"  Transaction ID: {e.intuit_tid}")
        print(f"\n{get_support_info()['message']}")
        raise
    except Exception as e:
        print(f"\n✗ Unexpected error: {str(e)}")
        print(f"\n{get_support_info()['message']}")
        raise


if __name__ == '__main__':
    main()
