#!/usr/bin/env python3
"""
Get customers from QuickBooks Online with error handling
"""

import os
import json
import argparse
from qbo_client import get_client
from qbo_error_handler import handle_exception, QBOError, get_support_info
from quickbooks.objects.customer import Customer

# Ensure .tmp directory exists
os.makedirs('.tmp/qbo_data', exist_ok=True)


def get_customers(active_only=False, max_results=1000):
    """
    Get customer list

    Args:
        active_only: Only return active customers
        max_results: Maximum number of results

    Returns:
        List of customer dictionaries
    """
    client = get_client()

    # Build query
    if active_only:
        query = "SELECT * FROM Customer WHERE Active = true"
    else:
        query = "SELECT * FROM Customer"

    query += f" MAXRESULTS {max_results}"

    print(f"Executing query: {query}\n")

    # Execute query
    customers = Customer.query(query, qb=client.client)

    # Convert to dictionaries
    customer_list = []
    for cust in customers:
        customer_data = {
            'id': cust.Id,
            'display_name': cust.DisplayName,
            'company_name': cust.CompanyName,
            'given_name': cust.GivenName,
            'family_name': cust.FamilyName,
            'primary_email': cust.PrimaryEmailAddr.Address if cust.PrimaryEmailAddr else None,
            'primary_phone': cust.PrimaryPhone.FreeFormNumber if cust.PrimaryPhone else None,
            'balance': float(cust.Balance) if cust.Balance else 0.0,
            'active': cust.Active,
        }

        # Add billing address if exists
        if cust.BillAddr:
            customer_data['billing_address'] = {
                'line1': cust.BillAddr.Line1,
                'city': cust.BillAddr.City,
                'country_sub_division_code': cust.BillAddr.CountrySubDivisionCode,
                'postal_code': cust.BillAddr.PostalCode,
            }

        customer_list.append(customer_data)

    return customer_list


def main():
    parser = argparse.ArgumentParser(description='Get QuickBooks customers')
    parser.add_argument('--active-only', action='store_true', help='Only return active customers')
    parser.add_argument('--max-results', type=int, default=1000, help='Maximum results')
    parser.add_argument('--output', default='.tmp/qbo_data/customers.json', help='Output file path')

    args = parser.parse_args()

    print("Fetching QuickBooks customers...\n")

    customers = get_customers(
        active_only=args.active_only,
        max_results=args.max_results
    )

    # Save to file
    with open(args.output, 'w') as f:
        json.dump(customers, f, indent=2)

    print(f"✓ Found {len(customers)} customers")
    print(f"✓ Saved to {args.output}")

    # Print summary
    active_count = sum(1 for c in customers if c['active'])
    total_balance = sum(c['balance'] for c in customers)
    with_email = sum(1 for c in customers if c['primary_email'])

    print(f"\nSummary:")
    print(f"  Total customers: {len(customers)}")
    print(f"  Active: {active_count}")
    print(f"  Inactive: {len(customers) - active_count}")
    print(f"  With email: {with_email}")
    print(f"  Total balance: ${total_balance:,.2f}")


if __name__ == '__main__':
    main()
