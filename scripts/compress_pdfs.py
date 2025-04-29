import argparse
import zipfile

from pathlib import Path

def create_pdf_archive(pdf_dir, output_file):
    """Create a ZIP archive of PDFs preserving UUID directory structure"""
    base_path = Path(pdf_dir)
    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for uuid_dir in base_path.iterdir():
            if not uuid_dir.is_dir():
                continue
                
            # Find all PDFs in this UUID directory
            for pdf_file in uuid_dir.glob('**/*.pdf'):
                # Create archive path relative to base_path
                arcname = pdf_file.relative_to(base_path)
                zipf.write(pdf_file, arcname)
    
    print(f"Created PDF archive at {output_file}")

if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description=("Compress a collection of PDFs, organized as root/uuid-subdir/*.pdf." \
        "Maintains uuid-subdir structure.")
        )

    p.add_argument('--pdf_dir', type=str)
    p.add_argument('--outpath', type=str)

    args = p.parse_args()

    create_pdf_archive(args.pdf_dir, args.outpath)
