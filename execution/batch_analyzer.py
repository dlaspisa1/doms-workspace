"""
Batch document analyzer - helps Claude process files systematically
Reads metadata and outputs file info for analysis
"""

import json
from pathlib import Path

# Load files metadata
metadata_file = Path('.tmp/drive_files_list.json')
with open(metadata_file, 'r') as f:
    all_files = json.load(f)

# Load existing rename mapping
mapping_file = Path('.tmp/rename_mapping.json')
with open(mapping_file, 'r') as f:
    current_mapping = json.load(f)

# Track progress
total = len(all_files)
mapped = len(current_mapping)
remaining = total - mapped

print(f"Progress: {mapped}/{total} files mapped ({remaining} remaining)")
print(f"Completion: {(mapped/total)*100:.1f}%")

# Show next batch to process
unmapped = [f for f in all_files if f['id'] not in current_mapping]
batch_size = 10

if unmapped:
    print(f"\nNext batch of {min(batch_size, len(unmapped))} files to process:")
    print("="*80)
    for i, file in enumerate(unmapped[:batch_size]):
        print(f"\n{i+1}. File ID: {file['id']}")
        print(f"   Name: {file['name']}")
        print(f"   Path: {file['local_path']}")
