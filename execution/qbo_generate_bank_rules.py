#!/usr/bin/env python3
"""
Generate QuickBooks Bank Rules Configuration
Creates detailed rule specifications for automated transaction categorization
"""

import os
import json
from collections import defaultdict
from qbo_client import get_client
from qbo_error_handler import handle_exception, QBOError, get_support_info

# Ensure .tmp directory exists
os.makedirs('.tmp/qbo_data', exist_ok=True)


def analyze_vendor_patterns():
    """Analyze vendor assignment results to generate rules"""

    results_file = '.tmp/qbo_data/vendor_assignment_results.json'
    if not os.path.exists(results_file):
        print("✗ No vendor assignment results found.")
        print("  Run: python3 execution/qbo_bulk_assign_vendors.py first")
        return None

    with open(results_file, 'r') as f:
        results = json.load(f)

    updated = results.get('updated', [])

    if not updated:
        print("✗ No transactions found to analyze.")
        return None

    # Group by vendor
    vendor_data = defaultdict(list)
    for txn in updated:
        vendor = txn['vendor']
        vendor_data[vendor].append(txn)

    return vendor_data


def extract_category_from_transaction(txn):
    """Extract category from transaction data"""
    # This would need to be enhanced based on actual transaction structure
    # For now, we'll use common mappings
    description = txn.get('description', '').upper()

    if 'CIRCLE K' in description:
        return 'Vehicle Fuel'
    elif any(word in description for word in ['COFFEE', 'RESTAURANT', 'BAR', 'GRILL', 'TACO']):
        return 'Meals and Entertainment'
    elif 'CAR WASH' in description:
        return 'Vehicle Expenses'
    elif 'MOTOR' in description:
        return 'Vehicle Warranty'
    elif 'LIQUOR' in description:
        return 'Meals and Entertainment'
    elif 'HEARTS' in description:
        return 'Contributions to Charities'
    else:
        return 'Miscellaneous'


def generate_bank_rules(vendor_data):
    """Generate bank rule configurations"""

    rules = []

    for vendor, transactions in sorted(vendor_data.items(),
                                      key=lambda x: len(x[1]),
                                      reverse=True):

        # Only create rules for vendors with 2+ transactions
        if len(transactions) < 2:
            continue

        # Extract category from first transaction
        category = extract_category_from_transaction(transactions[0])

        # Calculate average amount
        amounts = [txn['amount'] for txn in transactions]
        avg_amount = sum(amounts) / len(amounts)

        # Determine search terms
        search_terms = []

        # Add vendor name variations
        search_terms.append(vendor)

        # Add simplified version if needed
        if ' ' in vendor:
            parts = vendor.split()
            if len(parts[0]) > 3:  # Add first word if meaningful
                search_terms.append(parts[0])

        rule = {
            'rule_name': f'Auto-categorize {vendor}',
            'vendor': vendor,
            'search_terms': search_terms,
            'category': category,
            'transaction_count': len(transactions),
            'total_amount': sum(amounts),
            'avg_amount': avg_amount,
            'auto_add': True if len(transactions) >= 5 else False,
            'priority': 'High' if len(transactions) >= 5 else 'Medium'
        }

        rules.append(rule)

    return rules


def export_rules_to_csv(rules):
    """Export rules to CSV format"""
    csv_file = '.tmp/qbo_data/bank_rules.csv'

    with open(csv_file, 'w') as f:
        # Header
        f.write('Rule Name,Vendor,Search Terms,Category,Auto-Add,Priority,Transaction Count,Total Amount\n')

        # Data
        for rule in rules:
            search_terms = ' OR '.join(rule['search_terms'])
            f.write(f'"{rule["rule_name"]}","{rule["vendor"]}","{search_terms}","{rule["category"]}",')
            f.write(f'{"Yes" if rule["auto_add"] else "No"},{rule["priority"]},')
            f.write(f'{rule["transaction_count"]},${rule["total_amount"]:.2f}\n')

    return csv_file


