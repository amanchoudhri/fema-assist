import os
import uuid
import shutil
import argparse
import json
import datetime
import re

from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter

class DeclarationStorage:
    def __init__(self, base_dir="declarations"):
        """Initialize the declaration storage system"""
        self.base_dir = Path(base_dir)
        self.setup_storage()
    
    def setup_storage(self):
        """Create the base directory structure and registry files"""
        # Create base directory if it doesn't exist
        self.base_dir.mkdir(exist_ok=True)
        
        # Create registry file if it doesn't exist
        self.registry_path = self.base_dir / "registry.json"
        if not self.registry_path.exists():
            with open(self.registry_path, "w") as f:
                json.dump({
                    "documents": {},
                    "last_updated": datetime.datetime.now().isoformat()
                }, f, indent=2)
        
        # Create metadata schema file if it doesn't exist
        schema_path = self.base_dir / "metadata_schema.json"
        if not schema_path.exists():
            schema = {
                "type": "object",
                "properties": {
                    "original_filename": {"type": "string"},
                    "import_date": {"type": "string", "format": "date-time"},
                    "page_count": {"type": "integer"},
                    "file_path": {"type": "string"},
                    "pages": {"type": "array", "items": {"type": "string"}},

                    # Individual page entries (`page_1`, `page_2`, ...) will be added dynamically

                    # Also add metadata fields, which will be populated later.
                    "request_date": {"type": "string"},
                    "state_or_tribal_government": {"type": "string"},
                    "request_purpose": {"type": "string"},
                    "incident_type": {"type": "string"}
                },
                "required": ["original_filename", "import_date", "page_count", "file_path", "pages"]
            }
            with open(schema_path, "w") as f:
                json.dump(schema, f, indent=2)
    
    def add_document(self, pdf_path, metadata=None):
        """
        Add a new document to the storage system
        
        Args:
            pdf_path: Path to the PDF file
            metadata: Optional initial metadata
            
        Returns:
            document_id: UUID of the added document
        """
        pdf_path = Path(pdf_path)
        
        # Generate UUID for this document
        doc_id = str(uuid.uuid4())
        doc_dir = self.base_dir / doc_id
        
        # Create directory for this document
        doc_dir.mkdir(exist_ok=True)
        
        # Copy the original PDF
        dest_path = doc_dir / "all.pdf"
        shutil.copy(pdf_path, dest_path)
        
        # Split the PDF into individual pages
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        
        page_paths = []
        page_dict = {}  # Dictionary for individual page entries
        
        for i in range(total_pages):
            writer = PdfWriter()
            writer.add_page(reader.pages[i])
            page_path = doc_dir / f"page_{i+1}.pdf"
            with open(page_path, "wb") as out:
                writer.write(out)
                
            # Store relative path
            rel_path = str(page_path.relative_to(self.base_dir))
            page_paths.append(rel_path)
            
            # Add individual page entry
            page_dict[f"page_{i+1}"] = rel_path
        
        # Create or update metadata
        if metadata is None:
            metadata = {}
        
        doc_metadata = {
            "original_filename": pdf_path.name,
            "import_date": datetime.datetime.now().isoformat(),
            "page_count": total_pages,
            "file_path": str(dest_path.relative_to(self.base_dir)),
            "pages": page_paths,
            **page_dict  # Add individual page entries
        }
        doc_metadata.update(metadata)  # Add any additional metadata
        
        # Save document metadata
        with open(doc_dir / "metadata.json", "w") as f:
            json.dump(doc_metadata, f, indent=2)
        
        # Update registry
        self.update_registry(doc_id, doc_metadata)
        
        return doc_id
    
    def update_registry(self, doc_id, metadata):
        """Update the registry with a new or updated document"""
        # Update registry.json
        with open(self.registry_path, "r") as f:
            registry = json.load(f)
        
        # Extract page-specific keys
        page_dict = {}
        for i in range(1, metadata["page_count"] + 1):
            key = f"page_{i}"
            if key in metadata:
                page_dict[key] = metadata[key]
        
        # Add document info to registry
        registry["documents"][doc_id] = {
            "original_filename": metadata["original_filename"],
            "import_date": metadata["import_date"],
            "page_count": metadata["page_count"],
            "file_path": metadata["file_path"],
            "pages": metadata["pages"],
            **page_dict  # Include individual page entries
        }
        
        registry["last_updated"] = datetime.datetime.now().isoformat()
        
        with open(self.registry_path, "w") as f:
            json.dump(registry, f, indent=2)
        
    
    def update_document_metadata(self, doc_id, metadata):
        """Update metadata for an existing document"""
        doc_dir = self.base_dir / doc_id
        metadata_path = doc_dir / "metadata.json"
        
        if not metadata_path.exists():
            raise ValueError(f"Document {doc_id} not found")
        
        # Read existing metadata
        with open(metadata_path, "r") as f:
            existing_metadata = json.load(f)
        
        # Update with new metadata
        existing_metadata.update(metadata)
        
        # Save updated metadata
        with open(metadata_path, "w") as f:
            json.dump(existing_metadata, f, indent=2)
        
        # Also update the registry if relevant fields changed
        registry_fields = ["original_filename", "page_count", "file_path", "pages"]
        page_pattern = re.compile(r"^page_\d+$")
        
        if any(k in metadata for k in registry_fields) or any(page_pattern.match(k) for k in metadata):
            self.update_registry(doc_id, existing_metadata)
        
        return existing_metadata
    
    def get_document_metadata(self, doc_id):
        """Get metadata for a specific document"""
        metadata_path = self.base_dir / doc_id / "metadata.json"
        
        if not metadata_path.exists():
            raise ValueError(f"Document {doc_id} not found")
        
        with open(metadata_path, "r") as f:
            return json.load(f)
    
    def get_document_path(self, doc_id):
        """Get the path to a document's PDF file"""
        return self.base_dir / doc_id / "all.pdf"
    
    def get_page_path(self, doc_id, page_num):
        """Get the path to a specific page of a document"""
        return self.base_dir / doc_id / f"page_{page_num}.pdf"
    
    def get_all_documents(self):
        """Get information about all documents in the storage"""
        with open(self.registry_path, "r") as f:
            registry = json.load(f)
        
        return registry["documents"]
    
    def add_directory(self, dir_path):
        """Process all PDFs in a directory"""
        dir_path = Path(dir_path)
        
        # Find all PDFs in the directory
        pdfs = list(dir_path.glob("*.pdf"))
        
        if not pdfs:
            print(f"No PDF files found in {dir_path}")
            return []
        
        # Process each PDF
        results = []
        for pdf in pdfs:
            print(f"Processing {pdf.name}...")
            doc_id = self.add_document(pdf)
            results.append((pdf.name, doc_id))
            print(f"  → Stored as {doc_id}")
        
        return results

