#!/usr/bin/env python3
"""
Review unposted/draft transactions in QuickBooks Online
Analyzes various transaction types and provides posting suggestions
"""

import os
import json
from datetime import datetime
from qbo_client import get_client
from qbo_error_handler import handle_exception, QBOError, get_support_info
from quickbooks.objects.invoice import Invoice
from quickbooks.objects.bill import Bill
from quickbooks.objects.estimate import Estimate
from quickbooks.objects.salesreceipt import SalesReceipt
from quickbooks.objects.purchaseorder import PurchaseOrder
from quickbooks.objects.payment import Payment
from quickbooks.objects.journalentry import JournalEntry

# Ensure .tmp directory exists
os.makedirs('.tmp/qbo_data', exist_ok=True)


def check_draft_invoices(client):
    """Check for draft/unpaid invoices"""
    print("Checking for invoices...")

    # Get all invoices
    query = "SELECT * FROM Invoice MAXRESULTS 1000"
    invoices = Invoice.query(query, qb=client.client)

    draft_invoices = []
    unpaid_invoices = []

    for inv in invoices:
        inv_data = {
            'type': 'Invoice',
            'id': inv.Id,
            'doc_number': inv.DocNumber,
            'date': str(inv.TxnDate),
            'customer': inv.CustomerRef.name if inv.CustomerRef else 'Unknown',
            'total': float(inv.TotalAmt) if inv.TotalAmt else 0.0,
            'balance': float(inv.Balance) if inv.Balance else 0.0,
            'email_status': getattr(inv, 'EmailStatus', 'NotSet'),
            'print_status': getattr(inv, 'PrintStatus', 'NotSet'),
        }

        # Check if unpaid
        if inv_data['balance'] > 0:
            unpaid_invoices.append(inv_data)

    return unpaid_invoices


def check_estimates(client):
    """Check for estimates that haven't been converted to invoices"""
    print("Checking for estimates...")

    query = "SELECT * FROM Estimate MAXRESULTS 1000"
    estimates = Estimate.query(query, qb=client.client)

    open_estimates = []

    for est in estimates:
        est_data = {
            'type': 'Estimate',
            'id': est.Id,
            'doc_number': est.DocNumber,
            'date': str(est.TxnDate),
            'customer': est.CustomerRef.name if est.CustomerRef else 'Unknown',
            'total': float(est.TotalAmt) if est.TotalAmt else 0.0,
            'status': getattr(est, 'TxnStatus', 'Unknown'),
            'email_status': getattr(est, 'EmailStatus', 'NotSet'),
        }

        # Open estimates that haven't been accepted/closed
        if est_data['status'] in ['Pending', 'Accepted', None, 'Unknown']:
            open_estimates.append(est_data)

    return open_estimates


def check_bills(client):
    """Check for unpaid bills"""
    print("Checking for bills...")

    query = "SELECT * FROM Bill MAXRESULTS 1000"
    bills = Bill.query(query, qb=client.client)

    unpaid_bills = []

    for bill in bills:
        bill_data = {
            'type': 'Bill',
            'id': bill.Id,
            'doc_number': getattr(bill, 'DocNumber', 'N/A'),
            'date': str(bill.TxnDate),
            'vendor': bill.VendorRef.name if bill.VendorRef else 'Unknown',
            'total': float(bill.TotalAmt) if bill.TotalAmt else 0.0,
            'balance': float(bill.Balance) if bill.Balance else 0.0,
            'due_date': str(bill.DueDate) if bill.DueDate else None,
        }

        # Unpaid bills
        if bill_data['balance'] > 0:
            unpaid_bills.append(bill_data)

    return unpaid_bills


