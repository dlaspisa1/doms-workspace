"""
List and Download Files from Google Drive
Fetches files from a specified folder for analysis
"""

import os
import sys
import json
from pathlib import Path
from gdrive_auth import get_drive_service
from googleapiclient.http import MediaIoBaseDownload
import io

def find_folder_by_name(service, folder_name):
    """Find folder ID by name"""
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(
        q=query,
        spaces='drive',
        fields='files(id, name, owners)'
    ).execute()

    folders = results.get('files', [])
    if not folders:
        return None

    # Return first matching folder
    return folders[0]['id']

def list_files_in_folder(service, folder_id):
    """List all files in a folder"""
    query = f"'{folder_id}' in parents and trashed=false"

    all_files = []
    page_token = None

    while True:
        results = service.files().list(
            q=query,
            spaces='drive',
            fields='nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime)',
            pageToken=page_token,
            pageSize=100
        ).execute()

        files = results.get('files', [])
        all_files.extend(files)

        page_token = results.get('nextPageToken')
        if not page_token:
            break

    return all_files

def download_file(service, file_id, file_name, output_dir, use_id_prefix=False):
    """Download a file from Google Drive"""
    # Use file ID prefix to ensure unique filenames
    if use_id_prefix:
        safe_name = f"{file_id}_{file_name}"
    else:
        safe_name = file_name
    output_path = Path(output_dir) / safe_name

    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"  Download {int(status.progress() * 100)}%: {file_name}")

        # Write to file
        with open(output_path, 'wb') as f:
            f.write(fh.getvalue())

        return str(output_path)

    except Exception as e:
        print(f"  ✗ Failed to download {file_name}: {e}")
        return None

def main(folder_name):
    """Main execution"""
    print(f"Connecting to Google Drive...")
    service = get_drive_service()

    print(f"Finding folder: '{folder_name}'...")
    folder_id = find_folder_by_name(service, folder_name)

    if not folder_id:
        print(f"✗ Folder '{folder_name}' not found")
        return

    print(f"✓ Found folder (ID: {folder_id})")

    print(f"Listing files in folder...")
    files = list_files_in_folder(service, folder_id)

    if not files:
        print("✗ No files found in folder")
        return

    print(f"✓ Found {len(files)} files")

    # Create output directories
    tmp_dir = Path('.tmp')
    tmp_dir.mkdir(exist_ok=True)

    download_dir = tmp_dir / 'scanned_docs'
    download_dir.mkdir(exist_ok=True)

    # Download files and collect metadata
    file_metadata = []

    for file in files:
        print(f"\nProcessing: {file['name']}")
        print(f"  Type: {file['mimeType']}")
        print(f"  Size: {file.get('size', 'N/A')} bytes")

        # Download file (use ID prefix to avoid overwriting duplicates)
        local_path = download_file(service, file['id'], file['name'], download_dir, use_id_prefix=True)

        if local_path:
            file_metadata.append({
                'id': file['id'],
                'name': file['name'],
                'mimeType': file['mimeType'],
                'size': file.get('size'),
                'local_path': local_path,
                'created': file.get('createdTime'),
                'modified': file.get('modifiedTime')
            })

    # Save metadata
    metadata_path = tmp_dir / 'drive_files_list.json'
    with open(metadata_path, 'w') as f:
        json.dump(file_metadata, f, indent=2)

    print(f"\n✓ Downloaded {len(file_metadata)} files to {download_dir}")
    print(f"✓ Metadata saved to {metadata_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python list_drive_files.py 'Folder Name'")
        sys.exit(1)

    folder_name = sys.argv[1]
    main(folder_name)
