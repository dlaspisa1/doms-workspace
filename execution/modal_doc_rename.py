"""
Document Rename + File Automation - Modal

Renames scanned PDFs in "Raven Scans", then moves each to its destination:

  Personal docs  → matching Drive folder based on category + keywords
  Freehold LLC   → Business/Freehold LLC/
  EC Brandz /    → Raven Scans/LLC Files/  (move to those drives manually)
  DFW Capital

Unroutable personal docs (no matching folder) stay in Raven Scans.
Runs daily at 9am UTC.  Manual trigger: modal run execution/modal_doc_rename.py
"""

import modal
import json
import os
import io
import base64
from datetime import datetime

app = modal.App("doc-rename-automation")

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "google-api-python-client",
    "google-auth",
    "anthropic",
    "pypdf",
)

# Anthropic PDF limits: 32 MB per request, 600 pages per document.
# Classification only needs the opening pages, so we always trim.
ANALYSIS_MAX_PAGES  = 10
ANALYSIS_MAX_BYTES  = 20 * 1024 * 1024   # stay well under the 32 MB request cap

RAVEN_SCANS_NAME = "Raven Scans"
EMAIL = "dlaspisa1@gmail.com"

CATEGORIES = [
    "Financial", "Medical", "Legal", "Utilities", "Insurance",
    "Tax", "Personal", "Education", "Housing", "Auto", "Other"
]

# ── Folder ID reference ───────────────────────────────────────────────────────
# Root / top-level
FINANCE             = "1V0jQMB83eGsRKgvD3INOqsOOonyGhVx5"
BUSINESS_FREEHOLD   = "1FHIGE8V3NIzvUh18xqV5rIxI1RFNHxsm"  # Business/Freehold LLC
LLC_FILES           = "1SvuReWjEicyPSvLYyEPhjkObnNPj1FOM"   # Raven Scans/LLC Files

# Finance sub-folders
FINANCE_BANKING_PERSONAL  = "1uIYDZTwGMbtEtVIg8NA0x1P6iTuHBhMA"
FINANCE_BANKING_BUSINESS  = "1L4bWSOLn3tUwZd4Wp4w4ZNSFrmH4WsaH"
FINANCE_INVEST_BROKERAGE  = "1QH0ECH7dofIL9mkjhS2e5O5NAJJSkBUl"
FINANCE_INVEST_RETIRE     = "1qXZdXMR8CophskSWbs3Q9hMdpgieZie0"
FINANCE_INVEST_RETIRE_DOM = "1ENFW0AZIQ7B1kV_2fCcyC38Wk_BoX4bi"
FINANCE_INVEST_RETIRE_DAL = "1ugf5nsHvrhe118YPqaQyB22bxH9RKrDP"
FINANCE_INVEST_CRYPTO     = "1FoxXgw1iTqQaWPJbxgetJN74lQDuzjZK"
FINANCE_INSURANCE         = "0BzEIAvkM1YZBMmpDdlkyM25Cems"
FINANCE_INCOME_TAX        = "0BzEIAvkM1YZBUWtCZWZkcHhSNE0"

# Auto
AUTO_TRAFFIC_VIOLATIONS   = "1zv42PmEQAtRXNShBOXYM8BlU42bQwJdn"  # Auto/Traffic Violations
AUTO_JEEP                 = "1M4oLY4Lg5Z0buR4K8KUUqtCBTdtLSQbF"
AUTO_JEEP_LOAN            = "1STY97aBb8z2Bap-bS4ogXgiP-58zAEcB"
AUTO_JEEP_SERVICE         = "1MRV2b_fpbXgAEESHlVq0r1y4fgKo4p81"
AUTO_ACADIA               = "1MMLj214LY5uoW9Q3h5BdJpC-KqfNOh-_"

# Legal
LEGAL                     = "13iFiA2grPAwPbX2vnJFc0DgP8Vdh9Ijm"
LEGAL_CONTRACTS           = "1QvQJZF_t5Zf2zuDSRmZScZ2rxGiDeigo"
LEGAL_BIZ_FORMATION       = "1sN2bZ3tJGkKXalD-WwSTj4e5S98apdNG"
LEGAL_ESTATE_PLANNING     = "1BImHGDTP0c9yEfTFVV4mVjp3Jw9fMwwd"
LEGAL_GOVERNMENT          = "1o5aJK-MVZo_GiAuWHG_tdzcRChzrZGzQ"