def check_purchase_orders(client):
    """Check for open purchase orders"""
    print("Checking for purchase orders...")

    query = "SELECT * FROM PurchaseOrder MAXRESULTS 1000"
    purchase_orders = PurchaseOrder.query(query, qb=client.client)

    open_pos = []

    for po in purchase_orders:
        po_data = {
            'type': 'PurchaseOrder',
            'id': po.Id,
            'doc_number': po.DocNumber,
            'date': str(po.TxnDate),
            'vendor': po.VendorRef.name if po.VendorRef else 'Unknown',
            'total': float(po.TotalAmt) if po.TotalAmt else 0.0,
            'status': getattr(po, 'POStatus', 'Unknown'),
        }

        # Open POs that haven't been closed
        if po_data['status'] in ['Open', None, 'Unknown']:
            open_pos.append(po_data)

    return open_pos


def check_journal_entries(client):
    """Check for unapproved journal entries"""
    print("Checking for journal entries...")

    query = "SELECT * FROM JournalEntry MAXRESULTS 1000"
    journal_entries = JournalEntry.query(query, qb=client.client)

    entries = []

    for je in journal_entries:
        je_data = {
            'type': 'JournalEntry',
            'id': je.Id,
            'doc_number': je.DocNumber,
            'date': str(je.TxnDate),
            'total': float(je.TotalAmt) if je.TotalAmt else 0.0,
        }
        entries.append(je_data)

    return entries


def generate_posting_suggestions(results):
    """Generate suggestions for posting transactions"""
    suggestions = []

    # Unpaid invoices
    if results['unpaid_invoices']:
        total_unpaid = sum(inv['balance'] for inv in results['unpaid_invoices'])
        suggestions.append({
            'category': 'Unpaid Invoices',
            'count': len(results['unpaid_invoices']),
            'total_amount': total_unpaid,
            'action': 'Record Payments',
            'steps': [
                '1. Review each unpaid invoice',
                '2. Contact customers for payment',
                '3. Record payment when received (+ icon → Receive Payment)',
                '4. Match to bank deposit when it clears',
            ],
            'priority': 'High' if total_unpaid > 1000 else 'Medium',
        })

    # Open estimates
    if results['estimates']:
        total_estimates = sum(est['total'] for est in results['estimates'])
        suggestions.append({
            'category': 'Open Estimates',
            'count': len(results['estimates']),
            'total_amount': total_estimates,
            'action': 'Convert to Invoices',
            'steps': [
                '1. Contact customers to confirm acceptance',
                '2. Open estimate → Create Invoice',
                '3. Send invoice to customer',
                '4. Or mark estimate as Rejected if not accepted',
            ],
            'priority': 'Medium',
        })

    # Unpaid bills
    if results['unpaid_bills']:
        total_bills = sum(bill['balance'] for bill in results['unpaid_bills'])
        overdue = [b for b in results['unpaid_bills']
                   if b['due_date'] and b['due_date'] < str(datetime.now().date())]

        suggestions.append({
            'category': 'Unpaid Bills',
            'count': len(results['unpaid_bills']),
            'total_amount': total_bills,
            'overdue_count': len(overdue),
            'action': 'Pay Bills',
            'steps': [
                '1. Review bills and due dates',
                '2. Prioritize overdue bills',
                '3. Record bill payment (+ icon → Pay Bills)',
                '4. Match to bank transaction when it clears',
            ],
            'priority': 'High' if overdue else 'Medium',
        })

    # Open purchase orders
    if results['purchase_orders']:
        total_pos = sum(po['total'] for po in results['purchase_orders'])
        suggestions.append({
            'category': 'Open Purchase Orders',
            'count': len(results['purchase_orders']),
            'total_amount': total_pos,
            'action': 'Receive Items or Close POs',
            'steps': [
                '1. Check if items have been received',
                '2. Open PO → Create Bill (when received)',
                '3. Or close PO if cancelled',
                '4. Update PO status accordingly',
            ],
            'priority': 'Low',
        })

    # Journal entries
    if results['journal_entries']:
        suggestions.append({
            'category': 'Journal Entries',
            'count': len(results['journal_entries']),
            'action': 'Review for Accuracy',
            'steps': [
                '1. Review each journal entry',
                '2. Verify debits = credits',
                '3. Ensure proper account coding',
                '4. Add memo/description if missing',
            ],
            'priority': 'Low',
        })

    return suggestions


