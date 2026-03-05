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
- **File access**: Some files may be locked or have permission issues → skip and log
- **Large files**: Files >10MB may take longer to download/analyze

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

## Automated Weekly Processing (Modal)

A Modal automation runs weekly to process new scans automatically.

**Script:** `execution/modal_doc_rename.py`

**Schedule:** Sunday 9am UTC (2am MST)

**What it does:**
1. Connects to Google Drive "Raven Scans" folder
2. Skips already-categorized files (those with Category_ prefix)
3. Downloads and analyzes new PDFs with Gemini
4. Renames files in Drive
5. Emails report to dlaspisa1@gmail.com

**Manual trigger:**
```bash
modal run execution/modal_doc_rename.py
```

**Required secrets:**
- `gdrive-token` - Google Drive auth (token_drive.json)
- `gemini-key` - Gemini API key (requires billing enabled on Google Cloud project)
- `gmail-token` - Gmail auth for email reports (token.json)

**Key learning:** Gemini API requires billing enabled on the Google Cloud project, even for free tier usage. Without billing, quota is set to 0.