def generate_setup_guide(rules):
    """Generate detailed setup guide"""
    guide_file = '.tmp/qbo_data/bank_rules_setup_guide.md'

    with open(guide_file, 'w') as f:
        f.write('# QuickBooks Bank Rules Setup Guide\n\n')
        f.write('## Quick Setup Instructions\n\n')
        f.write('1. Log into QuickBooks Online\n')
        f.write('2. Click **Banking** in the left menu\n')
        f.write('3. Click **Rules** tab at the top\n')
        f.write('4. Click **New Rule** button\n')
        f.write('5. Follow the configurations below\n\n')
        f.write('---\n\n')

        for i, rule in enumerate(rules, 1):
            f.write(f'## Rule {i}: {rule["rule_name"]}\n\n')
            f.write(f'**Priority:** {rule["priority"]} ({rule["transaction_count"]} transactions, ${rule["total_amount"]:,.2f} total)\n\n')

            f.write('### Configuration\n\n')
            f.write('**Rule Name:**\n')
            f.write(f'```\n{rule["rule_name"]}\n```\n\n')

            f.write('**Money Out:**\n')
            f.write('```\nYes (for expenses)\n```\n\n')

            f.write('**In the Description:**\n')
            f.write('```\n')
            for term in rule['search_terms']:
                f.write(f'Contains: {term}\n')
            f.write('```\n\n')

            f.write('**Transaction Type:**\n')
            f.write('```\nExpense\n```\n\n')

            f.write('**Category:**\n')
            f.write(f'```\n{rule["category"]}\n```\n\n')

            f.write('**Payee/Vendor:**\n')
            f.write(f'```\n{rule["vendor"]}\n```\n\n')

            f.write('**Automatically confirm transactions this rule applies to:**\n')
            f.write(f'```\n{"✓ Yes" if rule["auto_add"] else "☐ No (Review first)"}\n```\n\n')

            f.write('### Why This Rule?\n\n')
            f.write(f'- Found {rule["transaction_count"]} transactions from {rule["vendor"]}\n')
            f.write(f'- Average transaction: ${rule["avg_amount"]:.2f}\n')
            f.write(f'- Total spend: ${rule["total_amount"]:.2f}\n\n')

            f.write('---\n\n')

        f.write('## Tips for Rule Management\n\n')
        f.write('- Start with high-priority rules (5+ transactions)\n')
        f.write('- Test rules before enabling auto-add\n')
        f.write('- Review rule performance monthly\n')
        f.write('- Edit rules if vendor names change\n')
        f.write('- Use "Contains" for partial matches\n')
        f.write('- Be specific enough to avoid false matches\n\n')

        f.write('## Rule Priority Recommendations\n\n')
        f.write('1. **High Priority (Auto-Add):** Frequent vendors (5+ transactions)\n')
        f.write('2. **Medium Priority (Review):** Regular vendors (2-4 transactions)\n')
        f.write('3. **Low Priority:** One-time vendors (create as needed)\n\n')

    return guide_file


@handle_exception
def main():
    try:
        print("QuickBooks Bank Rules Generator\n")
        print("="*60)

        client = get_client()
        print(f"Connected to QuickBooks (Realm ID: {client.realm_id})\n")

        # Analyze vendor patterns
        print("Analyzing vendor patterns...")
        vendor_data = analyze_vendor_patterns()

        if not vendor_data:
            return

        print(f"Found {len(vendor_data)} vendors\n")

        # Generate rules
        print("Generating bank rules...")
        rules = generate_bank_rules(vendor_data)

        print(f"Generated {len(rules)} recommended rules\n")

        # Export to CSV
        csv_file = export_rules_to_csv(rules)
        print(f"✓ CSV export saved to {csv_file}")

        # Generate setup guide
        guide_file = generate_setup_guide(rules)
        print(f"✓ Setup guide saved to {guide_file}")

        # Save JSON
        json_file = '.tmp/qbo_data/bank_rules.json'
        with open(json_file, 'w') as f:
            json.dump(rules, f, indent=2)
        print(f"✓ JSON data saved to {json_file}\n")

        # Print summary
        print("="*60)
        print("BANK RULES SUMMARY")
        print("="*60)

        high_priority = [r for r in rules if r['priority'] == 'High']
        medium_priority = [r for r in rules if r['priority'] == 'Medium']

        print(f"\n📊 RULE BREAKDOWN:")
        print(f"  High Priority (Auto-Add): {len(high_priority)} rules")
        print(f"  Medium Priority (Review): {len(medium_priority)} rules")
        print(f"  Total Rules: {len(rules)}")

        if high_priority:
            print(f"\n⚡ HIGH PRIORITY RULES (Setup First):")
            for rule in high_priority:
                print(f"  • {rule['vendor']} - {rule['transaction_count']} transactions")

        print(f"\n📝 MEDIUM PRIORITY RULES:")
        for rule in medium_priority:
            print(f"  • {rule['vendor']} - {rule['transaction_count']} transactions")

        print("\n" + "="*60)
        print("NEXT STEPS")
        print("="*60)
        print(f"\n1. Open the setup guide:")
        print(f"   {guide_file}")
        print(f"\n2. Log into QuickBooks Online")
        print(f"\n3. Go to Banking → Rules → New Rule")
        print(f"\n4. Follow the guide to create each rule")
        print(f"\n5. Start with High Priority rules first")
        print(f"\n6. Test rules before enabling auto-add")

        print("\n" + "="*60)
        print("ESTIMATED TIME SAVINGS")
        print("="*60)

        total_transactions = sum(r['transaction_count'] for r in rules)
        time_per_transaction = 30  # seconds
        total_time_saved_monthly = (total_transactions * time_per_transaction) / 60

        print(f"\nWith these {len(rules)} rules:")
        print(f"  • Covers {total_transactions} past transactions")
        print(f"  • Saves ~{time_per_transaction} seconds per transaction")
        print(f"  • Estimated monthly time savings: {total_time_saved_monthly:.0f} minutes")
        print(f"  • Annual time savings: {total_time_saved_monthly * 12 / 60:.1f} hours")

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
