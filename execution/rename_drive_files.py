"""
Rename Files in Google Drive
Applies renames based on mapping file generated from analysis
"""

import os
import sys
import json
from pathlib import Path
from gdrive_auth import get_drive_service

# Unbuffered output for real-time progress
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

def rename_file(service, file_id, new_name):
    """Rename a file in Google Drive"""
    try:
        file_metadata = {'name': new_name}
        updated_file = service.files().update(
            fileId=file_id,
            body=file_metadata,
            fields='id, name'
        ).execute()
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def main(mapping_file, dry_run=False):
    """Main execution"""
    # Load mapping file
    mapping_path = Path(mapping_file)
    if not mapping_path.exists():
        print(f"✗ Mapping file not found: {mapping_file}")
        return

    with open(mapping_path, 'r') as f:
        rename_mapping = json.load(f)

    if not rename_mapping:
        print("✗ Mapping file is empty")
        return

    print(f"Loaded {len(rename_mapping)} rename operations")

    if dry_run:
        print("\n=== DRY RUN MODE - No changes will be made ===\n")

    # Connect to Drive
    print("Connecting to Google Drive...")
    service = get_drive_service()
    print("✓ Connected")

    # Execute renames
    success_count = 0
    skip_count = 0

    total = len(rename_mapping)
    for i, (file_id, rename_info) in enumerate(rename_mapping.items(), 1):
        old_name = rename_info['old_name']
        new_name = rename_info['new_name']
        confidence = rename_info.get('confidence', 'unknown')

        print(f"\n[{i}/{total}] {old_name}")
        print(f"  → {new_name}")
        print(f"  Confidence: {confidence}", flush=True)

        if dry_run:
            print("  [DRY RUN - would rename]", flush=True)
            success_count += 1
        else:
            if rename_file(service, file_id, new_name):
                print("  ✓ Renamed", flush=True)
                success_count += 1
            else:
                print("  ✗ Failed to rename", flush=True)
                skip_count += 1

    print(f"\n{'='*50}")
    print(f"Summary:")
    print(f"  ✓ Successful: {success_count}")
    if skip_count > 0:
        print(f"  ✗ Failed: {skip_count}")

    if dry_run:
        print(f"\nThis was a dry run. To apply changes, run:")
        print(f"  python {sys.argv[0]} {mapping_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python rename_drive_files.py <mapping_file.json> [--dry-run]")
        sys.exit(1)

    mapping_file = sys.argv[1]
    dry_run = '--dry-run' in sys.argv

    main(mapping_file, dry_run)
