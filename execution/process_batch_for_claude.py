"""
Process documents in batches and output information for Claude to analyze
This script helps organize the analysis workflow
"""

import json
from pathlib import Path

# Load metadata
metadata_file = Path('.tmp/drive_files_list.json')
with open(metadata_file, 'r') as f:
    files_metadata = json.load(f)

# Load existing mapping
mapping_file = Path('.tmp/rename_mapping.json')
with open(mapping_file, 'r') as f:
    rename_mapping = json.load(f)

# Find files that haven't been mapped yet
already_mapped_ids = set(rename_mapping.keys())
unmapped_files = [f for f in files_metadata if f['id'] not in already_mapped_ids]

print(f"Total files: {len(files_metadata)}")
print(f"Already mapped: {len(already_mapped_ids)}")
print(f"Remaining to process: {len(unmapped_files)}")
print("\n" + "="*80)

# Output unmapped files in batches
batch_size = 20
for i in range(0, len(unmapped_files), batch_size):
    batch = unmapped_files[i:i+batch_size]
    batch_num = (i // batch_size) + 1

    print(f"\nBatch {batch_num} ({len(batch)} files):")
    print("-"*80)

    for file_info in batch:
        print(f"File ID: {file_info['id']}")
        print(f"Name: {file_info['name']}")
        print(f"Path: {file_info['local_path']}")
        print(f"Size: {file_info.get('size', 'N/A')} bytes")
        print()