# Housing / Real Estate
HOUSING_MORTGAGE          = "1frWF3ZPaE_hlxWCuLUgVU34acqKE-Wfm"  # 2222 Val Vista/Mortgage

# Health
HEALTH_INS_DOMINICK       = "1Z1jBrkB0FzkLqxdjjPSWFjlXZlGa-3Ik"
HEALTH_INS_DALILA         = "1RV3jhsI9FVkjEuorTH4RfGbXyIZN6xtq"
HEALTH_INS                = "1YXt40ohtUxYlCmeJHOi0jNiJw1ASnLf7"

# Utilities
UTILITIES                 = "1-53lqMfux2JwdyMEIxrwSYvO_47qkV3o"
UTILITIES_ELECTRIC        = "1QeXrMEAbXYXSMEwzqfQ0QNfBaXRB2UEM"
UTILITIES_WATER           = "1e86nwq4eWIpQ6AARBfRS2839XKKTRPmf"

# Career
CAREER_DOMINICK           = "1juga4xG59h3b-htIf1qgpLOaUuHGyxdG"
CAREER_DALILA             = "1obLEhbA9XsLlU-zGZYzRTKE1TuChIMFr"

# Family
FAMILY                    = "1I6Qg58nCXhJPVOst87QYrkei8de32Wf2"
FAMILY_FRANCO             = "19vBwLjTR9mLUoGPZlISNzCJWHkhx01V8"
FAMILY_ALESSANDRA         = "1A0YRxcBF21DLZoPhOZcJ0Chjm0kdn8fE"

# Tax
INCOME_TAX                = "0BzEIAvkM1YZBUWtCZWZkcHhSNE0"
# ─────────────────────────────────────────────────────────────────────────────


def _upper(name):
    return name.upper()


def _has(name, *keywords):
    u = _upper(name)
    return any(kw.upper() in u for kw in keywords)


def _person(name):
    """Return 'dalila', 'dominick', or None based on filename."""
    u = _upper(name)
    if "DALILA" in u:
        return "dalila"
    if "DOMINICK" in u or "DOM" in u:
        return "dominick"
    return None


