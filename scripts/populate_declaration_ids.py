#!/usr/bin/env python3
"""
Populate FEMA Declaration IDs for disaster declarations by querying the FEMA API.

This script:
1. Goes through all disaster declarations in a specified directory
2. For each declaration, queries the OpenFEMA API to find matching records
3. Updates the declaration with the matching FEMA declaration ID if found
4. Reports unprocessed declarations for manual review
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from fema_agent.storage import DeclarationStorage

STATE_ABBREVIATIONS = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'district of columbia': 'DC', 'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI',
    'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA',
    'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME',
    'maryland': 'MD', 'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN',
    'mississippi': 'MS', 'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE',
    'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM',
    'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH',
    'oklahoma': 'OK', 'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI',
    'south carolina': 'SC', 'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX',
    'utah': 'UT', 'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA',
    'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY',

     # American Samoa, Guam, etc are treated like states in the FEMA db
    'american samoa': 'AS',
    'u.s. territory of guam': 'GU',
    'northern mariana islands': 'MP'

}

TRIBES_TO_STATE = {
    'oglala sioux tribe': 'SD',
    'soboba band of luiseno indians': 'CA',
    'navajo nation': 'AZ',
    "tohono o'odham nation": 'AZ',
    'ponca tribe of nebraska': 'NE',
    'cahuilla band of indians': 'CA',
    'sac & fox tribe of the mississippi of iowa': 'IA',
    'confederated tribes of the colville reservation': 'WA',
    'havasupai tribe': 'AZ',
    'la jolla band of luiseno indians': 'CA'
}


def parse_state(state_str: str) -> str | None:
    name = state_str.lower().strip()
    
    # Remove known prefixes
    PREFIXES = [
        'commonwealth of the ', 'commonwealth of ',
        'the state of ', 'state of '
        ]
    for prefix in PREFIXES:
        if name.startswith(prefix):
            name = name.replace(prefix, '', 1)
            break  # only one prefix should apply
    
    # Remove trailing " state" if present
    if name.endswith(' state'):
        name = name.replace(' state', '', 1)

    name_clean = name.strip()

    # Try mapping to abbreviations, flagging if they don't exist
    if name_clean in STATE_ABBREVIATIONS:
        return STATE_ABBREVIATIONS[name_clean]
    elif name_clean in TRIBES_TO_STATE:
        return TRIBES_TO_STATE[name_clean]
    else:
        return None


def parse_date(date_str: str) -> Optional[datetime.datetime]:
    """Parse a date string into a datetime.datetime object."""
    if not date_str or not isinstance(date_str, str):
        return None
    
    # Only recognize YYYY-MM-DD format
    try:
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj
    except ValueError:
        return None


def search_fema_declarations(state: str, incident_date: datetime.datetime) -> List[Dict]:
    """
    Search the FEMA API for declarations matching the state and incident date.
    
    Args:
        state: The state or tribal name
        incident_date: The incident date
        
    Returns:
        A list of matching declaration records
    """
    # Build the API query
    base_url = "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"
    
    # Set up date range (3 days before and after incident date to catch matching records)
    date_before = incident_date - datetime.timedelta(days=3)
    date_after = incident_date + datetime.timedelta(days=3)
    
    # Format dates for the API
    start_date = date_before.isoformat()
    end_date = date_after.isoformat()
    
    # Build query parameters
    params = {
        "$filter": f"state eq '{state}' and " +
                  f"incidentBeginDate ge '{start_date}' and " +
                  f"incidentBeginDate le '{end_date}'",
        "$orderby": "incidentBeginDate desc",
        "$top": "50"
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("DisasterDeclarationsSummaries", [])
    except requests.RequestException as e:
        print(f"Error querying FEMA API: {e}")
        return []

def extract_unique_disasters(declaration_summaries: List[Dict]) -> List[Dict]:
    """
    Extract unique disasters from a list of FEMA records.
    
    Args:
        declaration_summaries: List of declaration records from the FEMA API
        
    Returns:
        List of unique disaster records with essential information
    """
    # Use a dictionary to track unique disaster numbers
    unique_disasters = {}
    
    for record in declaration_summaries:
        disaster_id = record.get('disasterNumber')
        
        # Skip if we've already seen this disaster
        if disaster_id in unique_disasters:
            continue
        
        # Extract the essential information
        unique_disasters[disaster_id] = {
            'femaDeclarationString': record.get('femaDeclarationString', ''),
            'state': record.get('state', ''),
            'incidentBeginDate': record.get('incidentBeginDate', ''),
            'incidentEndDate': record.get('incidentEndDate', ''),
            'incidentType': record.get('incidentType', ''),
            'declarationTitle': record.get('declarationTitle', ''),
            'declarationDate': record.get('declarationDate', ''),
            'disasterNumber': disaster_id
        }
    
    # Return the values as a list
    return list(unique_disasters.values())

def choose_matching_declaration(doc_metadata: Dict, declarations: List[Dict]) -> Optional[Dict]:
    """
    Present matching declarations to the user and let them choose one.
    
    Args:
        doc_metadata: The document metadata
        declarations: List of potential matching declarations
        
    Returns:
        The chosen declaration or None if none chosen
    """
    if not declarations:
        return None
    
    if len(declarations) == 1:
        # If there's only one match, return it without prompting
        return declarations[0]
    
    # If there are multiple matches, prompt the user to choose
    print("\n" + "="*80)
    print(f"Multiple matches found for document: {doc_metadata['original_filename']}")
    print(f"State: {doc_metadata.get('state_or_tribe', 'Unknown')}")
    print(f"Incident Date: {doc_metadata.get('incident_period_beginning_date', 'Unknown')}")
    print(f"Incident Type: {doc_metadata.get('incident_type', 'Unknown')}")
    print(f"Request Purpose: {doc_metadata.get('request_purpose', 'Unknown')}")
    print("="*80)
    
    print("\nPotential matches:")
    for i, decl in enumerate(declarations, 1):
        print(f"{i}. {decl.get('femaDeclarationString')} - {decl.get('declarationTitle')}")
        print(f"   Incident: {decl.get('incidentType')} - {decl.get('incidentBeginDate')} to {decl.get('incidentEndDate')}")
        print(f"   Declaration Date: {decl.get('declarationDate')}")
        print()
    
    print("0. None of these match (skip)")
    
    while True:
        try:
            choice = int(input("\nEnter choice number: "))
            if choice == 0:
                return None
            if 1 <= choice <= len(declarations):
                return declarations[choice - 1]
            print("Invalid choice. Please try again.")
        except ValueError:
            print("Please enter a number.")


def main():
    parser = argparse.ArgumentParser(description="Populate FEMA Declaration IDs for disaster declarations")
    parser.add_argument("declaration_dir", help="Directory containing declaration documents")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually update declaration IDs, just show what would happen")
    parser.add_argument("--auto-match", action="store_true", help="Automatically match declarations without prompting if only one match is found")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed logs")
    
    args = parser.parse_args()
    
    # Initialize storage
    storage = DeclarationStorage(args.declaration_dir)
    
    # Get all documents
    all_documents = storage.get_all_documents()
    print(f"Found {len(all_documents)} documents in {args.declaration_dir}")
    
    # Track unprocessed documents
    unprocessed = []
    matched = []
    
    for doc_id, doc_info in all_documents.items():
        # Get full metadata
        try:
            metadata = storage.get_document_metadata(doc_id)
        except ValueError:
            print(f"Error retrieving metadata for {doc_id}, skipping.")
            unprocessed.append((doc_id, doc_info, "Missing metadata"))
            continue
        
        # Skip if already has FEMA declaration ID
        if metadata.get("fema_declaration_id"):
            if args.verbose:
                print(f"Document {doc_id} already has FEMA declaration ID: {metadata['fema_declaration_id']}")
            continue
        
        # Extract key information for matching
        state_str = metadata.get("state_or_tribe")
        incident_date_str = metadata.get("incident_period_beginning_date")
        
        if not state_str or not incident_date_str:
            print(f"Document {doc_id} missing state or incident date, skipping.")
            unprocessed.append((doc_id, metadata, "Missing state or incident date"))
            continue
        
        # Parse state
        state = parse_state(state_str)
        if not state:
            print(f"Unable to parse state {state_str} from document {doc_id}, skipping.")
            unprocessed.append((doc_id, metadata, f"Unable to parse state: {state_str}"))
            continue

        # Parse incident date
        incident_date = parse_date(incident_date_str)
        if not incident_date:
            print(f"Document {doc_id} has invalid incident date format: {incident_date_str}, skipping.")
            unprocessed.append((doc_id, metadata, f"Invalid date format: {incident_date_str}"))
            continue
        
        print(f"Processing document {doc_id}: {metadata.get('original_filename', 'Unknown')}")
        print(f"  State: {state}, Incident Date: {incident_date}")
        
        # Search FEMA API for matching declarations
        declarations = search_fema_declarations(state, incident_date)
        
        if not declarations:
            print(f"  No matching FEMA declarations found for {doc_id}")
            unprocessed.append((doc_id, metadata, "No matching declarations found"))
            continue

        # Extract unique disasters
        unique_disasters = extract_unique_disasters(declarations)
        print(f"  Found {len(declarations)} records representing {len(unique_disasters)} unique disasters")
        
        # Choose matching declaration
        chosen_declaration = None
        if args.auto_match and len(declarations) == 1:
            chosen_declaration = declarations[0]
            print(f"  Auto-matched to {chosen_declaration['disasterNumber']} - {chosen_declaration['declarationTitle']}")
        else:
            chosen_declaration = choose_matching_declaration(metadata, unique_disasters)
        
        if not chosen_declaration:
            print(f"  No declaration chosen for {doc_id}")
            unprocessed.append((doc_id, metadata, "No declaration chosen"))
            continue
        
        # Update declaration ID
        fema_id = chosen_declaration.get("disasterNumber")
        if not args.dry_run:
            try:
                storage.update_declaration_id(doc_id, fema_id)
                print(f"  Updated {doc_id} with FEMA declaration ID: {fema_id}")
                matched.append((doc_id, metadata, fema_id))
            except Exception as e:
                print(f"  Error updating {doc_id}: {e}")
                unprocessed.append((doc_id, metadata, f"Error updating: {e}"))
        else:
            print(f"  [DRY RUN] Would update {doc_id} with FEMA declaration ID: {fema_id}")
            matched.append((doc_id, metadata, fema_id))
    
    # Summary
    print("\n" + "="*80)
    print(f"SUMMARY: Processed {len(all_documents)} documents")
    print(f"  - {len(matched)} successfully matched")
    print(f"  - {len(unprocessed)} unprocessed")
    
    if unprocessed:
        print("\nUnprocessed documents (review manually):")
        for doc_id, metadata, reason in unprocessed:
            print(f"  - {doc_id}: {metadata.get('original_filename', 'Unknown')}")
            print(f"    Reason: {reason}")
            print(f"    State: {metadata.get('state_or_tribe', 'Unknown')}")
            print(f"    Incident Date: {metadata.get('incident_period_beginning_date', 'Unknown')}")
            print(f"    Incident Type: {metadata.get('incident_type', 'Unknown')}")
            print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
