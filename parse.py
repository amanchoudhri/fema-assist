import argparse
import json
import tempfile
import time
import os
import re

from pathlib import Path
from typing import Any, Optional

from docetl.api import Pipeline, Dataset, MapOp, ReduceOp, PipelineStep, PipelineOutput

from docetl.operations.code_operations import CodeMapOperation

from forms.fema_010_0_13 import FEMA_FORM_010_0_13
from storage import DeclarationStorage

def field_display(page: int) -> str:
    fields = [
        f' - {field_name} ({field.field_number}): {field.description}'
        for field_name, field in FEMA_FORM_010_0_13.get_fields_for_page(page).items()
    ]
    return '\n'.join(fields)

def build_prompt(page: int, additional_instructions: Optional[str] = None) -> str:
    base_prompt = f"""
Extract the following information from this FEMA form page.

Here are the form field keystrings and descriptions on this
page for you to parse:
{field_display(page)}

Format all dates as "YYYY-MM-DD". If no day information is available,
format as "YYYY-MM".

If the form field is empty, return the empty string. Do NOT return
the field description in place of the empty string, when no data is available.
"""
    prompt = base_prompt
    if additional_instructions:
        prompt += '\n\n' + additional_instructions
    return prompt


def build_parse_op(page: int) -> MapOp:
    op = MapOp(
        name=f'parse_page_{page}',
        type='map',
        validate=[],
        pdf_url_key=f"page_{page}",
        prompt=build_prompt(page),
        output={"schema": FEMA_FORM_010_0_13.get_field_schema_dict(page=page)}
        )
    return op

def create_docetl_dataset_from_storage(storage_dir: str, temp_dir: str | None = None):
    """
    Create a DocETL-compatible dataset from a storage directory.
    
    Args:
        storage_dir: Path to the storage directory
        temp_dir: Path to use for the temporary dataset file (optional)
        
    Returns:
        Tuple of (dataset path, dataset documents)
    """
    # Initialize storage
    storage = DeclarationStorage(storage_dir)
    storage_dir_path = Path(storage_dir).absolute()
    
    # Get all documents
    documents = storage.get_all_documents()

    # Prepare dataset
    dataset = []
    for doc_id in documents.keys():
        # Get full metadata
        try:
            metadata = storage.get_document_metadata(doc_id)
            
            # Convert relative paths to absolute paths
            metadata_copy = metadata.copy()
            for key, value in metadata.items():
                # Check if it's a file path field
                is_page_number = bool(re.match(r"\Apage_\d+\Z", key))
                if key in ["file_path", "pages"] or is_page_number:
                    if key == "file_path" and value:
                        metadata_copy[key] = str(storage_dir_path / value)
                    elif key == "pages" and value:
                        metadata_copy[key] = [str(storage_dir_path / p) for p in value]
                    elif key.startswith("page_") and value:
                        metadata_copy[key] = str(storage_dir_path / value)
            
            dataset.append(metadata_copy)
        except Exception as e:
            print(f"Error retrieving metadata for {doc_id}: {e}")
    
    # # Prepare dataset
    # dataset = []
    # for doc_id, _ in documents.items():
    #     # Get full metadata
    #     try:
    #         metadata = storage.get_document_metadata(doc_id)
    #         dataset.append(metadata)
    #     except Exception as e:
    #         print(f"Error retrieving metadata for {doc_id}: {e}")
    
    # Determine output path
    if temp_dir:
        os.makedirs(temp_dir, exist_ok=True)
        dataset_path = Path(temp_dir) / f"{Path(storage_dir).name}_docetl.json"
    else:
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        dataset_path = Path(temp_file.name)
        temp_file.close()
    
    # Save dataset
    with open(dataset_path, 'w') as f:
        json.dump(dataset, f, indent=2)
    
    return dataset_path, dataset

def parse_dataset(
        dataset_path: Path,
        output_path: str,
        model: str,
        dataset_name: str = "dataset"
        ) -> list[dict[str, Any]]:
    """
    Parse a dataset using DocETL pipeline.
    
    Args:
        dataset_path: Path to the dataset JSON file
        output_path: Path where results will be saved
        model: Model name to use for parsing
        dataset_name: Name to use for the dataset in the pipeline
        
    Returns:
        List of parsed results
    """
    # Create operations for each page
    PAGES_IN_FEMA_010_0_13 = 4
    ops = [build_parse_op(i + 1) for i in range(PAGES_IN_FEMA_010_0_13)]
    
    # Define dataset
    datasets = {
        dataset_name: Dataset(type="file", path=str(dataset_path))
    }
    
    # Define pipeline steps
    steps = [
        PipelineStep(
            name="extract_info",
            input=dataset_name,
            operations=[op.name for op in ops]
        )
    ]
    
    # Define output
    output = PipelineOutput(type='file', path=output_path)
    
    # Create and run pipeline
    pipeline = Pipeline(
        name='extract_info',
        datasets=datasets,
        operations=ops,  # type: ignore
        steps=steps,
        output=output,
        default_model=model
    )
    
    pipeline.run()
    
    # Load and return results
    with open(output_path) as f:
        return json.load(f)