@handle_exception
def main():
    try:
        print("QuickBooks Unposted Transaction Review\n")
        print("="*60)

        client = get_client()
        print(f"Connected to QuickBooks (Realm ID: {client.realm_id})\n")

        # Collect all transaction data
        results = {
            'unpaid_invoices': check_draft_invoices(client),
            'estimates': check_estimates(client),
            'unpaid_bills': check_bills(client),
            'purchase_orders': check_purchase_orders(client),
            'journal_entries': check_journal_entries(client),
        }

        # Save raw data
        output_file = '.tmp/qbo_data/unposted_transactions.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        print(f"\n✓ Raw data saved to {output_file}\n")

        # Generate suggestions
        suggestions = generate_posting_suggestions(results)

        # Save suggestions
        suggestions_file = '.tmp/qbo_data/posting_suggestions.json'
        with open(suggestions_file, 'w') as f:
            json.dump(suggestions, f, indent=2)

        print("="*60)
        print("SUMMARY OF UNPOSTED TRANSACTIONS")
        print("="*60)

        # Print summary
        print(f"\nUnpaid Invoices: {len(results['unpaid_invoices'])}")
        if results['unpaid_invoices']:
            total = sum(inv['balance'] for inv in results['unpaid_invoices'])
            print(f"  Total Outstanding: ${total:,.2f}")
            print(f"  Top 3:")
            for inv in sorted(results['unpaid_invoices'],
                            key=lambda x: x['balance'], reverse=True)[:3]:
                print(f"    - {inv['doc_number']}: {inv['customer']} - ${inv['balance']:,.2f}")

        print(f"\nOpen Estimates: {len(results['estimates'])}")
        if results['estimates']:
            total = sum(est['total'] for est in results['estimates'])
            print(f"  Total Value: ${total:,.2f}")
            print(f"  Top 3:")
            for est in sorted(results['estimates'],
                            key=lambda x: x['total'], reverse=True)[:3]:
                print(f"    - {est['doc_number']}: {est['customer']} - ${est['total']:,.2f}")

        print(f"\nUnpaid Bills: {len(results['unpaid_bills'])}")
        if results['unpaid_bills']:
            total = sum(bill['balance'] for bill in results['unpaid_bills'])
            overdue = [b for b in results['unpaid_bills']
                      if b['due_date'] and b['due_date'] < str(datetime.now().date())]
            print(f"  Total Owed: ${total:,.2f}")
            print(f"  Overdue: {len(overdue)}")
            if overdue:
                print(f"  Overdue bills:")
                for bill in overdue[:3]:
                    print(f"    - {bill['vendor']}: ${bill['balance']:,.2f} (Due: {bill['due_date']})")

        print(f"\nOpen Purchase Orders: {len(results['purchase_orders'])}")
        print(f"Journal Entries: {len(results['journal_entries'])}")

        # Print suggestions
        print("\n" + "="*60)
        print("POSTING SUGGESTIONS")
        print("="*60)

        if not suggestions:
            print("\n✓ All caught up! No unposted transactions found.")
        else:
            for i, suggestion in enumerate(suggestions, 1):
                print(f"\n{i}. {suggestion['category']}")
                print(f"   Priority: {suggestion['priority']}")
                print(f"   Count: {suggestion['count']}")
                if 'total_amount' in suggestion:
                    print(f"   Total Amount: ${suggestion['total_amount']:,.2f}")
                if 'overdue_count' in suggestion:
                    print(f"   Overdue: {suggestion['overdue_count']}")
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
        print(f"\n{get_support_info()['message']}")
        raise


if __name__ == '__main__':
    main()
