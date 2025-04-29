import json
from pathlib import Path

def compress_metadata(base_dir, output_file):
    """Compress UUID-based metadata into a single JSONL file"""
    processed = 0
    base_path = Path(base_dir)
    
    # Ensure output directory exists
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as out_f:
        for uuid_dir in base_path.iterdir():
            if not uuid_dir.is_dir():
                continue
                
            metadata_file = uuid_dir / "metadata.json"
            if not metadata_file.exists():
                continue
                
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                metadata['uuid'] = uuid_dir.name
                out_f.write(json.dumps(metadata) + '\n')
                processed += 1
    
    print(f"Compressed {processed} metadata files to {output_file}")

# Example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Compress metadata to JSONL")
    parser.add_argument("base_dir", help="Directory containing UUID folders with metadata.json")
    parser.add_argument("output_file", help="Output JSONL file path")
    
    args = parser.parse_args()
    compress_metadata(args.base_dir, args.output_file)
