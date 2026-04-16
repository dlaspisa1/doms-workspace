"""
Batch Document Rename - Modal (Gemini)

Processes all 'Misc_Scanned Document' files in the "Document Scans" subfolder
of "Raven Scans" Google Drive folder. Uses Gemini for analysis.

Usage:
  modal run execution/modal_doc_rename_batch.py
"""

import modal
import json
import os
import io
import base64
from datetime import datetime

app = modal.App("doc-rename-batch")

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "google-api-python-client",
    "google-auth",
    "google-genai",
)

RAVEN_SCANS_FOLDER_ID = "1YuR7FCqlDJiaZxRU4MR_cZRvr0m_Ou0r"
DOC_SCANS_FOLDER_ID = "1bIFg6P1kGjZJ8zlZLQs8GMo2iL2GB3OH"
EMAIL = "dlaspisa1@gmail.com"

CATEGORIES = [
    "Financial", "Medical", "Legal", "Utilities", "Insurance",
    "Tax", "Personal", "Education", "Housing", "Auto", "Other"
]


def send_email(subject, body):
    """Send email report via Gmail."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from email.mime.text import MIMEText

    token = os.environ.get("GMAIL_TOKEN")
    if not token:
        print("GMAIL_TOKEN not set - skipping email")
        return

    creds = Credentials.from_authorized_user_info(json.loads(token))
    service = build('gmail', 'v1', credentials=creds)

    msg = MIMEText(body)
    msg["to"] = EMAIL
    msg["subject"] = subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    print(f"Email sent: {subject}")


def get_drive_service():
    """Get Google Drive service from token."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    token = os.environ.get("GDRIVE_TOKEN")
    if not token:
        raise ValueError("GDRIVE_TOKEN not set")

    creds = Credentials.from_authorized_user_info(json.loads(token))
    return build('drive', 'v3', credentials=creds)


def list_misc_files(service, folder_id):
    """List all 'Misc_Scanned Document' PDF files in folder."""
    query = (
        f"'{folder_id}' in parents and trashed=false "
        f"and mimeType='application/pdf' "
        f"and name contains 'Misc_Scanned Document'"
    )
    all_files = []
    page_token = None

    while True:
        results = service.files().list(
            q=query, spaces='drive', pageToken=page_token, pageSize=100,
            fields='nextPageToken, files(id, name, mimeType, size)'
        ).execute()
        all_files.extend(results.get('files', []))
        page_token = results.get('nextPageToken')
        if not page_token:
            break

    return all_files


def download_file(service, file_id):
    """Download file content from Google Drive."""
    from googleapiclient.http import MediaIoBaseDownload

    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    return fh.getvalue()


def analyze_document_gemini(client, pdf_content, file_name):
    """Analyze a document using Gemini's vision capabilities."""
    import time

    try:
        prompt = f"""Analyze this scanned document and provide:
1. The document category (one of: {', '.join(CATEGORIES)})
2. A descriptive filename in the format: Category_description.pdf
   - Keep it concise but informative
   - Include relevant dates (Month Year format like "Jan 2025")
   - Include key identifiers (company names, account holders, property addresses)
   - Use underscores instead of spaces
3. Your confidence level (high, medium, low)

Original filename: {file_name}

Respond in JSON format only:
{{
    "category": "Category",
    "new_name": "Category_Descriptive_Name_Here.pdf",
    "confidence": "high|medium|low"
}}"""

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "application/pdf",
                                "data": base64.b64encode(pdf_content).decode()
                            }
                        },
                        {"text": prompt}
                    ]
                }
            ]
        )

        response_text = response.text
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        return json.loads(response_text.strip())

    except Exception as e:
        error_str = str(e)
        # Handle rate limiting
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
            print(f"  Rate limited, waiting 30s...")
            time.sleep(30)
            return {"error": f"Rate limited: {error_str}"}
        return {"error": error_str}


def rename_file(service, file_id, new_name):
    """Rename a file in Google Drive."""
    try:
        service.files().update(fileId=file_id, body={'name': new_name}).execute()
        return True
    except Exception as e:
        return str(e)


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("gdrive-token"),
        modal.Secret.from_name("gemini-key"),
        modal.Secret.from_name("gmail-token"),
    ],
    timeout=3600,  # 60 min for large batch
)
def process_document_scans():
    """Process all Misc_Scanned Document files in Document Scans subfolder."""
    from google import genai
    import time

    print(f"Starting batch document rename at {datetime.now().isoformat()}")
    report_lines = [f"Document Rename Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
    report_lines.append("=" * 50)

    renamed = []
    errors = []
    skipped = []

    try:
        # Connect to services
        print("Connecting to Google Drive...")
        drive_service = get_drive_service()

        print("Initializing Gemini...")
        gemini_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_key:
            raise ValueError("GEMINI_API_KEY not set")
        client = genai.Client(api_key=gemini_key)

        # List misc files in Document Scans subfolder
        files = list_misc_files(drive_service, DOC_SCANS_FOLDER_ID)
        print(f"Found {len(files)} 'Misc_Scanned Document' files to process")
        report_lines.append(f"\nFound {len(files)} files to process in 'Document Scans'")

        if not files:
            report_lines.append("\nNo files to process.")
            send_email("Doc Rename Batch: No files to process", "\n".join(report_lines))
            return {"renamed": 0, "errors": 0}

        # Process each file
        for i, file in enumerate(files, 1):
            file_id = file['id']
            file_name = file['name']
            print(f"\n[{i}/{len(files)}] Processing: {file_name}")

            try:
                # Download
                content = download_file(drive_service, file_id)

                # Analyze with Gemini
                result = analyze_document_gemini(client, content, file_name)

                if "error" in result:
                    errors.append(f"{file_name}: {result['error']}")
                    report_lines.append(f"ERROR: {file_name} -> {result['error']}")
                    continue

                new_name = result['new_name']
                confidence = result.get('confidence', 'unknown')

                # Rename in Drive
                rename_result = rename_file(drive_service, file_id, new_name)

                if rename_result is True:
                    renamed.append(f"{file_name} -> {new_name}")
                    report_lines.append(f"RENAMED: {file_name}")
                    report_lines.append(f"  -> {new_name} ({confidence})")
                    print(f"  -> {new_name} ({confidence})")
                else:
                    errors.append(f"{file_name}: Rename failed - {rename_result}")
                    report_lines.append(f"FAILED: {file_name} -> {rename_result}")

                # Small delay to avoid rate limits
                time.sleep(1)

            except Exception as e:
                errors.append(f"{file_name}: {str(e)}")
                report_lines.append(f"ERROR: {file_name} -> {str(e)}")

    except Exception as e:
        errors.append(f"Critical error: {str(e)}")
        report_lines.append(f"\nCRITICAL ERROR: {str(e)}")

    # Summary
    report_lines.append("\n" + "=" * 50)
    report_lines.append("SUMMARY")
    report_lines.append(f"  Renamed: {len(renamed)}")
    report_lines.append(f"  Errors: {len(errors)}")

    if errors:
        report_lines.append("\nERRORS:")
        for err in errors:
            report_lines.append(f"  - {err}")

    report_body = "\n".join(report_lines)
    print(f"\n{report_body}")

    # Send email report
    subject = f"Doc Rename Batch: {len(renamed)} renamed, {len(errors)} errors"
    send_email(subject, report_body)

    return {"renamed": len(renamed), "errors": len(errors)}


@app.local_entrypoint()
def main():
    """Local entrypoint."""
    print("Running batch document rename...")
    result = process_document_scans.remote()
    print(f"Result: {result}")
