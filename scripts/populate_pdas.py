"""
Script to populate PDA reports for documents in a storage directory
Uses functionality from pull_pda.py to search and fetch reports by FEMA disaster ID
Implements simple multiprocessing for parallel API requests
"""

import argparse
import os
import time
import sys
from datetime import datetime
from collections import defaultdict
import multiprocessing as mp
from functools import partial

from fema_agent.storage import DeclarationStorage
from fema_agent.pull_pda import search_fema_pda_reports, fetch_report_details

def process_document(doc_id, info, storage_dir, force=False, delay=0.1):
    """
    Process a single document and fetch its PDA report
    
    Args:
        doc_id (str): Document UUID
        info (dict): Document information
        storage_dir (str): Path to the storage directory
        force (bool): If True, re-fetch reports even if they already exist
        delay (float): Delay between API requests to avoid rate limiting
        
    Returns:
        tuple: (doc_id, result_dict) where result_dict contains processing info
    """
    result = {
        'status': 'error',
        'id': doc_id,
        'filename': info.get('original_filename', 'Unknown'),
        'reports_found': 0,
        'reports_fetched': 0,
        'reason': None,
        'reports': []
    }
    
    try:
        storage = DeclarationStorage(storage_dir)
        
        # Get full metadata
        metadata = storage.get_document_metadata(doc_id)
        result['state'] = metadata.get('state_or_tribe', 'Unknown')
        
        # Skip if already has PDA report and not forcing
        if not force and metadata.get('pda_report'):
            result['status'] = 'skipped'
            result['reason'] = 'already_has_report'
            return doc_id, result
        
        # Extract FEMA disaster number
        disaster_num = metadata.get('fema_declaration_id')
        
        if disaster_num:
            # Search for PDA reports using disaster number
            reports = search_fema_pda_reports(disaster_num=str(disaster_num))
        else:
            # Search for PDA reports using state and year
            year = datetime.strptime(metadata['request_date'], '%Y-%m-%d').year
            reports = search_fema_pda_reports(
                    state=metadata['state_or_tribe'],
                    year=year
                    )
        
        if not reports:
            result['status'] = 'skipped'
            result['reason'] = 'no_reports_found'
            return doc_id, result
            
        result['reports_found'] = len(reports)
        result['reports'] = [(report['title'], report['date'], report['full_url']) 
                              for report in reports]
        
        # If multiple reports are found, skip
        if len(reports) > 1:
            result['status'] = 'skipped'
            result['reason'] = 'multiple_reports'
            return doc_id, result
        
        # Only one report found, proceed with fetching
        report = reports[0]
        
        # Add delay to avoid overwhelming the server
        if delay > 0:
            time.sleep(delay)
            
        # Fetch the report content
        report_text = None
        if report['full_url']:
            report_text = fetch_report_details(report['full_url'])
            
        if report_text:
            # Store the report text in metadata
            storage.store_pda_report(
                doc_id,
                report_text,
                pda_report_title=report['title'],
                pda_report_date=report['date'],
                pda_report_url=report['full_url'],
                pda_report_fetched_date=datetime.now().isoformat()
                )

            result['status'] = 'success'
            result['reports_fetched'] = 1
        else:
            result['status'] = 'skipped'
            result['reason'] = 'fetch_failed'
            
    except Exception as e:
        result['status'] = 'error'
        result['reason'] = 'error'
        result['error_message'] = str(e)
    
    return doc_id, result

