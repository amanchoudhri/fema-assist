"""
Generate docetl.json from the declaration storage system
"""

import argparse
import json
import re

from pathlib import Path

def generate_docetl(storage_dir, output_file=None):
    """
    Generate a docetl.json file from the declaration storage system
    
    Args:
        storage_dir (str): Path to the declarations storage directory
        output_file (str, optional): Path to the output file, 
            defaults to [storage dirname]_docetl.json in current dir
        
    Returns:
        int: Number of documents processed
    """
    storage_dir = Path(storage_dir).resolve()  # Get absolute path
    
    if output_file is None:
        output_file = Path(f"{storage_dir.name}_docetl.json")
    else:
        output_file = Path(output_file)
    
    # Read registry.json
    registry_path = storage_dir / "registry.json"
    if not registry_path.exists():
        raise FileNotFoundError(f"Registry file not found: {registry_path}")
    
    with open(registry_path, "r") as f:
        registry = json.load(f)
    
    documents = []
    
    # Process each document
    for doc_id, reg_info in registry["documents"].items():
        # Get full metadata from document's metadata.json
        metadata_path = storage_dir / doc_id / "metadata.json"
        
        try:
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # If metadata file is missing or invalid, use registry info
            metadata = reg_info.copy()
        
        # Create entry with UUID
        entry = {"uuid": doc_id}
        
        # Add metadata fields
        for key, value in metadata.items():
            # Process paths if needed
            is_page_number = bool(re.match(r"\Apage_\d+\Z", key))
            if key in ["file_path", "pages"] or is_page_number:
                if key == "file_path":
                    entry[key] = str(storage_dir / value)
                elif key == "pages":
                    entry[key] = [str(storage_dir / p) for p in value]
                elif key.startswith("page_"):
                    entry[key] = str(storage_dir / value)
            else:
                entry[key] = value
        
        documents.append(entry)
    
    # Write to output file
    with open(output_file, "w") as f:
        json.dump(documents, f, indent=2)
    
    return len(documents)

def main():
    parser = argparse.ArgumentParser(description="Generate docetl.json from the declaration storage system")
    parser.add_argument("storage_dir", help="Path to the declarations storage directory")
    parser.add_argument("--output", "-o",
                        help="Path to the output file (defaults to [storage dirname]_docetl.json)")
    
    args = parser.parse_args()
    
    try:
        count = generate_docetl(
            args.storage_dir, 
            args.output,
        )
        print(f"Generated docetl json file with {count} documents")
        return 0
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main())
