#!/usr/bin/env python3
"""
PDF Semantic Segmentation with Gemini API
"""

import time
import os
import argparse
import pathlib
import re
import io
import shutil

from pathlib import Path
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

import csv
import pandas as pd

from google import genai
from google.genai import types
from google.genai.errors import APIError

# Load environment variables from .env file
load_dotenv()

# Get API key from environment variable
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables. Please set it.")

import re

def parse_response(response: str):
    """
    Parses the language model's response based on the expected output format.
    
    Args:
        response (str): The raw text response from the language model.
    
    Returns:
        dict: A dictionary containing the extracted fields with keys:
            - 'request_date'
            - 'state_or_tribal_government'
            - 'request_purpose'
            - 'incident_start_date'
            - 'incident_end_date'
            - 'incident_type'
            - 'damage_description'
            - 'resources_committed'
    """
    
    # Define the expected fields
    fields = [
        "request_date",
        "state_or_tribal_government",
        "request_purpose",
        "incident_start_date",
        "incident_end_date",
        "incident_type"
        "damage_description",
        "resources_committed"
    ]
    
    # Initialize dictionary with default values
    parsed_data = {field: "NA" for field in fields}
    
    # Extract fields from response
    lines = response.strip().split("\n")
    for i, field in enumerate(fields):
        if i < len(lines):
            parsed_data[field] = lines[i].strip()
    
    # Validate `request_purpose`
    if parsed_data["request_purpose"] not in {"Major Disaster", "Emergency", "NA"}:
        parsed_data["request_purpose"] = "NA"
    
    # Validate `incident_type`
    valid_incident_types = {
        'Drought', 'Earthquake', 'Explosion', 'Fire', 'Flood', 'Hurricane', 'Landslide', 'Mudslide',
        'Severe Storm', 'Snowstorm', 'Straight-Line Winds', 'Tidal Wave', 'Tornado', 'Tropical Depression',
        'Tropical Storm', 'Tsunami', 'Volcanic Eruption', 'Winter Storm', 'Other'
    }
    print(f"Raw incident types: {parsed_data['incident_type']}")
    # split incident types
    incidents = parsed_data['incident_type'].split(',')
    valid_incidents = []
    for reported_type in incidents:
        if reported_type.strip() in valid_incident_types:
            valid_incidents.append(reported_type.strip())

    print(f"Parsed incidents: {valid_incidents}")
    
    # Validate date format (YYYY-MM-DD)
    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for date_field in ["request_date", "incident_start_date", "incident_end_date"]:
        if not date_pattern.match(parsed_data[date_field]):
            parsed_data[date_field] = "NA"
    
    return parsed_data

def call_gemini_api(pdf_data, prompt, client):
    """
    Make a call to the Gemini API with the PDF data and prompt.
    
    Args:
        pdf_data (bytes): PDF file content
        prompt (str): Prompt for the Gemini model
        client (genai.Client): Gemini API client
        
    Returns:
        Response: Gemini API response
        
    Raises:
        Various exceptions from the Gemini API
    """
    return client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Part.from_bytes(
                data=pdf_data,
                mime_type='application/pdf',
            ),
            prompt
        ],
    )

def retry_with_backoff(func, max_retries=3, initial_delay=5):
    """
    Retry a function with exponential backoff when rate limit errors occur.
    
    Args:
        func: Function to call
        max_retries (int): Maximum number of retry attempts
        initial_delay (int): Initial delay between retries in seconds
        
    Returns:
        The result of the function if successful, None otherwise
    """
    retries = 0
    current_delay = initial_delay
    
    while retries <= max_retries:
        try:
            return func()
        except APIError as e:
            retries += 1
            if retries <= max_retries:
                # Exponential backoff with jitter
                sleep_time = current_delay * (1 + 0.2 * (os.urandom(1)[0] / 255))
                print(f"Rate limit exceeded. Retrying in {sleep_time:.2f} seconds (attempt {retries}/{max_retries})...")
                time.sleep(sleep_time)
                current_delay *= 2  # Exponential backoff
            else:
                print(f"Maximum retries reached. Giving up.")
                return None
        except Exception as e:
            print(f"Error calling function: {str(e)}")
            return None

