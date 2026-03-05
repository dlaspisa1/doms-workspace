# QuickBooks Year-End Close Process

## Purpose
Systematic review and close of QuickBooks books for a specific company and fiscal year. Ensures all transactions are posted, accounts are reconciled, anomalies are identified, and necessary adjusting journal entries are made.

## Prerequisites
- QuickBooks Online API credentials configured in `.env`
- OAuth tokens valid (run `execution/qbo_auth.py` if needed)
- Target company's Realm ID in `.env`

## Company Configuration
Set the target company in `.env`:
```
QBO_REALM_ID=9341454919384635  # Freehold LLC
```

## Year-End Close Checklist

### Phase 1: Pre-Close Review (Unposted Items)

**Goal:** Ensure all transactions are posted before review.

1. **Pull all unposted/draft transactions**
   ```bash
   cd "/Users/dominicklaspisa/Doms workspace"
   python execution/qbo_review_unposted.py
   ```

2. **Review pending items:**
   - Draft invoices
   - Unapproved bills
   - Pending bank transactions
   - Uncategorized transactions
   - Bank feeds not matched

3. **Action:** Post, delete, or void each unposted item before proceeding.

### Phase 2: Account Review (Anomaly Detection)

**Goal:** Identify posting errors and unusual balances.

1. **Pull Trial Balance as of close date**
   ```bash
   python execution/qbo_get_report.py --report trial_balance --end-date 2025-12-31
   ```

2. **Run anomaly detection**
   ```bash
   python execution/qbo_detect_anomalies.py --year 2025
   ```

   This checks for:
   - Accounts with unusual balance signs (e.g., negative AR, positive AP)
   - Significant variance vs prior year (>25%)
   - Round number transactions (potential estimates needing true-up)
   - Duplicate transactions (same amount, date, vendor)
   - Uncleared bank transactions older than 90 days
   - Suspense/clearing accounts with balances
   - Intercompany accounts out of balance

3. **Review each flagged item** and determine if JE is needed.

### Phase 3: Standard Year-End Adjustments

**Goal:** Identify and record necessary adjusting entries.

1. **Run JE recommendation engine**
   ```bash
   python execution/qbo_recommend_jes.py --year 2025
   ```

   Common adjustments to consider:
   - **Accruals:** Expenses incurred but not yet billed
   - **Prepaid expenses:** Amortization of prepaid items
   - **Depreciation:** Fixed asset depreciation entries
   - **Bad debt:** Allowance for doubtful accounts
   - **Inventory adjustments:** Count vs book reconciliation
   - **Payroll accruals:** Wages earned but not paid
   - **Interest accruals:** Loan interest through year-end
   - **Deferred revenue:** Revenue recognition adjustments

2. **Review P&L for reasonableness**
   ```bash
   python execution/qbo_get_report.py --report profit_and_loss --start-date 2025-01-01 --end-date 2025-12-31
   ```

3. **Review Balance Sheet**
   ```bash
   python execution/qbo_get_report.py --report balance_sheet --date 2025-12-31
   ```

### Phase 4: Bank & Credit Card Reconciliation

**Goal:** Ensure all bank/CC accounts are reconciled through 12/31.

1. **Check reconciliation status**
   ```bash
   python execution/qbo_check_reconciliation.py --date 2025-12-31
   ```

2. **For unreconciled accounts:**
   - Pull December statement
   - Complete reconciliation in QuickBooks
   - Investigate and resolve any differences

### Phase 5: Final Review & Documentation

**Goal:** Generate final reports and document close.

1. **Generate final Trial Balance**
   ```bash
   python execution/qbo_get_report.py --report trial_balance --end-date 2025-12-31
   ```

2. **Generate final P&L and Balance Sheet**
   ```bash
   python execution/qbo_get_report.py --report profit_and_loss --start-date 2025-01-01 --end-date 2025-12-31
   python execution/qbo_get_report.py --report balance_sheet --end-date 2025-12-31
   ```

3. **Review and document:**
   - Trial Balance
   - P&L (full year)
   - Balance Sheet
   - List of all JEs made during close
   - Anomaly report with resolutions

3. **Close the period in QuickBooks** (manual step in QBO UI)
   - Settings > Account and Settings > Advanced > Close the books

## Output Files

All intermediate files saved to `.tmp/year_end_close/`:
- `trial_balance_2025.json` - Trial balance data
- `anomalies_2025.json` - Flagged items requiring review
- `recommended_jes_2025.json` - Suggested journal entries
- `reconciliation_status_2025.json` - Bank reconciliation status
- `unposted_2025.json` - List of unposted transactions

## Error Handling

If scripts fail:
1. Check `.tmp/logs/qbo_errors.log` for details
2. Re-authenticate if token expired: `python execution/qbo_auth.py`
3. Verify Realm ID matches target company

## Learnings & Updates

### 2025-01-23
- Initial directive created for Freehold LLC 2025 close
- Defined 5-phase close process
- Scripts available:
  - `qbo_review_unposted.py` - Review unposted transactions (invoices, bills, estimates, POs)
  - `qbo_get_report.py` - Pull financial reports (P&L, Balance Sheet, Trial Balance, AR/AP Aging)
  - `qbo_detect_anomalies.py` - Detect posting errors and unusual balances
  - `qbo_recommend_jes.py` - Generate adjusting entry recommendations
  - `qbo_check_reconciliation.py` - Check bank/CC reconciliation status
