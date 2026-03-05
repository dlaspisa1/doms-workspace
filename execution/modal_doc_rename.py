"""
Document Rename Automation - Modal

Automatically renames scanned documents in Google Drive "Raven Scans" folder.
Runs weekly, analyzes PDFs with Claude, renames in Drive, sends email report.

Setup:
  modal secret create gdrive-token GDRIVE_TOKEN="$(cat token_drive.json)"
  modal secret create gmail-token GMAIL_TOKEN="$(cat token.json)"
  modal secret create anthropic-key ANTHROPIC_API_KEY="your-anthropic-key"
  modal deploy execution/modal_doc_rename.py
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
)

FOLDER_NAME = "Raven Scans"
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


def find_folder_by_name(service, folder_name):
    """Find folder ID by name."""
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    folders = results.get('files', [])
    return folders[0]['id'] if folders else None


def list_files_in_folder(service, folder_id):
    """List all PDF files in a folder."""
    query = f"'{folder_id}' in parents and trashed=false and mimeType='application/pdf'"
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


def analyze_document(client, pdf_content, file_name):
    """Analyze a document using Claude's vision capabilities."""
    import anthropic

    try:
        prompt = f"""Analyze this scanned document and provide:
1. The document category (one of: {', '.join(CATEGORIES)})
2. A descriptive filename in the format: Category_description.pdf
   - Keep it concise but informative
   - Include relevant dates (Month Year format like "Jan 2025")
   - Include key identifiers (company names, account holders)
   - Use underscores instead of spaces
3. Your confidence level (high, medium, low)

Original filename: {file_name}

Respond in JSON format only:
{{
    "category": "Category",
    "new_name": "Category_Descriptive_Name_Here.pdf",
    "confidence": "high|medium|low"
}}"""

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
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

        response_text = response.content[0].text
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        return json.loads(response_text.strip())

    except Exception as e:
        return {"error": str(e)}


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
        modal.Secret.from_name("anthropic-key"),
        modal.Secret.from_name("gmail-token"),
    ],
    schedule=modal.Cron("0 9 * * 0"),  # Weekly: Sunday 9am UTC
    timeout=1800,  # 30 min timeout for large batches
)
def process_scanned_documents():
    """Main scheduled function - process and rename scanned documents."""
    import anthropic

    print(f"Starting document rename automation at {datetime.now().isoformat()}")
    report_lines = [f"Document Rename Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
    report_lines.append("=" * 50)

    renamed = []
    errors = []
    skipped = []

    try:
        # Connect to Google Drive
        print("Connecting to Google Drive...")
        drive_service = get_drive_service()

        # Find folder
        folder_id = find_folder_by_name(drive_service, FOLDER_NAME)
        if not folder_id:
            raise ValueError(f"Folder '{FOLDER_NAME}' not found")

        print(f"Found folder: {FOLDER_NAME}")

        # List files
        files = list_files_in_folder(drive_service, folder_id)
        print(f"Found {len(files)} PDF files")
        report_lines.append(f"\nFound {len(files)} PDF files in '{FOLDER_NAME}'")

        if not files:
            report_lines.append("\nNo files to process.")
            send_email("Doc Rename: No files to process", "\n".join(report_lines))
            return

        # Skip files that already look renamed (have Category_ prefix)
        files_to_process = []
        for f in files:
            name = f['name']
            # Check if already categorized
            if any(name.startswith(cat + "_") for cat in CATEGORIES):
                skipped.append(name)
            else:
                files_to_process.append(f)

        print(f"Skipping {len(skipped)} already-renamed files")
        print(f"Processing {len(files_to_process)} new files")
        report_lines.append(f"Skipping {len(skipped)} already-renamed files")
        report_lines.append(f"Processing {len(files_to_process)} new files")

        if not files_to_process:
            report_lines.append("\nAll files already processed.")
            send_email("Doc Rename: All files up to date", "\n".join(report_lines))
            return

        # Initialize Claude
        print("Initializing Claude...")
        claude_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        # Process each file
        report_lines.append("\n--- Processing Details ---")

        for i, file in enumerate(files_to_process, 1):
            file_id = file['id']
            file_name = file['name']
            print(f"\n[{i}/{len(files_to_process)}] Processing: {file_name}")

            try:
                # Download
                print(f"  Downloading...")
                content = download_file(drive_service, file_id)

                # Analyze
                print(f"  Analyzing with Claude...")
                result = analyze_document(claude_client, content, file_name)

                if "error" in result:
                    errors.append(f"{file_name}: {result['error']}")
                    report_lines.append(f"ERROR: {file_name}")
                    report_lines.append(f"  -> {result['error']}")
                    continue

                new_name = result['new_name']
                confidence = result.get('confidence', 'unknown')

                # Rename
                print(f"  Renaming to: {new_name}")
                rename_result = rename_file(drive_service, file_id, new_name)

                if rename_result is True:
                    renamed.append(f"{file_name} -> {new_name} ({confidence})")
                    report_lines.append(f"RENAMED: {file_name}")
                    report_lines.append(f"  -> {new_name} ({confidence})")
                    print(f"  Success!")
                else:
                    errors.append(f"{file_name}: Rename failed - {rename_result}")
                    report_lines.append(f"FAILED: {file_name}")
                    report_lines.append(f"  -> {rename_result}")

            except Exception as e:
                errors.append(f"{file_name}: {str(e)}")
                report_lines.append(f"ERROR: {file_name}")
                report_lines.append(f"  -> {str(e)}")

    except Exception as e:
        errors.append(f"Critical error: {str(e)}")
        report_lines.append(f"\nCRITICAL ERROR: {str(e)}")

    # Summary
    report_lines.append("\n" + "=" * 50)
    report_lines.append("SUMMARY")
    report_lines.append(f"  Renamed: {len(renamed)}")
    report_lines.append(f"  Skipped (already done): {len(skipped)}")
    report_lines.append(f"  Errors: {len(errors)}")

    if errors:
        report_lines.append("\nERRORS:")
        for err in errors:
            report_lines.append(f"  - {err}")

    # Send email report
    if errors:
        subject = f"Doc Rename: {len(renamed)} renamed, {len(errors)} errors"
    elif renamed:
        subject = f"Doc Rename: {len(renamed)} files renamed successfully"
    else:
        subject = "Doc Rename: No new files to process"

    report_body = "\n".join(report_lines)
    print(f"\n{report_body}")
    send_email(subject, report_body)

    return {
        "renamed": len(renamed),
        "skipped": len(skipped),
        "errors": len(errors)
    }


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("gdrive-token"),
        modal.Secret.from_name("anthropic-key"),
        modal.Secret.from_name("gmail-token"),
    ],
    timeout=1800,
)
def run_now():
    """Manual trigger - run the document rename process immediately."""
    return process_scanned_documents.local()


@app.function(image=image, secrets=[modal.Secret.from_name("gmail-token")])
def test_email():
    """Send a test email to verify setup."""
    send_email(
        "Doc Rename Automation - Test",
        "This is a test email from the document rename automation.\n\nSetup is working correctly!"
    )
    return "Test email sent"


@app.local_entrypoint()
def main():
    """Local entrypoint for testing."""
    print("Running document rename process...")
    result = run_now.remote()
    print(f"Result: {result}")
