"""
First-pass attempt to fill out a FEMA Form 010-0-13 using
the information contained in a preliminary damage assessment report.
"""

import argparse
import functools
import json
import multiprocessing as mp
import time

import logging

import litellm
from litellm import completion

from fema_agent.forms.fema_010_0_13 import FEMA_FORM_010_0_13
from fema_agent.storage import DeclarationStorage

# Set up logging to both file and stdout
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create file handler
file_handler = logging.FileHandler('log/form_fill.log')
file_handler.setLevel(logging.INFO)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

PROMPT = """
You are an ex-FEMA official working at the company Hagerty Consulting.
Given the following preliminary damage assessment report from FEMA,
please fill out a Request for Presidential Disaster Declaration (FEMA Form 010-0-13).

PDA Report:
{pda_report}

Fill out the following information:
{field_information}

Return this information **only**, formatted as a JSON object. Format dates as "YYYY-MM-DD".
"""

def build_json_schema(n_fields: int, start=0):
    all_fields = list(FEMA_FORM_010_0_13.fields.items())
    selected = all_fields[start: start + n_fields]
    field_schema_dict = {}
    for field_name, field in selected:
        field_schema_dict[field_name] = {"type": field.to_schema_string()}

    return {"type": "object", "properties": field_schema_dict}


def get_field_info(n_fields: int, start=0) -> str:
    all_fields = list(FEMA_FORM_010_0_13.fields.items())
    selected = all_fields[start: start + n_fields]
    field_string_builder = []
    for field_name, field in selected:
        field_str = f' - {field_name} (field {field.field_number}): {field.description}'
        field_string_builder.append(field_str)

    return '\n'.join(field_string_builder)


def build_prompt(document, field_start_idx: int, n_fields: int):
    formatted = PROMPT.format(
        pda_report=document['pda_report'],
        field_information=get_field_info(n_fields=n_fields, start=field_start_idx)
        )
    return formatted

def _call_api(message, print_raw_response=False, json_schema=None):
    kwargs = {
        'model': 'gemini/gemini-2.0-flash',
        'messages': [{'content': message, 'role': 'user'}]
        }
    if json_schema is not None:
        kwargs['response_format'] = {
            'type': 'json_schema',
            'json_schema': json_schema,
            'strict': True
            }
    response = completion(**kwargs)
    if print_raw_response:
        logger.info('Raw response ')
        logger.info(response.choices[0].message.content)
        logger.info('-' * 30)
    return response

def call_with_retries(message: str, max_retries: int = 5, sleep_delay: float = 15, **kwargs):
    retries = 0
    while (retries < max_retries):
        try:
            response = _call_api(message, **kwargs)
            return response
        except litellm.exceptions.InternalServerError:
            logger.warning(f"Vertex AI server overloaded. Attempt {retries+1}/{max_retries}. Sleeping for {sleep_delay}s")
            retries += 1
            time.sleep(sleep_delay)
        except litellm.exceptions.RateLimitError:
            logger.warning(f"Rate limit hit. Attempt {retries+1}/{max_retries}. Sleeping for {sleep_delay}s")
            time.sleep(sleep_delay)
            sleep_delay *= 1.5  # Exponential backoff
    return None


def parse(response):
    content = response.choices[0].message.content
    # remove backticks/json filetype if formatted like markdown
    if content.startswith('```'):
        content = (content
           .replace('```json', '')
           .replace('```', '')
            )
        return json.loads(content)
    else:
        raise ValueError("Unable to parse response to JSON!")

def fill_fields(start_field_idx: int, document, n_fields: int, verbose=False):
    response = call_with_retries(
            build_prompt(document, field_start_idx=start_field_idx, n_fields=n_fields),
            json_schema=build_json_schema(start=start_field_idx, n_fields=n_fields),
            print_raw_response=verbose
            )
    try:
        result = parse(response)
        if verbose:
            logger.info('Parsed response ')
            logger.info(result)
            logger.info('-' * 30)
        return result
    except Exception as e:
        print(e)

def fill_form(document, chunk_size: int = 10, verbose=False):
    _fill_fields = functools.partial(
            fill_fields,
            document=document,
            n_fields=chunk_size,
            verbose=verbose
            )

    N_FIELDS = len(FEMA_FORM_010_0_13.fields)
    start_indices = list(range(0, N_FIELDS, chunk_size))

    with mp.Pool(processes=mp.cpu_count()) as pool:
        result_dicts = pool.map(_fill_fields, start_indices)

    overall_results = {}
    for result in result_dicts:
        if result:
            overall_results.update(result)

    return overall_results

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        '--storage-dir', type=str, required=True,
        help='Path to directory where PDFs/metadata are stored.'
        )
    p.add_argument(
        '--outpath', type=str, required=True,
        help='Path to which the filled form JSON will be stored.'
        )
    p.add_argument(
        '--fields-per-request', type=int, default=5,
        help='Number of form fields to fill in a single LLM call. Defaults to 5.'
        )
    p.add_argument('--verbose', action='store_true')

    args = p.parse_args()

    s = DeclarationStorage(args.storage_dir)
    docs = s.get_all_documents()

    attempts = []
    for doc_id in docs.keys():
        doc = s.get_document_metadata(doc_id)

        results = fill_form(doc, args.fields_per_request, verbose=args.verbose)
        results['uuid'] = doc_id

        logger.info(f'Document {doc_id} parsed.')

        if args.verbose:
            logger.info('-' * 15)
            logger.info(results)
            logger.info('-' * 15)

        attempts.append(results)

    with open(args.outpath, 'w+') as f:
        json.dump(attempts, f)
