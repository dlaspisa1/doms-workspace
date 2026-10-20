# Rename Scanned Documents (Google Drive)

## Purpose
Intelligently rename scanned documents in Google Drive based on their content. Uses Claude's vision capabilities to analyze PDFs and images, then renames them in the format: `Category_description.pdf`

## Inputs
- **Google Drive folder**: "Raven Scans" (Dlaspisa1@gmail.com)
- **File types**: All (PDFs, images: JPG, PNG, etc.)
- **Naming format**: `Category_description.pdf`

## Tools/Scripts
- `execution/gdrive_auth.py` - Google Drive authentication handler
- `execution/list_drive_files.py` - List files in specified folder and download for analysis
- `execution/analyze_scans_anthropic.py` - Automated analysis using Anthropic API
- `execution/rename_drive_files.py` - Execute renames based on mapping file

## Workflow

### Option A: Fully Automated (Anthropic API)

**Prerequisites:**
- Add `ANTHROPIC_API_KEY=sk-ant-...` to your `.env` file
- Install dependencies: `pip install anthropic python-dotenv`

**Run the full pipeline:**
```bash
# Step 1: Download files from Google Drive
python execution/list_drive_files.py "Raven Scans"

# Step 2: Analyze documents with Claude API (automated)
python execution/analyze_scans_anthropic.py

# Step 3: Execute renames in Google Drive
python execution/rename_drive_files.py .tmp/rename_mapping.json --auto
```

**Options for analyze_scans_anthropic.py:**
- `--scans-dir PATH` - Custom directory for scanned PDFs
- `--mapping PATH` - Custom path for rename mapping JSON
- `--reanalyze` - Re-analyze files already in mapping

### Option B: Interactive (Claude Code)

Use Claude Code directly for manual analysis with vision capabilities:

**Step 1: List Files**
```bash
python execution/list_drive_files.py "Raven Scans"
```
- Outputs: `.tmp/drive_files_list.json` (file IDs, names, types)
- Downloads files to: `.tmp/scanned_docs/` for analysis

**Step 2: Analyze & Generate Rename Map**
- Claude Code analyzes each file (PDF text, OCR images, vision analysis)
- Determines appropriate category and description
- Outputs: `.tmp/rename_mapping.json` with structure:
```json
{
  "file_id_123": {
    "old_name": "scan001.pdf",
    "new_name": "Utilities_electric_bill_jan_2026.pdf",
    "category": "Utilities",
    "confidence": "high"
  }
}
```

**Step 3: Execute Renames (Auto-Approved)**
```bash
python execution/rename_drive_files.py .tmp/rename_mapping.json --auto
```

## Categories (Common)
- `Financial_` - Bank statements, invoices, receipts
- `Medical_` - Health records, prescriptions, insurance
- `Legal_` - Contracts, agreements, official documents
- `Utilities_` - Electric, water, internet bills
- `Insurance_` - Policy documents, claims
- `Tax_` - Tax returns, W2s, 1099s
- `Personal_` - IDs, certificates, personal records
- `Education_` - Transcripts, certificates, course materials
- `Housing_` - Lease, mortgage, property documents
- `Auto_` - Registration, insurance, maintenance records
- `Other_` - Miscellaneous documents

## Edge Cases
- **Unreadable files**: Name as `Unreadable_scan_[date].ext`
- **Multi-page documents**: Analyze first 3 pages for context
- **Duplicate names**: Append `_v2`, `_v3`, etc.
- **Unclear category**: Use `Misc_` prefix
- **Low confidence**: Flag for manual review before renaming

## Error Handling
- **Rate limits**: Google Drive API has quota limits; script includes exponential backoff
- **Anthropic API limits**: The analysis script saves after each file to handle interruptions
- **Authentication**: Token expires → re-authenticate via OAuth flow
- **Gmail `invalid_grant` in `send_email`**: Google revoked the Gmail refresh token (typically a password change or a third-party-access review; the Drive token survives because only Gmail-scoped tokens are revoked). Filing has already finished when the email step fails, so only the report is lost. Fix: `python3 execution/mint_gmail_send_token.py` → sign in as dlaspisa1@gmail.com → it overwrites the Modal `gmail-token` secret directly (no redeploy, no local copy). Verify with `modal.Function.from_name('doc-rename-automation', 'test_email').remote()`. Keep the failure fatal — the Modal failure alert is the only signal that reports have stopped. (Seen 2026-10-19/20.)
- **File access**: Some files may be locked or have permission issues → skip and log
- **Large files / long PDFs**: Anthropic rejects requests >32 MB (HTTP 413) and PDFs >600 pages (HTTP 400). `modal_doc_rename.py` pre-trims every PDF with `pypdf` to its first 10 pages (`ANALYSIS_MAX_PAGES`) and halves the page count until the payload is under 20 MB (`ANALYSIS_MAX_BYTES`) before sending. The report shows a `NOTE:` line when trimming happened. Classification only needs the opening pages, so this doesn't hurt accuracy.
- **Invalid / corrupt PDFs**: Anthropic returns "The PDF specified was not valid." If `pypdf` can't parse the file, the script skips it with `SKIPPED (invalid PDF)` and lists it under STAYED — re-scan or re-export the file (e.g. print-to-PDF) and it will be picked up next run. (Seen 2026-08-28: `La Spisa - LL Juniper.pdf`.)