def determine_destination(file_name: str, category: str):
    """
    Return (folder_id, human_path) for filing, or (None, None) to leave in Raven Scans.
    Business routing is handled before calling this function.
    """
    # ── Auto ──────────────────────────────────────────────────────────────────
    if category == "Auto":
        if _has(file_name, "TRAFFIC", "TRAFFIC_TICKET", "SPEED", "VIOLATION", "MVD"):
            return AUTO_TRAFFIC_VIOLATIONS, "Auto/Traffic Violations"
        if _has(file_name, "SERVICE", "CHAPMAN"):
            return AUTO_JEEP_SERVICE, "Auto/Jeep Grand Wagoneer/Service"
        if _has(file_name, "LOAN", "WELLS_FARGO", "WELLS FARGO", "FINANCING"):
            return AUTO_JEEP_LOAN, "Auto/Jeep Grand Wagoneer/Loan"
        if _has(file_name, "ACADIA", "GMC"):
            return AUTO_ACADIA, "Auto/GMC Acadia"
        return AUTO_JEEP, "Auto/Jeep Grand Wagoneer"

    # ── Legal ──────────────────────────────────────────────────────────────────
    if category == "Legal":
        if _has(file_name, "TRAFFIC", "TRAFFIC_TICKET", "SPEED", "MVD", "VIOLATION"):
            return AUTO_TRAFFIC_VIOLATIONS, "Auto/Traffic Violations"
        if _has(file_name, "CONTRACT", "AGREEMENT", "LEASE"):
            return LEGAL_CONTRACTS, "Legal/Contracts"
        if _has(file_name, "S-CORP", "S_CORP", "SCORP", "FORMATION", "ARTICLES",
                            "OPERATING_AGREEMENT", "REGISTERED_AGENT"):
            return LEGAL_BIZ_FORMATION, "Legal/Business Formation"
        if _has(file_name, "ESTATE", "WILL", "TRUST", "PROBATE", "BENEFICIARY"):
            return LEGAL_ESTATE_PLANNING, "Legal/Estate Planning"
        if _has(file_name, "IRS", "GOVERNMENT", "FEDERAL", "STATE", "NOTICE",
                            "COMPLIANCE", "COURT"):
            return LEGAL_GOVERNMENT, "Legal/Government"
        return LEGAL, "Legal"

    # ── Housing ────────────────────────────────────────────────────────────────
    if category == "Housing":
        return HOUSING_MORTGAGE, "Real Estate/2222 Val Vista/Mortgage"

    # ── Insurance ─────────────────────────────────────────────────────────────
    if category == "Insurance":
        if _has(file_name, "SUREST", "UHC", "UNITEDHEALTHCARE", "UNITED_HEALTHCARE",
                            "EOB", "EXPLANATION_OF_BENEFITS", "HEALTH", "MEDICAL",
                            "DENTAL", "VISION"):
            person = _person(file_name)
            if person == "dalila":
                return HEALTH_INS_DALILA, "Health/Insurance/Dalila"
            if person == "dominick":
                return HEALTH_INS_DOMINICK, "Health/Insurance/Dominick"
            return HEALTH_INS, "Health/Insurance"
        return FINANCE_INSURANCE, "Finance/Insurance"

    # ── Financial ─────────────────────────────────────────────────────────────
    if category == "Financial":
        # Retirement accounts
        if _has(file_name, "401K", "401_K", "IRA", "PCRA", "BREIT", "BLACKSTONE",
                            "TRADE_CONFIRMATION", "TRADE CONFIRMATION",
                            "SCHWAB", "LOCKTON_401", "LOCKTON 401"):
            person = _person(file_name)
            if person == "dalila":
                return FINANCE_INVEST_RETIRE_DAL, "Finance/Investments/Retirement/Dalila"
            if person == "dominick":
                return FINANCE_INVEST_RETIRE_DOM, "Finance/Investments/Retirement/Dominick"
            return FINANCE_INVEST_RETIRE, "Finance/Investments/Retirement"
        # Brokerage / investment accounts
        if _has(file_name, "SCHWAB", "FIDELITY", "MSTR", "NVIDIA", "PROXY",
                            "TREASURY", "MONEY_MARKET", "MONEY MARKET",
                            "INVESTMENT_TRUST", "JPMORGAN_TREASURY", "JPMORGAN TREASURY",
                            "ANNUAL_REPORT", "STATEMENT"):
            return FINANCE_INVEST_BROKERAGE, "Finance/Investments/Brokerage"
        # Payroll / earnings → Career
        if _has(file_name, "EARNINGS_STATEMENT", "EARNINGS STATEMENT", "PAYROLL",
                            "PAYCHECK", "PAY_STUB", "PAY STUB", "PAYSTUB"):
            person = _person(file_name)
            if person == "dalila":
                return CAREER_DALILA, "Career/Dalila"
            if person == "dominick":
                return CAREER_DOMINICK, "Career/Dominick"
        # Bank statements
        if _has(file_name, "BANK_STATEMENT", "BANK STATEMENT", "CHECKING", "SAVINGS"):
            return FINANCE_BANKING_PERSONAL, "Finance/Banking/Personal"
        return FINANCE, "Finance"

    # ── Tax ───────────────────────────────────────────────────────────────────
    if category == "Tax":
        return INCOME_TAX, "Finance/Income Tax"

    # ── Medical ───────────────────────────────────────────────────────────────
    if category == "Medical":
        person = _person(file_name)
        if person == "dalila":
            return HEALTH_INS_DALILA, "Health/Insurance/Dalila"
        if person == "dominick":
            return HEALTH_INS_DOMINICK, "Health/Insurance/Dominick"
        return HEALTH_INS, "Health/Insurance"

    # ── Utilities ─────────────────────────────────────────────────────────────
    if category == "Utilities":
        if _has(file_name, "SRP", "ELECTRIC", "POWER", "ENERGY"):
            return UTILITIES_ELECTRIC, "Utilities/Electric"
        if _has(file_name, "EPCOR", "WATER", "SEWER"):
            return UTILITIES_WATER, "Utilities/Water"
        if _has(file_name, "MESA"):
            # Mesa city bills — route to Electric (SRP is the Mesa electric provider)
            return UTILITIES_ELECTRIC, "Utilities/Electric"
        return None, None  # stay in Raven Scans if no sub-match

    # ── Personal → Family ─────────────────────────────────────────────────────
    if category == "Personal":
        if _has(file_name, "FRANCO"):
            return FAMILY_FRANCO, "Family/Franco"
        if _has(file_name, "ALESSANDRA"):
            return FAMILY_ALESSANDRA, "Family/Alessandra"
        return FAMILY, "Family"

    # Education, Other → no route
    return None, None