def process_storage_directory_parallel(storage_dir, force=False, workers=None, delay=0.1):
    """
    Process all documents in a storage directory in parallel and fetch PDA reports
    
    Args:
        storage_dir (str): Path to the storage directory
        force (bool): If True, re-fetch reports even if they already exist
        workers (int): Number of worker processes (default: CPU count)
        delay (float): Delay between API requests to avoid rate limiting (in seconds)
        
    Returns:
        dict: Statistics about the operation and skipped documents
    """
    if workers is None:
        workers = min(mp.cpu_count(), 8)  # Default to CPU count, but cap at 8
    
    storage = DeclarationStorage(storage_dir)
    documents = storage.get_all_documents()
    
    stats = {
        'total': len(documents),
        'processed': 0,
        'reports_found': 0,
        'reports_fetched': 0,
        'errors': 0,
        'skipped': defaultdict(list)  # Track skipped documents by reason
    }
    
    print(f"Found {stats['total']} documents in storage.")
    print(f"Processing with {workers} worker processes...")
    
    # Prepare the worker function with partial to fix some arguments
    worker_func = partial(process_document, 
                          storage_dir=storage_dir, 
                          force=force,
                          delay=delay)
    
    # List to hold tasks for processing
    tasks = []
    
    # Create tasks
    for doc_id, info in documents.items():
        tasks.append((doc_id, info))
    
    # Process documents in parallel
    with mp.Pool(workers) as pool:
        results = []
        for i, result in enumerate(pool.starmap(worker_func, tasks), 1):
            doc_id, doc_result = result
            results.append(doc_result)
            
            # Update stats
            stats['processed'] += 1
            
            if doc_result['status'] == 'success':
                stats['reports_fetched'] += doc_result['reports_fetched']
                stats['reports_found'] += doc_result['reports_found']
            elif doc_result['status'] == 'error':
                stats['errors'] += 1
                stats['skipped']['error'].append({
                    'id': doc_id,
                    'filename': doc_result['filename'],
                    'error': doc_result.get('error_message', 'Unknown error')
                })
            elif doc_result['status'] == 'skipped':
                reason = doc_result['reason']
                doc_info = {
                    'id': doc_id,
                    'filename': doc_result['filename'],
                    'state': doc_result.get('state', 'Unknown')
                }
                
                if reason == 'multiple_reports':
                    doc_info['reports'] = doc_result['reports']
                
                stats['skipped'][reason].append(doc_info)
            
            # Print progress
            print(f"\rProcessing: {stats['processed']}/{stats['total']} documents ({int(stats['processed']/stats['total']*100)}%)", end='')
            
            # Occasionally flush stdout for responsive feedback
            if i % 10 == 0:
                sys.stdout.flush()
    
    print("\nProcessing complete!")
    return stats

def process_multiple_report_documents(stats, storage_dir):
    """
    Process documents that have multiple PDA reports by allowing the user to select one
    
    Args:
        stats (dict): Statistics about the processed documents
        storage_dir (str): Path to the storage directory
        
    Returns:
        dict: Updated statistics
    """
    if not stats['skipped']['multiple_reports']:
        return stats  # No documents with multiple reports
    
    print("\n" + "="*80)
    print(f"DOCUMENTS WITH MULTIPLE PDA REPORTS ({len(stats['skipped']['multiple_reports'])})")
    print("="*80)
    print("\nYou can select a specific report for each document:")
    
    storage = DeclarationStorage(storage_dir)
    processed_docs = []  # Track which documents were processed
    
    # Process each document with multiple reports
    for doc_info in stats['skipped']['multiple_reports']:
        doc_id = doc_info['id']
        
        try:
            # Get full metadata for the document
            metadata = storage.get_document_metadata(doc_id)
            
            # Display document information
            print("\n" + "-"*80)
            print(f"Document: {doc_info['filename']}")
            print(f"State: {metadata.get('state_or_tribe', 'Unknown')}")
            print(f"Incident Begin Date: {metadata.get('incident_period_beginning_date', 'Unknown')}")
            print(f"Request Date: {metadata.get('request_date', 'Unknown')}")
            print(f"Request Purpose: {metadata.get('request_purpose', 'Unknown')}")
            print("-"*80)
            
            # Display available reports
            print("\nAvailable PDA Reports:")
            for idx, (title, date, url) in enumerate(doc_info['reports'], 1):
                print(f"{idx}. {title} ({date})")
                print(f"   URL: {url}")
            
            # Prompt user for selection
            print("\n0. Skip this document")
            
            choice = None
            while choice is None:
                try:
                    choice = int(input("\nSelect a report (0 to skip): "))
                    if choice < 0 or choice > len(doc_info['reports']):
                        print(f"Invalid choice. Please enter a number between 0 and {len(doc_info['reports'])}")
                        choice = None
                except ValueError:
                    print("Please enter a number.")
                    choice = None
            
            # Process the user's choice
            if choice == 0:
                print("Skipping this document.")
                continue
            
            # Get the selected report
            selected_idx = choice - 1
            selected_title, selected_date, selected_url = doc_info['reports'][selected_idx]
            
            # Fetch the report content
            print(f"Fetching report {choice}...")
            report_text = fetch_report_details(selected_url)
            
            if report_text:
                # Store the report in the document metadata
                storage.store_pda_report(
                    doc_id,
                    report_text,
                    pda_report_title=selected_title,
                    pda_report_date=selected_date,
                    pda_report_url=selected_url,
                    pda_report_fetched_date=datetime.now().isoformat()
                )
                
                print(f"Successfully stored report for document {doc_id}")
                
                # Update statistics
                stats['reports_fetched'] += 1
                processed_docs.append(doc_id)
            else:
                print(f"Failed to fetch report content for document {doc_id}")
                
        except Exception as e:
            print(f"Error processing document {doc_id}: {str(e)}")
    
    # Update statistics - remove successfully processed documents from the skipped list
    if processed_docs:
        stats['skipped']['multiple_reports'] = [
            doc for doc in stats['skipped']['multiple_reports'] 
            if doc['id'] not in processed_docs
        ]
        
        print(f"\nSuccessfully processed {len(processed_docs)} documents with multiple reports")
    
    return stats

