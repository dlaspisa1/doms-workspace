"""
Analyze scanned documents and generate rename mappings
This script helps create the rename mapping file that Claude will populate
"""

import json
from pathlib import Path

# Load metadata
metadata_file = Path('.tmp/drive_files_list.json')
with open(metadata_file, 'r') as f:
    files_metadata = json.load(f)

# Initialize rename mapping
rename_mapping = {}

print(f"Total files to process: {len(files_metadata)}")
print(f"\nStarting batch processing...")
print("=" * 80)

# Files that already have good names (keep or improve slightly)
already_named = [
    "Googipet Insurance Application .pdf",
    "Christina Robledo rent letter and rent request.pdf",
    "Rent Increase Request revised.pdf",
    "Req for rent inc.pdf",
    "Naomi Rent Increase request.pdf",
    "Client Service Agreement Waltlaw PLC.pdf",
    "5 day noitce to pay or quit Dangelo Juniper.pdf",
    "Product recall or market withdrawl SOP.pdf",
    "Beneficiary Designation Form.pdf",
    "Dalila 401k Rolllover Docs.pdf",
    "EC Brandz LLC Ingardona Agreement .pdf",
    "Ec brandz tpt 2025.pdf",
    "DE Registration letter for .pdf",
    "Req for Tenancy Approval.pdf",
    "Letter of Authorization.pdf",
    "Beneficial Owners.pdf"
]

# Process files and create mapping structure
batch_num = 1
batch_size = 10

for i in range(0, len(files_metadata), batch_size):
    batch = files_metadata[i:i+batch_size]
    print(f"\nBatch {batch_num} ({len(batch)} files):")
    print("-" * 80)

    for file_info in batch:
        file_id = file_info['id']
        old_name = file_info['name']
        local_path = file_info['local_path']

        # Skip already well-named files
        if old_name in already_named:
            print(f"  ✓ {old_name} (keeping name)")
            continue

        # Placeholder for Claude to fill in
        print(f"  📄 {old_name}")
        print(f"     Path: {local_path}")
        print(f"     ID: {file_id}")

        # Add to mapping with placeholder
        rename_mapping[file_id] = {
            "old_name": old_name,
            "new_name": "NEEDS_ANALYSIS",  # Claude will fill this in
            "category": "Unknown",
            "confidence": "pending",
            "local_path": local_path
        }

    batch_num += 1

# Save the mapping template
output_file = Path('.tmp/rename_mapping.json')
with open(output_file, 'w') as f:
    json.dump(rename_mapping, f, indent=2)

print(f"\n{'=' * 80}")
print(f"Created mapping template at: {output_file}")
print(f"Files requiring analysis: {len(rename_mapping)}")
print(f"\nReady for Claude to analyze and populate intelligent names!")