def is_freehold(name: str) -> bool:
    return _has(name, "FREEHOLD_LLC", "FREEHOLD LLC", "FREEHOLD")


def is_other_business(name: str) -> bool:
    return _has(name, "EC_BRANDZ", "EC BRANDZ", "ECBRANDZ",
                      "DFW_CAPITAL", "DFW CAPITAL",
                      "WESTBY",
                      "ILLUMINATI_CAPITAL", "ILLUMINATI CAPITAL",
                      "LIMITLESS_AZ", "LIMITLESS AZ",
                      "FOUNTAIN_HILLS", "FOUNTAIN HILLS")


# ── Drive helpers ─────────────────────────────────────────────────────────────

def get_drive_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    token = os.environ.get("GDRIVE_TOKEN")
    if not token:
        raise ValueError("GDRIVE_TOKEN not set")
    creds = Credentials.from_authorized_user_info(json.loads(token))
    return build('drive', 'v3', credentials=creds)


def find_folder_by_name(service, folder_name):
    query = (f"name='{folder_name}' and "
             f"mimeType='application/vnd.google-apps.folder' and trashed=false")
    results = service.files().list(
        q=query, spaces='drive', fields='files(id, name)'
    ).execute()
    folders = results.get('files', [])
    return folders[0]['id'] if folders else None


def list_pdfs_in_folder(service, folder_id):
    query = f"'{folder_id}' in parents and trashed=false and mimeType='application/pdf'"
    all_files, page_token = [], None
    while True:
        res = service.files().list(
            q=query, spaces='drive', pageToken=page_token, pageSize=100,
            fields='nextPageToken, files(id, name, size)'
        ).execute()
        all_files.extend(res.get('files', []))
        page_token = res.get('nextPageToken')
        if not page_token:
            break
    return all_files


def download_file(service, file_id):
    from googleapiclient.http import MediaIoBaseDownload
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return fh.getvalue()


def rename_file(service, file_id, new_name):
    try:
        service.files().update(fileId=file_id, body={'name': new_name}).execute()
        return True
    except Exception as e:
        return str(e)


def move_file(service, file_id, dest_folder_id, current_parent_id):
    try:
        service.files().update(
            fileId=file_id,
            addParents=dest_folder_id,
            removeParents=current_parent_id,
            fields='id, parents'
        ).execute()
        return True
    except Exception as e:
        return str(e)


# ── PDF pre-flight ────────────────────────────────────────────────────────────

class InvalidPDF(Exception):
    pass


