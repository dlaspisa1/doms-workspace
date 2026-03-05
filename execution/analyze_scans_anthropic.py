"""
Automated Document Analysis using Anthropic API
Analyzes scanned PDFs and generates rename mappings using Claude's vision capabilities
"""

import os
import sys
import json
import base64
import anthropic
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Categories for document classification
CATEGORIES = [
    "Financial",  # Bank statements, invoices, receipts
    "Medical",    # Health records, prescriptions, insurance
    "Legal",      # Contracts, agreements, official documents
    "Utilities",  # Electric, water, internet bills
    "Insurance",  # Policy documents, claims
    "Tax",        # Tax returns, W2s, 1099s
    "Personal",   # IDs, certificates, personal records
    "Education",  # Transcripts, certificates, course materials
    "Housing",    # Lease, mortgage, property documents
    "Auto",       # Registration, insurance, maintenance records
    "Other"       # Miscellaneous documents
]

def get_anthropic_client():
    """Initialize Anthropic client"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
    return anthropic.Anthropic(api_key=api_key)

def encode_pdf_to_base64(file_path):
    """Read and encode PDF file to base64"""
    with open(file_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")

def analyze_document(client, file_path, file_name):
    """
    Analyze a document using Claude's vision capabilities
    Returns: dict with category, new_name, confidence
    """
    try:
        # Encode PDF to base64
        pdf_base64 = encode_pdf_to_base64(file_path)

        # Create the analysis prompt
        prompt = f"""Analyze this scanned document and provide:
1. The document category (one of: {', '.join(CATEGORIES)})
2. A descriptive filename in the format: Category_description.pdf
   - Keep it concise but informative
   - Include relevant dates (Month Year format like "Jan 2025")
   - Include key identifiers (company names, account holders, property addresses)
3. Your confidence level (high, medium, low)

Original filename: {file_name}

Respond in JSON format only:
{{
    "category": "Category",
    "new_name": "Category_Descriptive Name Here.pdf",
    "confidence": "high|medium|low"
}}"""

        # Call Claude API with vision
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )

        # Parse the response
        response_text = message.content[0].text

        # Extract JSON from response (handle potential markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        result = json.loads(response_text.strip())
        return result

    except Exception as e:
        print(f"  Error analyzing {file_name}: {e}")
        return None

def load_existing_mapping(mapping_path):
    """Load existing rename mapping if it exists"""
    if os.path.exists(mapping_path):
        with open(mapping_path, 'r') as f:
            return json.load(f)
    return {}

def save_mapping(mapping, mapping_path):
    """Save rename mapping to file"""
    with open(mapping_path, 'w') as f:
        json.dump(mapping, f, indent=2)

def get_file_id_from_path(file_path):
    """Extract Google Drive file ID from local filename"""
    # Files are named: {file_id}_{original_name}.pdf
    filename = os.path.basename(file_path)
    # Split on first underscore to get file ID
    parts = filename.split('_', 1)
    if len(parts) >= 1:
        return parts[0]
    return None

def main(scans_dir=None, mapping_path=None, skip_existing=True):
    """
    Main execution

    Args:
        scans_dir: Directory containing downloaded scans (default: .tmp/scanned_docs)
        mapping_path: Path to rename mapping JSON (default: .tmp/rename_mapping.json)
        skip_existing: Skip files already in the mapping (default: True)
    """
    # Set defaults
    if scans_dir is None:
        scans_dir = Path('.tmp/scanned_docs')
    else:
        scans_dir = Path(scans_dir)

    if mapping_path is None:
        mapping_path = Path('.tmp/rename_mapping.json')
    else:
        mapping_path = Path(mapping_path)

    # Initialize Anthropic client
    print("Initializing Anthropic client...")
    client = get_anthropic_client()

    # Load existing mapping
    print("Loading existing mapping...")
    mapping = load_existing_mapping(mapping_path)
    print(f"Found {len(mapping)} existing entries")

    # Get list of PDF files
    pdf_files = list(scans_dir.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files in {scans_dir}")

    # Process each file
    processed = 0
    skipped = 0
    errors = 0

    for pdf_path in pdf_files:
        file_id = get_file_id_from_path(pdf_path)

        if not file_id:
            print(f"Could not extract file ID from: {pdf_path.name}")
            errors += 1
            continue

        # Skip if already in mapping
        if skip_existing and file_id in mapping:
            skipped += 1
            continue

        # Get original filename (after the file_id prefix)
        original_name = pdf_path.name.split('_', 1)[1] if '_' in pdf_path.name else pdf_path.name

        print(f"\nAnalyzing: {original_name}")

        # Analyze with Claude
        result = analyze_document(client, pdf_path, original_name)

        if result:
            mapping[file_id] = {
                "old_name": original_name,
                "new_name": result["new_name"],
                "category": result["category"],
                "confidence": result["confidence"]
            }
            processed += 1
            print(f"  → {result['new_name']} ({result['confidence']})")

            # Save after each successful analysis (in case of interruption)
            save_mapping(mapping, mapping_path)
        else:
            errors += 1

    # Final save
    save_mapping(mapping, mapping_path)

    print(f"\n{'='*50}")
    print(f"Analysis complete!")
    print(f"  Processed: {processed}")
    print(f"  Skipped (existing): {skipped}")
    print(f"  Errors: {errors}")
    print(f"  Total in mapping: {len(mapping)}")
    print(f"\nMapping saved to: {mapping_path}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analyze scanned documents using Anthropic API")
    parser.add_argument("--scans-dir", help="Directory containing scanned PDFs")
    parser.add_argument("--mapping", help="Path to rename mapping JSON")
    parser.add_argument("--reanalyze", action="store_true", help="Re-analyze files already in mapping")

    args = parser.parse_args()

    main(
        scans_dir=args.scans_dir,
        mapping_path=args.mapping,
        skip_existing=not args.reanalyze
    )