def main():
    parser = argparse.ArgumentParser(description="Disaster Declaration Document Storage")

    # Add base parser to pull the form folder storage directory
    base_parser = argparse.ArgumentParser(add_help=False)
    base_parser.add_argument('--base_dir', default='declarations',
                             help='Base directory for document storage.')

    subparsers = parser.add_subparsers(
            dest="command",
            required=True,
            help="Command to execute")
    
    # Add document command
    add_parser = subparsers.add_parser("add", parents=[base_parser], help="Add a document")
    add_parser.add_argument("source", help="PDF file or directory to add")
    
    # List documents command
    list_parser = subparsers.add_parser("list", parents=[base_parser], help="List all documents")
    
    # Update metadata command
    update_parser = subparsers.add_parser("update", parents=[base_parser], help="Update document metadata")
    update_parser.add_argument("doc_id", help="Document UUID")
    update_parser.add_argument("--metadata", required=True, help="JSON metadata string or file path")

    args = parser.parse_args()
    
    storage = DeclarationStorage(args.base_dir)
    
    if args.command == "add":
        source_path = Path(args.source)
        
        if source_path.is_file() and source_path.suffix.lower() == '.pdf':
            # Add a single PDF file
            doc_id = storage.add_document(source_path)
            print(f"Added {source_path.name} → UUID: {doc_id}")
            
        elif source_path.is_dir():
            # Process all PDFs in a directory
            results = storage.add_directory(source_path)
            print(f"Added {len(results)} PDF files")
            for filename, doc_id in results:
                print(f"  {filename} → {doc_id}")
                
        else:
            print(f"Error: {args.source} is not a PDF file or directory")
            return 1
            
    elif args.command == "list":
        # List all documents
        documents = storage.get_all_documents()
        print(f"Found {len(documents)} documents:")
        for doc_id, info in documents.items():
            print(f"  {doc_id}: {info['original_filename']} ({info['page_count']} pages)")
            
    elif args.command == "update":
        # Update document metadata
        try:
            # Parse metadata from JSON string or file
            metadata_arg = args.metadata
            if os.path.isfile(metadata_arg):
                with open(metadata_arg, 'r') as f:
                    metadata = json.load(f)
            else:
                metadata = json.loads(metadata_arg)
                
            storage.update_document_metadata(args.doc_id, metadata)
            print(f"Updated metadata for document {args.doc_id}")
            
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON metadata")
            return 1
        except ValueError as e:
            print(f"Error: {str(e)}")
            return 1

    else:
        parser.print_help()
        
    return 0

if __name__ == "__main__":
    exit(main())