def chunk_dataset(data_path: Path, chunk_size: int) -> list[Path]:
    """
    Create temporary dataset files by chunking a larger dataset into smaller pieces.
    
    Args:
        data_path: Path to the original JSON dataset
        chunk_size: Maximum number of items per chunk
        
    Returns:
        List of paths to the temporary chunked dataset files
    """
    # Load the original dataset
    with open(data_path) as f:
        data = json.load(f)
    
    # If dataset is smaller than chunk_size, just return the original path
    if len(data) <= chunk_size:
        return [data_path]
    
    # Create temporary directory for chunks
    temp_dir = Path(tempfile.mkdtemp(prefix="fema_chunks_"))
    
    # Split data into chunks and save as temporary files
    chunk_paths = []
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i+chunk_size]
        chunk_path = temp_dir /  f"chunk_{i//chunk_size}.json"
        with open(chunk_path, 'w') as f:
            json.dump(chunk, f)
        chunk_paths.append(chunk_path)
    
    print(f"Split dataset into {len(chunk_paths)} chunks of {chunk_size} items each")
    return chunk_paths

def process_dataset_with_rate_limit(
        dataset_path: Path,
        outpath: str,
        model: str,
        chunk_size: int = 8,
        sleep_time: int = 60
        ):
    """
    Process a dataset in chunks with pauses between chunks to avoid rate limits.
    
    Args:
        dataset_path: Path to the dataset JSON
        outpath: Path where final output will be saved
        model: Model to use for parsing
        chunk_size: Maximum number of items to process in one batch
        sleep_time: Seconds to sleep between batches
    """
    # Split dataset into chunks
    chunk_paths = chunk_dataset(dataset_path, chunk_size)
    
    # Prepare for combining results
    all_results = []
    
    # Process each chunk
    for i, chunk_path in enumerate(chunk_paths):
        print(f"Processing chunk {i+1}/{len(chunk_paths)}...")
        
        # Create temp output path for this chunk
        temp_outpath = f"{outpath}_chunk_{i}.json"
        
        # Parse this chunk
        chunk_results = parse_dataset(
            dataset_path=chunk_path,
            output_path=temp_outpath,
            model=model,
            dataset_name=f"chunk_{i}"
        )
        
        # Add results to combined list
        all_results.extend(chunk_results)
        
        # Sleep between chunks (except after the last one)
        if i < len(chunk_paths) - 1:
            print(f"Sleeping for {sleep_time} seconds to avoid rate limits...")
            time.sleep(sleep_time)
    
    # Save combined results to the final output path
    with open(outpath, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"All chunks processed successfully. Combined results saved to {outpath}")
    
    # Clean up temp files
    for chunk_path in chunk_paths:
        if chunk_path != dataset_path:  # Don't delete original file
            try:
                os.remove(chunk_path)
                os.rmdir(os.path.dirname(chunk_path))
            except:
                pass

def parse_storage_directory(
        storage_dir: str,
        output_path: str,
        model: str,
        temp_dir: str | None = None,
        avoid_rate_limit: bool = False,
        chunk_size: int = 8,
        sleep_time: int = 60
        ):
    """
    Parse all declarations in a storage directory.
    
    Args:
        storage_dir: Path to the storage directory
        output_path: Path where parsed results will be saved
        model: Model to use for parsing
        temp_dir: Directory to store temporary files (optional)
        avoid_rate_limit: Whether to process in batches with delays
        chunk_size: Number of documents per batch if avoiding rate limits
        sleep_time: Seconds to sleep between batches
    """
    print(f"Creating DocETL dataset from storage directory: {storage_dir}")
    dataset_path, documents = create_docetl_dataset_from_storage(storage_dir, temp_dir)
    
    print(f"Created dataset with {len(documents)} documents at {dataset_path}")
    
    if avoid_rate_limit:
        process_dataset_with_rate_limit(
            dataset_path=dataset_path,
            outpath=output_path,
            model=model,
            chunk_size=chunk_size,
            sleep_time=sleep_time
        )
    else:
        parse_dataset(
            dataset_path=dataset_path,
            output_path=output_path,
            model=model
        )
    
    print(f"Processing complete. Results saved to {output_path}")
    
    # Clean up temporary dataset file
    if not temp_dir:  # Only remove if we created a temp file
        try:
            os.remove(dataset_path)
        except:
            pass

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description='Parse FEMA disaster declaration forms using DocETL'
        )
    parser.add_argument(
        '--storage-dir', type=str, required=True, 
        help='Path to the storage directory containing declarations'
        )
    parser.add_argument('--outpath', type=str, required=True,
                        help='Path where output JSON will be saved')
    parser.add_argument('--model', type=str, default='gemini-2.0-flash-lite',
                        choices=['gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-2.5-flash'],
                        help='Model to use for parsing')
    parser.add_argument('--avoid-rate-limit', action='store_true',
                        help='Process in smaller batches with pauses to avoid rate limits')
    
    args = parser.parse_args()
    
    # Model mapping
    MODEL_MAPPING = {
        'gemini-2.0-flash': 'gemini/gemini-2.0-flash',
        'gemini-2.0-flash-lite': 'gemini/gemini-2.0-flash-lite-preview-02-05',
        'gemini-2.5-flash': 'gemini-2.5-flash-preview-04-17'
    }

    model = MODEL_MAPPING[args.model]
    
    parse_storage_directory(
        args.storage_dir,
        args.outpath,
        model,
        avoid_rate_limit=args.avoid_rate_limit
        )


if __name__ == "__main__":
    main()
