import argparse
import json
import tempfile
import time
import os

from pathlib import Path
from typing import Any, Optional

from docetl.api import Pipeline, Dataset, MapOp, ReduceOp, PipelineStep, PipelineOutput

from docetl.operations.code_operations import CodeMapOperation

from forms.fema_010_0_13 import FEMA_FORM_010_0_13

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

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description='Parse FEMA disaster declaration forms using DocETL'
        )
    parser.add_argument(
        '--dataset', type=str, required=True, 
        help='Dataset to use: "first_three", "all", "test_set", or path to a JSON file'
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
    
    # Pre-defined datasets
    DATASETS = {
        'first_three': Dataset(type="file", path="first_three_docetl.json"),
        'all': Dataset(type="file", path="all-declarations_docetl.json"),
        'test_set': Dataset(type="file", path="test-set-declarations_docetl.json")
    }
    
    if args.dataset in DATASETS:
        dataset_path = Path(DATASETS[args.dataset].path)
    else:
        # Assume it's a path to a JSON file
        dataset_path = Path(args.dataset)

    if args.avoid_rate_limit:
        process_dataset_with_rate_limit(
            dataset_path, 
            args.outpath, 
            model
        )
    else:
        # Just process the dataset directly
        parse_dataset(
            dataset_path=dataset_path,
            output_path=args.outpath,
            model=model
        )

if __name__ == "__main__":
    main()
