import argparse
import datetime
import zipfile
import json

from pathlib import Path

def extract_pdfs(pdf_archive, output_dir):
    """Extract PDFs from archive, creating UUID directory structure"""
    output_path = Path(output_dir)
    
    with zipfile.ZipFile(pdf_archive, 'r') as zipf:
        print(f"Extracting PDFs from {pdf_archive}...")
        zipf.extractall(path=output_path)
    
    print(f"PDFs extracted successfully to {output_path.parent}")
    return True

def inflate_metadata(jsonl_file, output_dir):
    """Inflate metadata into existing UUID directory structure"""
    output_path = Path(output_dir)
    count = 0
    
    print(f"Inflating metadata from {jsonl_file}...")
    with open(jsonl_file, 'r') as f:
        for line in f:
            metadata = json.loads(line)
            uuid = metadata.pop('uuid', None)
            
            if not uuid:
                continue
                
            uuid_dir = output_path / uuid
            
            # Skip if directory doesn't exist (PDF might be missing)
            if not uuid_dir.exists():
                print(f"Warning: Directory for {uuid} doesn't exist, skipping metadata")
                continue
                
            with open(uuid_dir / "metadata.json", 'w') as mf:
                json.dump(metadata, mf, indent=2)
            
            count += 1
    
    print(f"Inflated {count} metadata files to {output_dir}")
    return count


def create_registry(output_dir):
    """Create registry.json file for the storage API"""
    output_path = Path(output_dir)
    registry_path = output_path / "registry.json"
    
    print(f"Creating registry.json file...")
    
    # Initialize registry structure
    registry = {
        "documents": {},
        "last_updated": datetime.datetime.now().isoformat()
    }
    
    # Scan directories to build registry
    for uuid_dir in output_path.iterdir():
        if not uuid_dir.is_dir():
            continue
            
        metadata_path = uuid_dir / "metadata.json"
        if not metadata_path.exists():
            print(f"Warning: No metadata found for {uuid_dir.name}, skipping in registry")
            continue
            
        # Read metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        # Extract basic info for registry
        doc_info = {
            "original_filename": metadata.get("original_filename", f"unknown_{uuid_dir.name}.pdf"),
            "import_date": metadata.get("import_date", datetime.datetime.now().isoformat()),
            "page_count": metadata.get("page_count", 0),
            "file_path": str(uuid_dir / "all.pdf")
        }
        
        # Add page paths if they exist
        pages = []
        page_dict = {}
        
        # Look for pages in metadata or in directory
        for i in range(1, metadata.get("page_count", 100) + 1):  # Try up to max page count or 100
            page_key = f"page_{i}"
            page_path = uuid_dir / f"{page_key}.pdf"
            
            if page_path.exists():
                rel_path = str(page_path)
                pages.append(rel_path)
                page_dict[page_key] = rel_path
            elif page_key in metadata:
                # If page info is in metadata but file doesn't exist, skip
                continue
            else:
                # No more pages found
                break
                
        if pages:
            doc_info["pages"] = pages
            doc_info.update(page_dict)
        
        # Add to registry
        registry["documents"][uuid_dir.name] = doc_info
    
    # Write registry to file
    with open(registry_path, 'w') as f:
        json.dump(registry, f, indent=2)
    
    print(f"Created registry with {len(registry['documents'])} documents")
    return len(registry["documents"])

def setup_repository(pdf_archive, jsonl_file, destination=None):
    """Set up repository data from archives, PDFs first then metadata"""
    output_dir = destination if destination else "data/processed/all-declarations"
    # Create base directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 1. Extract PDFs if provided (creates directory structure)
    if pdf_archive and Path(pdf_archive).exists():
        extract_pdfs(pdf_archive, output_dir)
    else:
        print("No PDF archive provided or file not found.")
        print(f"Expecting directory structure in {output_dir}")
    
    # 2. Inflate metadata into existing structure
    inflate_metadata(jsonl_file, output_dir)

    # 3. Create registry.json file
    create_registry(output_dir)
    
    print("Setup complete! You can now use the repository.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Set up FEMA declaration (Form 010-0-13) data")
    parser.add_argument("--pdf-archive", required=True, help="Path to PDF archive")
    parser.add_argument("--jsonl-file", required=True, help="Path to JSONL metadata file")
    parser.add_argument(
            "--destination",
            help="Path in which the data will be setup. Defaults to data/processed/all-declarations",
            default="data/processed/all-declarations"
            )
    args = parser.parse_args()
    
    setup_repository(args.pdf_archive, args.jsonl_file, destination=args.destination)