def extract_metadata(pdf_path, client=None, max_retries=3, retry_delay=5):
    """
    Use Gemini API to extract metadata from a PDF automatically.
    
    Args:
        pdf_path (str or Path): Path to the PDF file
        client (genai.Client, optional): Gemini API client
        max_retries (int): Maximum number of retry attempts for rate limit errors
        retry_delay (int): Initial delay between retries in seconds
        
    Returns:
        Optional[pd.DataFrame]: DataFrame with the segmentation results, or None if failed
    """
    if client is None:
        client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Convert path to pathlib.Path if it's not already
    pdf_file = pdf_path if isinstance(pdf_path, pathlib.Path) else pathlib.Path(pdf_path)
    
    # Check if file exists
    if not pdf_file.exists():
        print(f"Error: The file '{pdf_path}' does not exist.")
        return None

    print(f'Parsing file: {pdf_file.name}')
    
    # Prepare prompt
    prompt = """
    This PDF contains a disaster declaration request issued to FEMA sometime
    between 2017-2019. Extract the following information from it, returning
    entries in plaintext separated by newlines. When you cannot parse a piece of
    information, write "NA". Your output format should be the following:

    <BASIC_INFORMATION>
    {{request_date: date}}
    {{state_or_tribal_government: text}}
    {{request_purpose: text}}
    {{incident_start_date: date}}
    {{incident_end_date: date}}
    {{incident_type: enum | comma-separated enum values}}
    <\\BASIC_INFORMATION>
    <DAMAGE>
    {{damage_description: multitext}}
    <\\DAMAGE>
    <RESOURCES>
    {{resources_committed: multitext}}
    <\\RESOURCES>
    <IA_PDA>
    {{ia_pda_performed: bool}}
    {{ia_pda_requested: date}}
    {{ia_pda_start: date}}
    {{ia_pda_end: date}}
    --
    {{ia_pda_accessibility_problems: multitext}}
    --
    <\\IA_PDA>
    <PA_PDA>
    {{pa_pda_performed: bool}}
    {{pa_pda_requested: date}}
    {{pa_pda_start: date}}
    {{pa_pda_end: date}}
    --
    {{pa_pda_accessibility_problems: multitext}}
    --
    <\\PA_PDA>
    <IA_PROGRAMS_AREAS>
    {{ia_programs: enum | comma-separated enum values}}
    --
    {{ia_programs_areas: multitext}}
    --
    {{ia_tribes: multitext}}
    --
    <\\IA_PROGRAMS_AREAS>

    ### Here is some formatting information.
    Do NOT include the output field names, include only the values.
    All dates should be formatted as YYYY-MM-DD.
    The `request_purpose` field should be either the string 'Major Disaster' or 'Emergency'.
    The type of incident should be either a single instance or a
    comma-separated list of the following strings:
        'Drought', 'Earthquake', 'Explosion', 'Fire', 'Flood',
        'Hurricane', 'Landslide', 'Mudslide', 'Severe Storm', 'Snowstorm',
        'Straight-Line Winds', 'Tidal Wave', 'Tornado', 'Tropical Depression',
        'Tropical Storm', 'Tsunami', 'Volcanic Eruption', 'Winter Storm', 'Other'.
    """
    
    # Read the file data once to avoid repeated file reads in retries
    try:
        pdf_data = pdf_file.read_bytes()
    except Exception as e:
        print(f"Error reading file {pdf_file.name}: {str(e)}")
        return None
    
    # Define the API call function
    def make_api_call():
        return call_gemini_api(pdf_data, prompt, client)
    
    # Call API with retry logic
    response = retry_with_backoff(make_api_call, max_retries, retry_delay)
    
    if response is None:
        return None
    
    # Process the response
    if response.text:
        # Print the raw response for debugging
        print(f'Response from file {pdf_file.name}:')
        print(response.text)
        
        # Parse the response into a DataFrame
        return parse_response(response.text)
    else:
        print(f"Error: No content in the response for {pdf_file.name}")
        return None

def process_directory(directory_path, result_directory, max_workers=3):
    """
    Process all PDF files in a directory and combine results into one CSV file.
    
    Args:
        directory_path (str): Path to the directory containing PDF files
        output_csv (str): Path to the output CSV file
        max_workers (int): Maximum number of concurrent workers
        
    Returns:
        bool: True if any files were successfully processed, False otherwise
    """
    directory = pathlib.Path(directory_path)
    
    # Check if directory exists
    if not directory.exists() or not directory.is_dir():
        print(f"Error: Directory '{directory_path}' does not exist or is not a directory.")
        return False
    
    # Find all PDF files in the directory
    pdf_files = list(directory.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in directory '{directory_path}'.")
        return False
    
    print(f"Found {len(pdf_files)} PDF files in directory '{directory_path}'.")

    # Create output directory if it doesn't exist
    result_directory = Path(result_directory)
    result_directory.mkdir(exist_ok=True, parents=True)
    
    # Initialize the Gemini client (reuse the same client for all requests)
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Process all PDF files and collect results
    all_results = []
    
    # Sort the files by name to ensure consistent processing order
    pdf_files.sort()
    
    # Use ThreadPoolExecutor for concurrent processing
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(extract_metadata, pdf_file, client): pdf_file
            for pdf_file in pdf_files
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_file):
            pdf_file = future_to_file[future]
            try:
                result_dict = future.result()
                if result_dict is not None:
                    result_dict['source_file'] = pdf_file.name
                    all_results.append(result_dict)
                    # copy the file to the result directory with
                    # the new name
                    shutil.copy(pdf_file, result_directory / pdf_file.name)
            except Exception as e:
                print(f"Error processing {pdf_file.name}: {str(e)}")
    
    # Combine all results into a single DataFrame
    if all_results:
        # combined_df = pd.concat(all_results, ignore_index=True)
        # 
        # # Sort by adjusted page number to maintain document order
        # combined_df = combined_df.sort_values('start_page')
        # 
        # # Save to CSV
        # combined_df.to_csv(output_csv, index=False)
        # print(f"Combined results from {len(all_results)} files saved to {output_csv}")
        print(all_results)
        return True
    else:
        print("No successful results to combine.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Segment directory of PDFs semantically using Gemini API")
    parser.add_argument("directory", help="Directory of PDF files to process")
    parser.add_argument("output", help="Output directory for extracted pdfs")
    parser.add_argument("--max-workers", type=int, default=3,
                        help="Maximum number of concurrent workers (default: 3)")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Segment the PDFs
    success = process_directory(args.directory, args.output, args.max_workers)

    
    if success:
        print("PDF segmentation completed successfully!")
        return 0
    else:
        print("PDF segmentation failed.")
        return 1

if __name__ == "__main__":
    exit(main())