def prepare_pdf_for_analysis(pdf_content):
    """
    Return (trimmed_bytes, note).  Trims to the first ANALYSIS_MAX_PAGES pages
    and keeps halving the page count until the payload is under
    ANALYSIS_MAX_BYTES.  Raises InvalidPDF if the file can't be parsed.
    """
    from pypdf import PdfReader, PdfWriter

    # Real PDFs start with %PDF- (possibly after a little junk). Java-serialized
    # blobs, HTML error pages, etc. sometimes get saved with a .pdf extension.
    if b"%PDF-" not in pdf_content[:1024]:
        raise InvalidPDF(f"not a PDF (starts with {pdf_content[:5]!r})")

    try:
        reader = PdfReader(io.BytesIO(pdf_content), strict=False)
        total  = len(reader.pages)
        if total == 0:
            raise InvalidPDF("PDF has no pages")
    except InvalidPDF:
        raise
    except Exception as e:
        raise InvalidPDF(f"unreadable PDF ({type(e).__name__}: {e})")

    if total <= ANALYSIS_MAX_PAGES and len(pdf_content) <= ANALYSIS_MAX_BYTES:
        return pdf_content, ""

    n = min(total, ANALYSIS_MAX_PAGES)
    while True:
        writer = PdfWriter()
        for i in range(n):
            writer.add_page(reader.pages[i])
        buf = io.BytesIO()
        writer.write(buf)
        out = buf.getvalue()
        if len(out) <= ANALYSIS_MAX_BYTES or n == 1:
            note = f"analyzed first {n}/{total} pages, {len(out)/1024/1024:.1f} MB"
            if len(out) > ANALYSIS_MAX_BYTES:
                note += " (still over limit)"
            return out, note
        n = max(1, n // 2)


# ── Claude analysis ───────────────────────────────────────────────────────────

def analyze_document(client, pdf_content, file_name):
    import anthropic

    prompt = f"""Analyze this scanned document and provide:
1. category — one of: {', '.join(CATEGORIES)}
2. new_name — descriptive filename: Category_Description_Person_Date.pdf
   Use underscores, include company/account holder/date (Month_Year)
3. confidence — high, medium, or low
4. is_business — true if document belongs to a business entity (LLC, Corp,
   business account such as Freehold LLC, EC Brandz, DFW Capital); false for personal

Original filename: {file_name}

Respond in JSON only:
{{
    "category": "...",
    "new_name": "Category_Descriptive_Name_Here.pdf",
    "confidence": "high|medium|low",
    "is_business": false
}}"""

    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": base64.b64encode(pdf_content).decode()
                        }
                    },
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        text = response.content[0].text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except Exception as e:
        return {"error": str(e)}


# ── Email ─────────────────────────────────────────────────────────────────────

def send_email(subject, body):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from email.mime.text import MIMEText

    token = os.environ.get("GMAIL_TOKEN")
    if not token:
        print("GMAIL_TOKEN not set — skipping email")
        return

    creds = Credentials.from_authorized_user_info(json.loads(token))
    service = build('gmail', 'v1', credentials=creds)
    msg = MIMEText(body)
    msg["to"] = EMAIL
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    print(f"Email sent: {subject}")


# ── Main function ─────────────────────────────────────────────────────────────