## Cost Estimate (Anthropic API)
- Using claude-sonnet-4-20250514 model
- ~$0.003-0.01 per document (varies by PDF size/complexity)
- 100 documents ≈ $0.30-1.00

## Notes
- All intermediate files (downloads) stored in `.tmp/scanned_docs/`
- Original filenames preserved in rename mapping for audit trail
- Script can be run in "dry-run" mode to preview changes without executing
- Supports batch processing of 100+ documents efficiently
- The mapping file acts as a checkpoint - safe to stop and resume

## Automated Daily Processing (Modal)

**Script:** `execution/modal_doc_rename.py`

**Schedule:** Daily 9am UTC (2am MST)

**What it does:**
1. Lists all PDFs in "Raven Scans" (including already-renamed ones)
2. Newly uploaded files (no Category_ prefix): analyzed with Claude, renamed
3. All files: routed to destination folder and moved out of Raven Scans
4. Emails report to dlaspisa1@gmail.com

**Manual trigger:**
```bash
modal profile activate dlaspisa1
modal run execution/modal_doc_rename.py
```

**Required secrets:**
- `gdrive-token` — Google Drive auth
- `anthropic-key` — Claude API key
- `gmail-token` — Gmail auth for email reports (`gmail.send` scope only, since 2026-10-20; mint with `execution/mint_gmail_send_token.py`)

**Deploy after changes:**
```bash
modal profile activate dlaspisa1
modal deploy execution/modal_doc_rename.py
```

## Filing Destinations

### Business routing (checked first, by filename keyword)
| Keyword in filename | Destination |
|---|---|
| Freehold / Freehold LLC | `Business/Freehold LLC/` |
| EC Brandz / DFW Capital / Westby / Illuminati Capital / Limitless AZ / Fountain Hills | `Raven Scans/LLC Files/` ← move to their drives manually |

### Personal routing by category
| Category | Keyword refinement | Destination |
|---|---|---|
| `Auto_` | Traffic, Speed, Violation | `Auto/Traffic Violations/` |
| `Auto_` | Service, Chapman | `Auto/Jeep Grand Wagoneer/Service/` |
| `Auto_` | Loan, Wells Fargo | `Auto/Jeep Grand Wagoneer/Loan/` |
| `Auto_` | Acadia, GMC | `Auto/GMC Acadia/` |
| `Auto_` | default | `Auto/Jeep Grand Wagoneer/` |
| `Legal_` | Traffic, Speed, MVD | `Auto/Traffic Violations/` |
| `Legal_` | Contract, Agreement, Lease | `Legal/Contracts/` |
| `Legal_` | S-Corp, Formation, Articles | `Legal/Business Formation/` |
| `Legal_` | Estate, Will, Trust | `Legal/Estate Planning/` |
| `Legal_` | IRS, Government, Court | `Legal/Government/` |
| `Legal_` | default | `Legal/` |
| `Housing_` | any | `Real Estate/2222 Val Vista/Mortgage/` |
| `Insurance_` | Surest, UHC, EOB, Health | `Health/Insurance/Dalila/` or `/Dominick/` |
| `Insurance_` | default | `Finance/Insurance/` |
| `Medical_` | any | `Health/Insurance/Dalila/` or `/Dominick/` |
| `Financial_` | 401k, IRA, PCRA, BREIT, trades | `Finance/Investments/Retirement/Dalila/` or `/Dominick/` |
| `Financial_` | Schwab, Fidelity, Brokerage, Statement | `Finance/Investments/Brokerage/` |
| `Financial_` | Earnings Statement, Payroll, Paystub | `Career/Dalila/` or `/Dominick/` |
| `Financial_` | Bank Statement, Checking | `Finance/Banking/Personal/` |
| `Financial_` | default | `Finance/` |
| `Tax_` | any | `Finance/Income Tax/` |
| `Utilities_` | SRP, Electric, Power | `Utilities/Electric/` |
| `Utilities_` | EPCOR, Water, Sewer | `Utilities/Water/` |
| `Utilities_` | Mesa (city bill — SRP provider) | `Utilities/Electric/` |
| `Utilities_` | default | stays in Raven Scans |
| `Personal_` | Franco | `Family/Franco/` |
| `Personal_` | Alessandra | `Family/Alessandra/` |
| `Personal_` | default | `Family/` |
| `Education_`, `Other_` | any | stays in Raven Scans |

## Manual tasks (Drive API cannot rename/move existing folders)
- Rename `Realestate/` → `Real Estate/`
- Move `Finance/Career/` contents → new `Career/` root folder
- Move `Finance/Dom and Dalila Trust/` → `Finance/Trust/`
- Move `Finance/Coinbase/` contents → `Finance/Investments/Crypto/`
- Move existing `Freehold LLC/` (root) files → `Business/Freehold LLC/`
- Delete unused `Traffic Ticket/` root folder (after moving any contents to `Auto/Traffic Violations/`)
- Delete unused `Business Inbox/` root folder (created in error, now replaced by `Raven Scans/LLC Files/`)