def print_skipped_documents(stats):
    """Print details about skipped documents"""
    print("\n=== SKIPPED DOCUMENTS ===")
    
    # No FEMA ID
    if stats['skipped']['no_fema_id']:
        print(f"\nDocuments with no FEMA ID ({len(stats['skipped']['no_fema_id'])}):")
        for doc in stats['skipped']['no_fema_id']:
            print(f"  - {doc['id']} ({doc['state']}): {doc['filename']}")
    
    # No reports found
    if stats['skipped']['no_reports_found']:
        print(f"\nDocuments with no PDA reports found ({len(stats['skipped']['no_reports_found'])}):")
        for doc in stats['skipped']['no_reports_found']:
            print(f"  - {doc['id']}: {doc['filename']}")
    
    # Multiple reports
    if stats['skipped']['multiple_reports']:
        print(f"\nDocuments with multiple PDA reports ({len(stats['skipped']['multiple_reports'])}):")
        for doc in stats['skipped']['multiple_reports']:
            print(f"  - {doc['id']}: {doc['filename']}")
            print(f"    Available reports:")
            for idx, (title, date, url) in enumerate(doc['reports'], 1):
                print(f"      {idx}. {title} ({date})")
                print(f"         {url}")
    
    # Fetch failures
    if stats['skipped']['fetch_failed']:
        print(f"\nDocuments where fetching PDA report failed ({len(stats['skipped']['fetch_failed'])}):")
        for doc in stats['skipped']['fetch_failed']:
            print(f"  - {doc['id']}: {doc['filename']}")
    
    # Already has report
    if stats['skipped']['already_has_report']:
        print(f"\nDocuments that already have PDA reports ({len(stats['skipped']['already_has_report'])})")
    
    # Errors
    if stats['skipped']['error']:
        print(f"\nDocuments with errors ({len(stats['skipped']['error'])}):")
        for doc in stats['skipped']['error']:
            print(f"  - {doc['id']}: {doc['filename']}")
            print(f"    Error: {doc['error']}")

def main():
    parser = argparse.ArgumentParser(description='Populate PDA reports for documents in storage using FEMA IDs')
    parser.add_argument('storage_dir', help='Path to the storage directory')
    parser.add_argument('--force', action='store_true', help='Re-fetch reports even if they already exist')
    parser.add_argument('--output', help='Path to save skipped documents report (default: print to console)')
    
    args = parser.parse_args()
    
    storage_dir = args.storage_dir
    if not os.path.isdir(storage_dir):
        print(f"Error: Storage directory '{storage_dir}' not found")
        return 1
        
    stats = process_storage_directory_parallel(
        storage_dir, 
        force=args.force,
    )

    # Allow user to select reports for documents with multiple matches
    if stats['skipped']['multiple_reports']:
        stats = process_multiple_report_documents(stats, storage_dir)
    
    print("\nProcessing Summary:")
    print(f"Total documents: {stats['total']}")
    print(f"Documents processed: {stats['processed']}")
    print(f"Documents skipped with no FEMA ID: {len(stats['skipped']['no_fema_id'])}")
    print(f"Documents skipped with no PDA reports: {len(stats['skipped']['no_reports_found'])}")
    print(f"Documents skipped with multiple PDA reports: {len(stats['skipped']['multiple_reports'])}")
    print(f"Documents skipped due to fetch failure: {len(stats['skipped']['fetch_failed'])}")
    print(f"Documents skipped that already have reports: {len(stats['skipped']['already_has_report'])}")
    print(f"PDA reports found: {stats['reports_found']}")
    print(f"PDA reports fetched and stored: {stats['reports_fetched']}")
    print(f"Errors encountered: {stats['errors']}")
    
    # Print detailed information about skipped documents
    if args.output:
        # Save to file
        with open(args.output, 'w') as f:
            original_stdout = sys.stdout
            sys.stdout = f
            print_skipped_documents(stats)
            sys.stdout = original_stdout
        print(f"\nSkipped documents report saved to: {args.output}")
    else:
        # Print to console
        print_skipped_documents(stats)
    
    return 0

if __name__ == "__main__":
    import sys
    exit(main())
