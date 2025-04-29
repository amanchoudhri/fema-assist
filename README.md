# FEMA Disaster Declarations Agent

A system for processing and analyzing FEMA disaster declaration forms (Form 010-0-13).

## Overview

This project aims to develop an intelligent assistant to help state and local government officials navigate the complex process of applying for federal assistance after a natural disaster. The system uses LLMs to process disaster declaration forms and extract structured data; next, we'll develop and benchmark the capability to fill out forms automatically.

## Current Status

- Implemented PDF parsing pipeline using DocETL with [97.5% field extraction accuracy](experiments/2025-04-28)
- Created storage system for managing declaration documents and metadata
- Added capabilities to match declarations with FEMA disaster IDs and fetch associated Preliminary Damage Assessment (PDA) reports

## Components

- **Storage System**: UUID-based document management with metadata tracking
- **Parsing Pipeline**: Extracts structured data from PDFs using LLMs
- **Evaluation Pipeline**: Verifies extraction accuracy against ground truth (12 reports manually parsed/transcribed)
- **FEMA Data Integration**: Matches declarations with official FEMA disaster IDs and PDA reports

## Setup Instructions

### Prerequisites

- Python 3.8+
- DocETL (`pip install docetl`)
- Required Python packages: `requirements.txt`

### Installation

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Download the dataset, available [here](https://drive.google.com/drive/folders/1YOuMQRD7gwXDvIr_Pi4EUOwn6cIpYdbj?usp=drive_link):
   - `metadata.jsonl` - Declaration metadata
   - `pdfs.zip` - PDF documents

### Setting Up the Data

```bash
# Set up the declaration repository with PDFs and metadata
python scripts/setup_declarations.py --pdf-archive path/to/pdfs.zip --jsonl-file path/to/metadata.jsonl
```

### Running the Parser

```bash
# Parse declarations from storage
python -m fema_agent.parse --storage-dir data/processed/all-declarations --outpath parsed_results.json --model gemini-2.0-flash-lite

# Update storage with parsed results
python -m fema_agent.parse --storage-dir data/processed/all-declarations --outpath parsed_results.json --update-storage
```

### Evaluation

```bash
# Check parsed results against ground truth
python -m fema_agent.check parsed_results.json --ground-truth data/ground_truth/test_set_truth.json
```

## Project Structure

- `src/fema_agent/` - Core agent code
  - `storage.py` - Document storage system
  - `parse.py` - Parsing pipeline
  - `check.py` - Evaluation pipeline
  - `forms/` - Form field definitions
- `scripts/` - Utility scripts for setup and data processing/linking
- `experiments/` - Evaluation results and experiments
