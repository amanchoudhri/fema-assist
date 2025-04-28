import argparse
from typing import Optional

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
    
    # Determine which dataset to use
    if args.dataset in DATASETS:
        dataset_name = args.dataset
        dataset = DATASETS[args.dataset]
    else:
        # Assume it's a path to a JSON file
        dataset_name = "custom_dataset"
        dataset = Dataset(type="file", path=args.dataset)
        DATASETS[dataset_name] = dataset
    
    # Create operations for each page
    PAGES_IN_FEMA_010_0_13 = 4
    ops = [build_parse_op(i + 1) for i in range(PAGES_IN_FEMA_010_0_13)]
    
    # Define pipeline steps
    steps = [
        PipelineStep(
            name="extract_info",
            input=dataset_name,
            operations=[op.name for op in ops]
        )
    ]
    
    # Define output
    output = PipelineOutput(type='file', path=args.outpath)
    
    # Create and run pipeline
    pipeline = Pipeline(
        name='extract_info',
        datasets=DATASETS,
        operations=ops,  # type: ignore
        steps=steps,
        output=output,
        default_model=model
    )
    
    pipeline.run()

if __name__ == "__main__":
    main()