@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("gdrive-token"),
        modal.Secret.from_name("anthropic-key"),
        modal.Secret.from_name("gmail-token"),
    ],
    schedule=modal.Cron("0 9 * * *"),  # Daily 9am UTC (2am MST)
    timeout=3600,
)
def process_scanned_documents():
    import anthropic

    print(f"Starting doc rename+file at {datetime.now().isoformat()}")
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')
    report = [f"Document Rename + File Report — {ts}", "=" * 60]

    renamed, filed, stayed, errors = [], [], [], []

    try:
        svc = get_drive_service()
        raven_id = find_folder_by_name(svc, RAVEN_SCANS_NAME)
        if not raven_id:
            raise ValueError(f"'{RAVEN_SCANS_NAME}' folder not found")

        files = list_pdfs_in_folder(svc, raven_id)
        print(f"Found {len(files)} PDFs in Raven Scans")
        report.append(f"\nFound {len(files)} PDFs in Raven Scans")

        if not files:
            send_email("Doc Automation: nothing to process", "\n".join(report))
            return

        claude = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        report.append("\n--- Details ---")

        for i, file in enumerate(files, 1):
            fid  = file['id']
            name = file['name']
            print(f"\n[{i}/{len(files)}] {name}")

            try:
                # ── Step 1: rename if needed ──────────────────────────────────
                already_named = any(name.startswith(cat + "_") for cat in CATEGORIES)
                category = None
                claude_flagged_business = False

                if already_named:
                    category = name.split("_")[0]
                    print(f"  Already named — category: {category}")
                else:
                    content = download_file(svc, fid)
                    try:
                        content, note = prepare_pdf_for_analysis(content)
                    except InvalidPDF as e:
                        stayed.append(f"{name} (invalid PDF — re-scan or re-export: {e})")
                        report.append(f"  SKIPPED (invalid PDF): {name} — {e}")
                        print(f"  Invalid PDF: {e}")
                        continue
                    if note:
                        report.append(f"  NOTE: {name} — {note}")
                        print(f"  {note}")
                    result  = analyze_document(claude, content, name)

                    if "error" in result and "PDF specified was not valid" in result["error"]:
                        stayed.append(f"{name} (invalid PDF — re-scan or re-export)")
                        report.append(f"  SKIPPED (invalid PDF): {name} — rejected by Anthropic")
                        continue
                    if "error" in result:
                        errors.append(f"{name}: {result['error']}")
                        report.append(f"  ERROR (analysis): {name} — {result['error']}")
                        continue

                    new_name   = result['new_name']
                    category   = result.get('category', new_name.split('_')[0])
                    confidence = result.get('confidence', '?')
                    claude_flagged_business = result.get('is_business', False)

                    ok = rename_file(svc, fid, new_name)
                    if ok is not True:
                        errors.append(f"{name}: rename failed — {ok}")
                        report.append(f"  FAILED rename: {name} — {ok}")
                        continue

                    renamed.append(f"{name} → {new_name} ({confidence})")
                    report.append(f"  RENAMED: {name} → {new_name} ({confidence})")
                    name = new_name

                # ── Step 2: route to destination ──────────────────────────────
                if is_freehold(name):
                    dest_id, dest_path = BUSINESS_FREEHOLD, "Business/Freehold LLC"
                elif is_other_business(name) or claude_flagged_business:
                    dest_id, dest_path = LLC_FILES, "Raven Scans/LLC Files"
                else:
                    dest_id, dest_path = determine_destination(name, category)

                # ── Step 3: move ──────────────────────────────────────────────
                if dest_id:
                    ok = move_file(svc, fid, dest_id, raven_id)
                    if ok is True:
                        filed.append(f"{name} → {dest_path}")
                        report.append(f"  FILED → {dest_path}")
                        print(f"  Filed → {dest_path}")
                    else:
                        errors.append(f"{name}: move failed — {ok}")
                        report.append(f"  FAILED move: {name} — {ok}")
                else:
                    stayed.append(name)
                    report.append(f"  STAYED (no route): {name}")
                    print(f"  No route — stays in Raven Scans")

            except Exception as e:
                errors.append(f"{name}: {e}")
                report.append(f"  ERROR: {name} — {e}")

    except Exception as e:
        errors.append(f"Critical: {e}")
        report.append(f"\nCRITICAL ERROR: {e}")

    # ── Summary ───────────────────────────────────────────────────────────────
    report += [
        "\n" + "=" * 60, "SUMMARY",
        f"  Renamed:  {len(renamed)}",
        f"  Filed:    {len(filed)}",
        f"  Stayed:   {len(stayed)}",
        f"  Errors:   {len(errors)}",
    ]
    if stayed:
        report.append("\nSTAYED (no matching folder):")
        report += [f"  - {f}" for f in stayed]
    if errors:
        report.append("\nERRORS:")
        report += [f"  - {e}" for e in errors]

    total = len(filed)
    if errors:
        subject = f"Doc Automation: {len(renamed)} renamed, {total} filed, {len(errors)} errors"
    elif renamed or total:
        subject = f"Doc Automation: {len(renamed)} renamed, {total} filed"
    else:
        subject = "Doc Automation: nothing to process"

    body = "\n".join(report)
    print(f"\n{body}")
    send_email(subject, body)

    return {"renamed": len(renamed), "filed": total, "stayed": len(stayed), "errors": len(errors)}


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("gdrive-token"),
        modal.Secret.from_name("anthropic-key"),
        modal.Secret.from_name("gmail-token"),
    ],
    timeout=3600,
)
def run_now():
    """Manual trigger."""
    return process_scanned_documents.local()


@app.function(image=image, secrets=[modal.Secret.from_name("gmail-token")])
def test_email():
    send_email("Doc Automation — Test", "Setup is working correctly!")
    return "Test email sent"


@app.local_entrypoint()
def main():
    print("Running document rename + file process...")
    result = run_now.remote()
    print(f"Result: {result}")
