#!/usr/bin/env python3
"""
Script to populate document metadata in the storage system from a JSON file
"""

import argparse
import json
from pathlib import Path

from fema_agent.storage import DeclarationStorage

def update_storage_from_json(
        json_path,
        storage_dir: str = "declarations",
        ground_truth: bool = False,
        dry_run: bool = False):
    """
    Update the storage system with metadata from a JSON file
    
    Args:
        json_path (str): Path to the JSON file with parsed data
        storage_dir (str): Base directory for the storage system
        dry_run (bool): If True, just print what would be updated without making changes
        
    Returns:
        int: Number of documents updated
    """
    # Initialize storage
    storage = DeclarationStorage(storage_dir)
    
    # Load the JSON data
    with open(json_path, "r") as f:
        data = json.load(f)
    
    # Process each document
    updated_count = 0
    for doc_data in data:
        doc_id = doc_data.get("uuid")
        if not doc_id:
            print(f"Warning: Document missing UUID, skipping")
            continue
            
        print(f"Processing document: {doc_id}")
        
        # Create a copy of the document data excluding storage-specific fields
        # that are already managed by the storage system
        metadata = {}
        excluded_fields = ["uuid", "file_path", "original_filename", "page_count", 
                          "import_date", "pages"]
        
        # Also exclude page_N keys which are managed by the storage system
        page_prefixes = ["page_"]
        
        for key, value in doc_data.items():
            # Skip excluded fields and page-specific paths
            if key in excluded_fields or any(key.startswith(prefix) for prefix in page_prefixes):
                continue
                
            metadata[key] = value

        # Add in flag to indicate whether the fields are to be considered ground-truth
        metadata['ground_truth'] = ground_truth

        if dry_run:
            print(f"  Would update document {doc_id} with {len(metadata)} metadata fields")
            # for key, value in sorted(metadata.items()):
            #     print(f"    {key}: {value}")
        else:
            try:
                # Update the document metadata
                storage.update_document_metadata(doc_id, metadata)
                updated_count += 1
                print(f"  Updated document {doc_id} with {len(metadata)} metadata fields")
            except ValueError as e:
                print(f"  Error updating document {doc_id}: {str(e)}")
    
    return updated_count

def main():
    parser = argparse.ArgumentParser(description="Update storage metadata from JSON file")
    parser.add_argument("json_file", help="Path to the JSON file with parsed data")
    parser.add_argument("--storage-dir", default="declarations", 
                      help="Base directory for the storage system (default: declarations)")
    parser.add_argument("--ground-truth", action='store_true', 
                      help="Record that the fields are human-verified and to be considered ground truth.")
    parser.add_argument("--dry-run", action="store_true", 
                      help="Don't actually update storage, just print what would be updated")
    
    args = parser.parse_args()
    
    try:
        count = update_storage_from_json(
            args.json_file, 
            args.storage_dir,
            ground_truth=args.ground_truth,
            dry_run=args.dry_run
        )
        
        if args.dry_run:
            print(f"Dry run complete.")
        else:
            print(f"Successfully updated {count} documents.")
        return 0
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main())
